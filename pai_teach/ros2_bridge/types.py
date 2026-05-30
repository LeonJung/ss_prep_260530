"""ROS-free data types shared by ros2_bridge, data_recorder, and policy/runner.

Importing this module must NOT pull in rclpy — the data_recorder needs to
construct these objects when replaying datasets without a live ROS graph.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class RobotState:
    """One synchronous snapshot of robot proprioception."""

    ur10e_position: np.ndarray            # shape (6,), rad
    ur10e_velocity: np.ndarray            # shape (6,), rad/s
    dg5f_position: np.ndarray             # shape (20,), rad
    dg5f_velocity: np.ndarray             # shape (20,), rad/s
    dg5f_effort: np.ndarray               # shape (20,), motor current proxy
    # Monotonic timestamps (seconds) of the most-recent source messages.
    # Useful for the recorder to detect staleness.
    ur10e_stamp: float = 0.0
    dg5f_stamp: float = 0.0


@dataclass
class Observation:
    """What the policy sees at one timestep."""

    state: RobotState
    # Camera name -> HxWx3 uint8 RGB image.
    images: dict[str, np.ndarray] = field(default_factory=dict)
    stamp: float = 0.0                    # recorder loop wall time


@dataclass
class Action:
    """What the policy emits. Joint-position targets for both robots."""

    ur10e_position: np.ndarray            # shape (6,), rad
    dg5f_position: np.ndarray             # shape (20,), rad
