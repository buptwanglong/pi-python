# pi-trajectory

Task trajectory recording for agent runs (RL and tuning).

## Usage

- **Schema**: `TaskTrajectory`, `TurnRecord`, `ToolCallRecord` (Pydantic, JSON-serializable).
- **Recorder**: `TrajectoryRecorder` — `start_task(user_input)`, `on_event(event)`, `finalize(state)`, `get_trajectory()`.
- **Storage**: `write_trajectory(trajectory, path)`, `load_trajectory(path)`, `load_trajectories(dir_or_path)`.

In pi-assistant, set `agent.trajectory_dir` in settings (or `PI_TRAJECTORY_DIR` env) to enable recording; each run writes a JSON file under that directory.
