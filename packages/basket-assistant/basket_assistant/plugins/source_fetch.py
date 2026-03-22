"""Resolve plugin install source: local dir, zip/tar file or URL, or git clone."""

from __future__ import annotations

import asyncio
import logging
import re
import tarfile
import zipfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_MAX_URL_LEN = 2048
_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$", re.IGNORECASE)


@dataclass
class MaterializedPluginRoot:
    """Plugin root path and optional tempfile backing (for cleanup)."""

    path: Path
    _tmpdir: Optional[tempfile.TemporaryDirectory[str]] = None

    def cleanup_tmp(self) -> None:
        if self._tmpdir is not None:
            try:
                self._tmpdir.cleanup()
            except Exception:
                logger.debug("Temp dir cleanup failed", exc_info=True)
            self._tmpdir = None


@dataclass(frozen=True)
class ParsedInstallSource:
    """What to fetch and optional git ref."""

    kind: str  # "local_dir" | "local_archive" | "url_archive" | "git"
    primary: str  # path string or clone URL (no fragment)
    ref: Optional[str] = None  # git branch/tag/sha or None


def parse_install_source(raw: str) -> tuple[Optional[ParsedInstallSource], Optional[str]]:
    """Parse user install source string. Returns (parsed, error_message)."""
    text = (raw or "").strip()
    if not text:
        return None, "Empty source"

    ref_from_fragment: Optional[str] = None
    main_part = text
    ref_from_space: Optional[str] = None

    parts = text.split(maxsplit=1)
    if len(parts) == 2:
        main_part, ref_from_space = parts[0], parts[1].strip() or None

    if main_part.startswith(("http://", "https://")):
        parsed_url = urlparse(main_part)
        if parsed_url.fragment:
            ref_from_fragment = parsed_url.fragment.strip() or None
            # Rebuild URL without fragment
            main_part = parsed_url._replace(fragment="").geturl().rstrip("#")

    ref = ref_from_fragment or ref_from_space

    if len(main_part) > _MAX_URL_LEN:
        return None, "Source string too long"

    path_candidate = Path(main_part).expanduser()
    if path_candidate.is_dir():
        return ParsedInstallSource(kind="local_dir", primary=str(path_candidate.resolve()), ref=None), None

    lower = main_part.lower()
    is_archive_name = lower.endswith(".zip") or lower.endswith(".tar.gz") or lower.endswith(".tgz")
    if path_candidate.is_file() and is_archive_name:
        return ParsedInstallSource(
            kind="local_archive", primary=str(path_candidate.resolve()), ref=None
        ), None

    if main_part.startswith("git@"):
        return ParsedInstallSource(kind="git", primary=main_part, ref=ref), None

    parsed = urlparse(main_part)
    scheme = (parsed.scheme or "").lower()
    if scheme in ("http", "https"):
        path_lower = (parsed.path or "").lower()
        if is_archive_name or any(path_lower.endswith(s) for s in (".zip", ".tar.gz", ".tgz")):
            return ParsedInstallSource(kind="url_archive", primary=main_part, ref=None), None
        return ParsedInstallSource(kind="git", primary=main_part, ref=ref), None

    return None, f"Source is not a directory or supported URL: {main_part}"


def _find_plugin_root(extract_dir: Path) -> Path:
    """If single top-level dir and it validates as plugin root, use it; else extract_dir."""
    from .manifest import validate_plugin_dir

    entries = [p for p in extract_dir.iterdir() if p.name != "__MACOSX"]
    if len(entries) == 1 and entries[0].is_dir():
        sub = entries[0]
        if not validate_plugin_dir(sub):
            return sub
    return extract_dir


def _extract_archive(archive_path: Path, dest: Path) -> Path:
    """Extract zip or tar.gz/tgz into dest; return plugin root path."""
    dest.mkdir(parents=True, exist_ok=True)
    lower = archive_path.name.lower()
    if lower.endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(dest)
    elif lower.endswith(".tar.gz") or lower.endswith(".tgz"):
        with tarfile.open(archive_path, "r:*") as tf:
            try:
                tf.extractall(dest, filter="data")
            except TypeError:
                tf.extractall(dest)
    else:
        raise ValueError(f"Unsupported archive: {archive_path}")
    return _find_plugin_root(dest)


async def _run_git(args: list[str], cwd: Optional[Path] = None) -> tuple[int, str, str]:
    """Run git with args; return (code, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out_b, err_b = await proc.communicate()
    out = out_b.decode(errors="replace") if out_b else ""
    err = err_b.decode(errors="replace") if err_b else ""
    return proc.returncode or 0, out, err


async def materialize_plugin_source(
    parsed: ParsedInstallSource,
    *,
    progress_sink: Optional[Callable[[dict], Awaitable[None]]] = None,
) -> tuple[Optional[MaterializedPluginRoot], Optional[str]]:
    """
    Materialize plugin to a path (temporary when not local_dir).
    Caller must call .cleanup_tmp() on the wrapper when done copying.
    """
    tmp: Optional[tempfile.TemporaryDirectory[str]] = None

    async def _sink(payload: dict) -> None:
        if progress_sink is not None:
            await progress_sink(payload)

    try:
        if parsed.kind == "local_dir":
            return MaterializedPluginRoot(path=Path(parsed.primary).resolve()), None

        if parsed.kind == "local_archive":
            tmp = tempfile.TemporaryDirectory(prefix="basket-plugin-")
            root = Path(tmp.name)
            try:
                plugin_root = _extract_archive(Path(parsed.primary), root)
            except (OSError, zipfile.BadZipFile, tarfile.TarError, ValueError) as e:
                tmp.cleanup()
                return None, f"Failed to extract archive: {e}"
            return MaterializedPluginRoot(path=plugin_root, _tmpdir=tmp), None

        if parsed.kind == "url_archive":
            tmp = tempfile.TemporaryDirectory(prefix="basket-plugin-")
            root = Path(tmp.name)
            archive_file = root / "download.bin"
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
                    resp = await client.get(parsed.primary)
                    resp.raise_for_status()
                    archive_file.write_bytes(resp.content)
                plugin_root = _extract_archive(archive_file, root / "extract")
            except httpx.HTTPError as e:
                tmp.cleanup()
                return None, f"Download failed: {e}"
            except (OSError, zipfile.BadZipFile, tarfile.TarError, ValueError) as e:
                tmp.cleanup()
                return None, f"Failed to extract download: {e}"
            return MaterializedPluginRoot(path=plugin_root, _tmpdir=tmp), None

        if parsed.kind == "git":
            tmp = tempfile.TemporaryDirectory(prefix="basket-plugin-git-")
            clone_dest = Path(tmp.name) / "repo"
            clone_dest.parent.mkdir(parents=True, exist_ok=True)
            url = parsed.primary
            ref = (parsed.ref or "").strip() or None
            is_sha = bool(ref and _SHA_RE.match(ref))

            await _sink({"type": "plugin_install_progress", "phase": "git_clone", "detail": "cloning"})

            try:
                if ref and not is_sha:
                    code, _, err = await _run_git(
                        [
                            "git",
                            "clone",
                            "--depth",
                            "1",
                            "--branch",
                            ref,
                            url,
                            str(clone_dest),
                        ]
                    )
                    if code != 0:
                        tmp.cleanup()
                        return None, f"git clone failed: {err.strip() or 'unknown error'}"
                else:
                    code, _, err = await _run_git(
                        ["git", "clone", "--depth", "1", url, str(clone_dest)]
                    )
                    if code != 0:
                        tmp.cleanup()
                        return None, f"git clone failed: {err.strip() or 'unknown error'}"
                    if is_sha and ref is not None:
                        await _sink(
                            {
                                "type": "plugin_install_progress",
                                "phase": "git_checkout",
                                "detail": ref,
                            }
                        )
                        code2, _, err2 = await _run_git(
                            ["git", "-C", str(clone_dest), "fetch", "--depth", "1", "origin", ref]
                        )
                        if code2 != 0:
                            tmp.cleanup()
                            return None, f"git fetch {ref} failed: {err2.strip() or 'unknown error'}"
                        code3, _, err3 = await _run_git(
                            ["git", "-C", str(clone_dest), "checkout", ref]
                        )
                        if code3 != 0:
                            tmp.cleanup()
                            return None, f"git checkout {ref} failed: {err3.strip() or 'unknown error'}"
            except FileNotFoundError:
                tmp.cleanup()
                raise

            return MaterializedPluginRoot(path=clone_dest, _tmpdir=tmp), None

        return None, f"Unsupported source kind: {parsed.kind}"
    except FileNotFoundError:
        return None, "git executable not found on PATH"
    except Exception as e:
        logger.exception("materialize_plugin_source failed")
        return None, str(e)


__all__ = [
    "MaterializedPluginRoot",
    "ParsedInstallSource",
    "parse_install_source",
    "materialize_plugin_source",
]
