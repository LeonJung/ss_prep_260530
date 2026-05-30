"""Unified RobotIO: one rclpy node + executor thread + synchronous get/send API.

Consumers (recorder, runner) don't touch rclpy directly. Use as:

    with RobotIO.from_yaml("pai_teach/configs/robot.yaml", mode="record") as io:
        io.wait_until_ready()
        obs = io.get_observation()
        # ... at deploy time:
        io.send_action(Action(ur10e_position=..., dg5f_position=...))
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Literal

import numpy as np
import rclpy
import yaml
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from .camera_io import CameraBank, CameraSpec
from .dg5f_io import DG5FIO
from .types import Action, Observation, RobotState
from .ur10e_io import UR10EIO

Mode = Literal["record", "deploy"]


class RobotIO:
    """Single host node owning UR10E, dg5f, and camera IO."""

    def __init__(
        self,
        config: dict,
        mode: Mode = "record",
        node_name: str = "pai_teach_robot_io",
    ) -> None:
        self._mode = mode
        self._config = config

        if not rclpy.ok():
            rclpy.init()
        self._node = Node(node_name)

        ur_cfg = config["ur10e"]
        state_topic = (
            ur_cfg["state_topic_teleop"]
            if mode == "record"
            else ur_cfg["state_topic_deploy"]
        )
        command_action = ur_cfg["command_action"] if mode == "deploy" else None
        self.ur10e = UR10EIO(
            self._node,
            joint_names=ur_cfg["joint_names"],
            state_topic=state_topic,
            command_action=command_action,
        )

        hand_cfg = config["dg5f"]
        hand_cmd = hand_cfg["command_topic"] if mode == "deploy" else None
        self.dg5f = DG5FIO(
            self._node,
            joint_names=hand_cfg["joint_names"],
            state_topic=hand_cfg["state_topic"],
            command_topic=hand_cmd,
        )

        cam_specs = [
            CameraSpec(
                name=c["name"],
                topic=c["topic"],
                compressed=bool(c.get("compressed", False)),
                width=c.get("width"),
                height=c.get("height"),
            )
            for c in config.get("cameras", [])
        ]
        self.cameras = CameraBank(self._node, cam_specs)

        self._executor = MultiThreadedExecutor()
        self._executor.add_node(self._node)
        self._spin_thread = threading.Thread(
            target=self._executor.spin, name="rclpy-spin", daemon=True
        )
        self._spin_thread.start()

    # ---- factory ---------------------------------------------------------

    @classmethod
    def from_yaml(cls, path: str | Path, mode: Mode = "record") -> "RobotIO":
        cfg = yaml.safe_load(Path(path).read_text())
        return cls(cfg, mode=mode)

    # ---- context mgmt ----------------------------------------------------

    def __enter__(self) -> "RobotIO":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.shutdown()

    def shutdown(self) -> None:
        try:
            self._executor.shutdown()
        finally:
            self._node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()

    # ---- readiness -------------------------------------------------------

    def wait_until_ready(self, timeout_s: float = 10.0) -> None:
        """Block until all subscriptions have produced at least one message."""
        deadline = time.monotonic() + timeout_s
        ok_ur = self.ur10e.wait_for_state(max(0.1, deadline - time.monotonic()))
        ok_hand = self.dg5f.wait_for_state(max(0.1, deadline - time.monotonic()))
        ok_cams = self.cameras.wait_for_all(max(0.1, deadline - time.monotonic()))
        if not (ok_ur and ok_hand and ok_cams):
            missing = []
            if not ok_ur:
                missing.append("ur10e")
            if not ok_hand:
                missing.append("dg5f")
            if not ok_cams:
                missing.append("cameras")
            raise TimeoutError(
                f"RobotIO not ready after {timeout_s}s; missing: {missing}"
            )

    # ---- read ------------------------------------------------------------

    def get_observation(self) -> Observation:
        ur_pos, ur_vel, ur_t = self.ur10e.snapshot()
        h_pos, h_vel, h_eff, h_t = self.dg5f.snapshot()
        state = RobotState(
            ur10e_position=ur_pos,
            ur10e_velocity=ur_vel,
            dg5f_position=h_pos,
            dg5f_velocity=h_vel,
            dg5f_effort=h_eff,
            ur10e_stamp=ur_t,
            dg5f_stamp=h_t,
        )
        images = self.cameras.snapshot()
        return Observation(state=state, images=images, stamp=time.monotonic())

    # ---- write -----------------------------------------------------------

    def send_action(self, action: Action, time_from_start_s: float = 0.05) -> None:
        if self._mode != "deploy":
            raise RuntimeError(
                "send_action is only valid in 'deploy' mode "
                "(record mode has no command publishers)"
            )
        # UR10E uses JTC (action) — needs a time_from_start.
        # dg5f uses a multi-DOF PidController (publisher) — no horizon, just
        # publish the next position reference; PID does the rest.
        self.ur10e.send_joint_position(action.ur10e_position, time_from_start_s)
        self.dg5f.send_joint_position(action.dg5f_position)
