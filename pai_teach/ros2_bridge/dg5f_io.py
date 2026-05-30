"""dg5f (5-finger hand, 20 DoF) ROS2 IO.

State:   /dg5f_<side>/joint_states (~300 Hz)
Command: /dg5f_<side>/dg5f_<side>_controller/follow_joint_trajectory  (PID JTC)

The hardware command interface is effort-only; the JTC's PID converts our
position targets to motor current internally.
"""

from __future__ import annotations

import threading
import time

import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


class DG5FIO:
    def __init__(
        self,
        node: Node,
        joint_names: list[str],
        state_topic: str,
        command_action: str | None = None,
    ) -> None:
        self._node = node
        self._joint_names = list(joint_names)
        self._dof = len(joint_names)
        self._command_action = command_action

        self._lock = threading.Lock()
        self._position = np.zeros(self._dof, dtype=np.float32)
        self._velocity = np.zeros(self._dof, dtype=np.float32)
        self._effort = np.zeros(self._dof, dtype=np.float32)
        self._stamp = 0.0
        self._name_to_idx: dict[str, int] | None = None
        self._canonical_idx = {n: i for i, n in enumerate(self._joint_names)}

        self._sub = node.create_subscription(
            JointState, state_topic, self._on_joint_state, 30
        )

        self._action_client = None  # lazily created in deploy mode
        if command_action is not None:
            from control_msgs.action import FollowJointTrajectory
            from rclpy.action import ActionClient

            self._FollowJointTrajectory = FollowJointTrajectory
            self._action_client = ActionClient(
                node, FollowJointTrajectory, command_action
            )

    def _on_joint_state(self, msg: JointState) -> None:
        if self._name_to_idx is None:
            mapping: dict[str, int] = {}
            for name in self._joint_names:
                if name not in msg.name:
                    self._node.get_logger().warn(
                        f"DG5FIO: joint '{name}' not in msg (have {list(msg.name)})"
                    )
                    return
                mapping[name] = list(msg.name).index(name)
            self._name_to_idx = mapping

        pos = np.asarray(msg.position, dtype=np.float32)
        vel = (
            np.asarray(msg.velocity, dtype=np.float32)
            if len(msg.velocity) == len(msg.position)
            else np.zeros_like(pos)
        )
        eff = (
            np.asarray(msg.effort, dtype=np.float32)
            if len(msg.effort) == len(msg.position)
            else np.zeros_like(pos)
        )
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        with self._lock:
            for name, src_i in self._name_to_idx.items():
                dst_i = self._canonical_idx[name]
                self._position[dst_i] = pos[src_i]
                self._velocity[dst_i] = vel[src_i]
                self._effort[dst_i] = eff[src_i]
            self._stamp = stamp

    def has_state(self) -> bool:
        with self._lock:
            return self._stamp > 0.0

    def snapshot(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
        with self._lock:
            return (
                self._position.copy(),
                self._velocity.copy(),
                self._effort.copy(),
                self._stamp,
            )

    def send_joint_position(
        self, position: np.ndarray, time_from_start_s: float = 0.05
    ) -> None:
        if self._action_client is None:
            raise RuntimeError(
                "DG5FIO has no command_action configured (record-only mode)"
            )
        if position.shape != (self._dof,):
            raise ValueError(
                f"position shape {position.shape} != expected ({self._dof},)"
            )
        if not self._action_client.server_is_ready():
            self._node.get_logger().warn(
                f"DG5FIO: JTC action server {self._command_action} not ready"
            )
            return

        from builtin_interfaces.msg import Duration
        from trajectory_msgs.msg import JointTrajectoryPoint

        goal = self._FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = self._joint_names
        point = JointTrajectoryPoint()
        point.positions = [float(x) for x in position]
        sec = int(time_from_start_s)
        nsec = int((time_from_start_s - sec) * 1e9)
        point.time_from_start = Duration(sec=sec, nanosec=nsec)
        goal.trajectory.points = [point]
        self._action_client.send_goal_async(goal)

    def wait_for_state(self, timeout_s: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self.has_state():
                return True
            time.sleep(0.05)
        return False
