"""Fixed-rate recorder loop: RobotIO -> LeRobotWriter.

Action convention for teleop demos: there is no separate command stream
during bilateral teleop (UR10E is driven via RTDE direct-torque, dg5f via
PID JTC from the master glove). We therefore use the standard ACT
formulation `action[t] = state[t+1]` (next-step joint targets). The loop
buffers one frame and writes obs[t]/action=state[t+1] together.
"""

from __future__ import annotations

import signal
import time
from pathlib import Path

import numpy as np
import yaml

from ..ros2_bridge.types import Action, Observation
from .lerobot_writer import CameraInfo, LeRobotWriter


def _cameras_from_cfg(cfg: dict) -> list[CameraInfo]:
    return [
        CameraInfo(name=c["name"], height=int(c["height"]), width=int(c["width"]))
        for c in cfg.get("cameras", [])
    ]


def _state_to_action(obs: Observation) -> Action:
    return Action(
        ur10e_position=obs.state.ur10e_position.copy(),
        dg5f_position=obs.state.dg5f_position.copy(),
    )


class Recorder:
    def __init__(
        self,
        config_path: str | Path,
        repo_id: str,
        dataset_root: str | Path,
        task: str,
        *,
        dg5f_enabled: bool | None = None,
    ) -> None:
        self._cfg = yaml.safe_load(Path(config_path).read_text())
        if dg5f_enabled is not None:
            self._cfg["dg5f"]["enabled"] = bool(dg5f_enabled)
        self._task = task
        self._rate_hz = int(self._cfg.get("record_rate_hz", 30))
        # If dg5f is disabled at the IO layer, the dataset must also collapse
        # to UR-only — otherwise state/action shape mismatches the empty
        # arrays Observation/Action carry.
        dg5f_enabled = bool(self._cfg["dg5f"].get("enabled", True))
        dg5f_names = self._cfg["dg5f"]["joint_names"] if dg5f_enabled else []
        self._writer = LeRobotWriter(
            repo_id=repo_id,
            root=dataset_root,
            fps=self._rate_hz,
            ur10e_joint_names=self._cfg["ur10e"]["joint_names"],
            dg5f_joint_names=dg5f_names,
            cameras=_cameras_from_cfg(self._cfg),
            use_videos=bool(self._cfg.get("use_videos", True)),
        )
        # Lazy import so this module is importable on dev boxes without rclpy.
        from ..ros2_bridge.robot_io import RobotIO

        self._io = RobotIO(self._cfg, mode="record")
        self._stop = False
        signal.signal(signal.SIGINT, self._on_sigint)

    def _on_sigint(self, *_: object) -> None:
        self._stop = True

    def record_episode(self, max_seconds: float | None = None) -> int:
        """Record one episode. Returns number of frames written.

        Stops on SIGINT or when max_seconds elapses.
        """
        self._io.wait_until_ready(timeout_s=15.0)
        period = 1.0 / self._rate_hz
        prev_obs: Observation | None = None
        n_frames = 0
        t0 = time.monotonic()
        next_tick = t0
        try:
            while not self._stop:
                if max_seconds is not None and (time.monotonic() - t0) >= max_seconds:
                    break
                next_tick += period
                obs = self._io.get_observation()
                if prev_obs is not None:
                    action = _state_to_action(obs)
                    self._writer.add_frame(prev_obs, action, task=self._task)
                    n_frames += 1
                prev_obs = obs
                sleep_for = next_tick - time.monotonic()
                if sleep_for > 0:
                    time.sleep(sleep_for)
                else:
                    # Loop fell behind — skip catch-up to avoid bursting.
                    next_tick = time.monotonic()
        finally:
            if n_frames > 0:
                self._writer.save_episode()
        return n_frames

    def shutdown(self) -> None:
        self._io.shutdown()

    def __enter__(self) -> "Recorder":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.shutdown()
