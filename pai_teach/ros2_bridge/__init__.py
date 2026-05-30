"""ROS2 -> Python adapters. Single-node host; rest of the package is rclpy-free."""

from .types import Action, Observation, RobotState

# RobotIO imports rclpy lazily-but-eagerly; keep it out of the top-level export
# so types.py can be imported without ROS installed (e.g. on the analysis box).
__all__ = ["Action", "Observation", "RobotState"]
