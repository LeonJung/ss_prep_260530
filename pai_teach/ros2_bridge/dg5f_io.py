"""dg5f (5-finger hand, 20 DoF) ROS2 IO.

State:   /dg5f_<side>/joint_states  (~300 Hz, sensor_msgs/JointState)
Command: /dg5f_<side>/<controller>/reference  (control_msgs/MultiDOFCommand)

The production controller is a single multi-DOF `pid_controller/PidController`
(`rj_dg_pospid` for right, `lj_dg_pospid` for left). Reference is published
as `MultiDOFCommand{dof_names, values, values_dot}` at ~50 Hz. The
controller's command_interface is `effort` and `reference_and_state_interfaces`
is `[position]` — i.e. we publish position references and PID converts to
motor current internally.
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
        command_topic: str | None = None,
    ) -> None:
        self._node = node
        self._joint_names = list(joint_names)
        self._dof = len(joint_names)
        self._command_topic = command_topic

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

        self._cmd_pub = None
        self._MultiDOFCommand = None
        if command_topic is not None:
            # Lazy: control_msgs may not be installed on the dev box.
            from control_msgs.msg import MultiDOFCommand

            self._MultiDOFCommand = MultiDOFCommand
            self._cmd_pub = node.create_publisher(MultiDOFCommand, command_topic, 10)

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

    def send_joint_position(self, position: np.ndarray) -> None:
        """Publish one MultiDOFCommand frame with the given joint positions.

        The PidController consumes this as the reference; rate is up to the
        caller (production teleop is 50 Hz).
        """
        if self._cmd_pub is None:
            raise RuntimeError(
                "DG5FIO has no command_topic configured (record-only mode)"
            )
        if position.shape != (self._dof,):
            raise ValueError(
                f"position shape {position.shape} != expected ({self._dof},)"
            )
        msg = self._MultiDOFCommand()
        msg.dof_names = list(self._joint_names)
        msg.values = [float(x) for x in position]
        msg.values_dot = [0.0] * self._dof
        self._cmd_pub.publish(msg)

    def wait_for_state(self, timeout_s: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self.has_state():
                return True
            time.sleep(0.05)
        return False
