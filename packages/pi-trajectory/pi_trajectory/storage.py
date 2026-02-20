"""
Trajectory storage: write and load TaskTrajectory to/from disk.
"""

import json
from pathlib import Path
from typing import List, Union

from .schema import TaskTrajectory


def write_trajectory(trajectory: TaskTrajectory, path: Union[Path, str]) -> None:
    """Write a single trajectory to a JSON file."""
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = trajectory.model_dump(mode="json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_trajectory(path: Union[Path, str]) -> TaskTrajectory:
    """Load a single trajectory from a JSON file."""
    path = Path(path).expanduser()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return TaskTrajectory.model_validate(data)


def load_trajectories(dir_or_path: Union[Path, str]) -> List[TaskTrajectory]:
    """
    Load trajectories from a directory (all .json) or a single file.

    If dir_or_path is a directory, loads all *.json files in it.
    If it is a file, returns a single-element list.
    """
    path = Path(dir_or_path).expanduser()
    if path.is_file():
        return [load_trajectory(path)]
    if not path.is_dir():
        return []
    out: List[TaskTrajectory] = []
    for f in sorted(path.glob("*.json")):
        try:
            out.append(load_trajectory(f))
        except Exception:
            continue
    return out
