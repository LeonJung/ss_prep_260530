"""UR10E ROS2 IO: joint_state subscriber + JTC action client.

Two state topics depending on mode:
  - record:   /ur10e/follower/joint_state (teleop stack, ~50 Hz)
  - deploy:   /joint_states              (ros2_control native, ~100 Hz)

Command path (deploy only): joint_trajectory_controller action.
"""

from __future__ import annotations

import threading
import time

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import JointState


class UR10EIO:
    """Minimal IO bound to a host rclpy Node.

    The caller owns the Node and the executor; this class only wires
    subscriptions/clients onto it. That keeps RobotIO single-node.
    """

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
        self._stamp = 0.0
        # Map incoming joint_name -> our canonical index. Computed lazily
        # because incoming order is not guaranteed.
        self._name_to_idx: dict[str, int] | None = None

        # SENSOR_DATA = BEST_EFFORT + KEEP_LAST(5). Matches both default
        # RELIABLE and SENSOR_DATA publishers; default RELIABLE subscribers
        # silently miss every message from a BEST_EFFORT teleop publisher.
        self._sub = node.create_subscription(
            JointState, state_topic, self._on_joint_state, qos_profile_sensor_data
        )

        self._action_client = None  # lazily created in deploy mode
        if command_action is not None:
            # Defer control_msgs / trajectory_msgs import — they aren't
            # installed on the dev PC.
            from control_msgs.action import FollowJointTrajectory
            from rclpy.action import ActionClient

            self._FollowJointTrajectory = FollowJointTrajectory
            self._action_client = ActionClient(
                node, FollowJointTrajectory, command_action
            )

    # ---- subscription ----------------------------------------------------

    def _on_joint_state(self, msg: JointState) -> None:
        if self._name_to_idx is None:
            self._name_to_idx = self._build_index(list(msg.name))
            if self._name_to_idx is None:
                # Names didn't match expected set — keep trying next message.
                return
        idx = self._name_to_idx
        pos = np.asarray(msg.position, dtype=np.float32)
        vel = (
            np.asarray(msg.velocity, dtype=np.float32)
            if len(msg.velocity) == len(msg.position)
            else np.zeros_like(pos)
        )
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        with self._lock:
            for name, src_i in idx.items():
                dst_i = self._canonical_idx[name]
                self._position[dst_i] = pos[src_i]
                self._velocity[dst_i] = vel[src_i]
            self._stamp = stamp

    def _build_index(self, incoming: list[str]) -> dict[str, int] | None:
        # Accept the message only if every canonical joint is present.
        self._canonical_idx = {n: i for i, n in enumerate(self._joint_names)}
        mapping: dict[str, int] = {}
        for name in self._joint_names:
            if name not in incoming:
                self._node.get_logger().warn(
                    f"UR10EIO: joint '{name}' not in incoming msg "
                    f"(have {incoming}). Will retry."
                )
                return None
            mapping[name] = incoming.index(name)
        return mapping

    # ---- snapshot --------------------------------------------------------

    def has_state(self) -> bool:
        with self._lock:
            return self._stamp > 0.0

    def snapshot(self) -> tuple[np.ndarray, np.ndarray, float]:
        with self._lock:
            return self._position.copy(), self._velocity.copy(), self._stamp

    # ---- commands --------------------------------------------------------

    def send_joint_position(
        self, position: np.ndarray, time_from_start_s: float = 0.05
    ) -> None:
        """Send a single-point JTC goal. Returns immediately (fire-and-forget)."""
        if self._action_client is None:
            raise RuntimeError(
                "UR10EIO has no command_action configured (record-only mode)"
            )
        if position.shape != (self._dof,):
            raise ValueError(
                f"position shape {position.shape} != expected ({self._dof},)"
            )
        if not self._action_client.server_is_ready():
            # Don't block the loop — log and skip.
            self._node.get_logger().warn(
                f"UR10EIO: JTC action server {self._command_action} not ready"
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
        """Spin-friendly wait. Caller must be running an executor in another thread."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self.has_state():
                return True
            time.sleep(0.05)
        return False
