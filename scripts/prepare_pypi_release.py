#!/usr/bin/env python3
"""
Prepare monorepo packages for PyPI: replace path dependencies with version
constraints so 'poetry build' produces installable sdist/wheel.

Usage:
  python scripts/prepare_pypi_release.py [--version 0.1.0] [--restore]
  --version: version constraint for internal deps (default: read from pi-ai)
  --restore: restore pyproject.toml from .pypi-release.bak (after build/upload)
"""

import argparse
import re
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGES_DIR = REPO_ROOT / "packages"

# Order: publish base packages first, then dependents
PUBLISH_ORDER = ["pi-ai", "pi-tui", "pi-agent", "pi-trajectory", "pi-coding-agent"]

# Per-package: path dep -> version dep (regex, replacement with {version})
PACKAGE_REPLACEMENTS: dict[str, list[tuple[str, str]]] = {
    "pi-agent": [
        (r'pi-ai = \{path = "\.\./pi-ai", develop = true\}', 'pi-ai = "^{version}"'),
    ],
    "pi-coding-agent": [
        (r'pi-ai = \{path = "\.\./pi-ai", develop = true\}', 'pi-ai = "^{version}"'),
        (r'pi-agent = \{path = "\.\./pi-agent", develop = true\}', 'pi-agent = "^{version}"'),
        (
            r'pi-trajectory = \{path = "\.\./pi-trajectory", develop = true\}',
            'pi-trajectory = "^{version}"',
        ),
        (
            r'pi-tui = \{path = "\.\./pi-tui", develop = true, optional = true\}',
            'pi-tui = {{version = "^{version}", optional = true}}',
        ),
    ],
}


def get_default_version() -> str:
    """Read version from pi-ai pyproject.toml."""
    path = PACKAGES_DIR / "pi-ai" / "pyproject.toml"
    text = path.read_text()
    m = re.search(r'^version = "([^"]+)"', text, re.MULTILINE)
    if m:
        return m.group(1)
    return "0.1.0"


def prepare_package(pkg_name: str, version: str) -> None:
    """Replace path deps with version deps in package pyproject.toml."""
    pyproject = PACKAGES_DIR / pkg_name / "pyproject.toml"
    if not pyproject.exists():
        return
    repls = PACKAGE_REPLACEMENTS.get(pkg_name, [])
    if not repls:
        return
    content = pyproject.read_text()
    original = content
    for pattern, repl in repls:
        repl_filled = repl.format(version=version)
        content = re.sub(pattern, repl_filled, content)
    if content != original:
        backup = pyproject.with_suffix(".toml.pypi-release.bak")
        shutil.copy(pyproject, backup)
        pyproject.write_text(content)
        print(f"  Prepared {pkg_name} (backup: {backup.name})")


def restore_package(pkg_name: str) -> None:
    """Restore pyproject.toml from backup."""
    pyproject = PACKAGES_DIR / pkg_name / "pyproject.toml"
    backup = pyproject.with_suffix(".toml.pypi-release.bak")
    if backup.exists():
        shutil.copy(backup, pyproject)
        backup.unlink()
        print(f"  Restored {pkg_name}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Prepare or restore pyproject for PyPI release")
    ap.add_argument("--version", default=None, help="Version constraint for internal deps (e.g. 0.1.0)")
    ap.add_argument("--restore", action="store_true", help="Restore all pyproject.toml from backup")
    args = ap.parse_args()

    if args.restore:
        for pkg in PUBLISH_ORDER:
            restore_package(pkg)
        print("Done. All pyproject.toml restored.")
        return

    version = args.version or get_default_version()
    print(f"Using version constraint: ^{version}")
    for pkg in PUBLISH_ORDER:
        prepare_package(pkg, version)
    print("Done. Run 'poetry build' in each package (in order), then upload. Use --restore to revert.")


if __name__ == "__main__":
    main()
