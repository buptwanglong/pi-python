"""Tests for trajectory storage."""

import pytest
from pathlib import Path

from basket_trajectory import TaskTrajectory, write_trajectory, load_trajectory, load_trajectories


def test_write_and_load_trajectory(tmp_path):
    tr = TaskTrajectory(
        task_id="task_1",
        started_at=1000.0,
        ended_at=1005.0,
        model_provider="openai",
        model_id="gpt-4",
        success=True,
        user_input="Hi",
        turns=[],
        total_turns=1,
    )
    path = tmp_path / "task_1.json"
    write_trajectory(tr, path)
    assert path.exists()
    loaded = load_trajectory(path)
    assert loaded.task_id == tr.task_id
    assert loaded.user_input == tr.user_input


def test_load_trajectories_dir(tmp_path):
    for i in range(2):
        tr = TaskTrajectory(
            task_id=f"task_{i}",
            started_at=1000.0,
            ended_at=1005.0,
            success=True,
            user_input=f"q{i}",
            total_turns=1,
        )
        write_trajectory(tr, tmp_path / f"task_{i}.json")
    out = load_trajectories(tmp_path)
    assert len(out) == 2
    assert {t.task_id for t in out} == {"task_0", "task_1"}


def test_load_trajectories_single_file(tmp_path):
    tr = TaskTrajectory(
        task_id="single",
        started_at=1000.0,
        ended_at=1005.0,
        success=True,
        total_turns=1,
    )
    path = tmp_path / "single.json"
    write_trajectory(tr, path)
    out = load_trajectories(path)
    assert len(out) == 1
    assert out[0].task_id == "single"
