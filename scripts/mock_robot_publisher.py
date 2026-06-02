"""Mock teleop publisher — emulates the robot stacks on this PC.

Publishes the four topics record_demo subscribes to:
  /ur10e/follower/joint_state    (sensor_msgs/JointState, 50 Hz)
  /dg5f_right/joint_states       (sensor_msgs/JointState, 300 Hz)
  /wrist_cam/color/image_raw     (sensor_msgs/Image rgb8, 30 Hz)
  /scene_cam/color/image_raw     (sensor_msgs/Image rgb8, 30 Hz)

State is a slow sinusoid per joint (different freq/phase per channel) so
the recorder's lag-1 action target looks like motion rather than zeros.
Images are a moving gradient — non-zero variance so ACT's vision branch
sees something.

Run inside the docker container, ROS env sourced:
    python -m scripts.mock_robot_publisher --robot-config pai_teach/configs/robot.yaml

Stops on Ctrl-C.
"""

from __future__ import annotations

import argparse
import math
import time
from pathlib import Path

import numpy as np
import rclpy
import yaml
from rclpy.node import Node
from sensor_msgs.msg import Image, JointState


def _now_msg(node: Node):
    """builtin_interfaces/Time from rclpy clock."""
    t = node.get_clock().now().to_msg()
    return t


def _make_image(h: int, w: int, t: float) -> np.ndarray:
    """Moving diagonal gradient -> HxWx3 uint8 RGB."""
    yy, xx = np.meshgrid(np.arange(h, dtype=np.float32), np.arange(w, dtype=np.float32), indexing="ij")
    phase = (xx + yy + t * 60.0) / (h + w)
    r = (0.5 + 0.5 * np.sin(2 * math.pi * phase)) * 255
    g = (0.5 + 0.5 * np.sin(2 * math.pi * phase + 2.094)) * 255
    b = (0.5 + 0.5 * np.sin(2 * math.pi * phase + 4.189)) * 255
    return np.stack([r, g, b], axis=-1).astype(np.uint8)


class MockRobotPublisher(Node):
    def __init__(self, cfg: dict):
        super().__init__("mock_robot_publisher")
        self._t0 = time.monotonic()

        # UR10E follower state — publish on BOTH the teleop topic
        # (/ur10e/follower/joint_state, used during record) AND the deploy
        # topic (/joint_states, used during run_policy) so a single mock
        # process covers both record and deploy code paths.
        self._ur_names = list(cfg["ur10e"]["joint_names"])
        self._ur_pubs = [
            self.create_publisher(JointState, cfg["ur10e"]["state_topic_teleop"], 10),
            self.create_publisher(JointState, cfg["ur10e"]["state_topic_deploy"], 10),
        ]
        self.create_timer(1.0 / 50.0, self._tick_ur)

        # dg5f state — gated on config.dg5f.enabled
        self._hand_enabled = bool(cfg["dg5f"].get("enabled", True))
        if self._hand_enabled:
            self._hand_names = list(cfg["dg5f"]["joint_names"])
            self._hand_pub = self.create_publisher(
                JointState, cfg["dg5f"]["state_topic"], 30
            )
            self.create_timer(1.0 / 300.0, self._tick_hand)
        else:
            self._hand_names = []
            self._hand_pub = None

        # Cameras
        self._cam_pubs: list[tuple[str, int, int, "rclpy.publisher.Publisher"]] = []
        for cam in cfg.get("cameras", []):
            pub = self.create_publisher(Image, cam["topic"], 5)
            self._cam_pubs.append(
                (cam["name"], int(cam["height"]), int(cam["width"]), pub)
            )
        if self._cam_pubs:
            self.create_timer(1.0 / 30.0, self._tick_cams)

        self.get_logger().info(
            f"mock publisher up — UR={cfg['ur10e']['state_topic_teleop']}, "
            f"dg5f={'(off)' if not self._hand_enabled else cfg['dg5f']['state_topic']}, "
            f"cams={[c[0] for c in self._cam_pubs]}"
        )

    def _elapsed(self) -> float:
        return time.monotonic() - self._t0

    def _tick_ur(self) -> None:
        t = self._elapsed()
        msg = JointState()
        msg.header.stamp = _now_msg(self)
        msg.name = self._ur_names
        # Slow joint sinusoid, ~0.3 rad amplitude, different freq per joint
        msg.position = [
            0.3 * math.sin(2 * math.pi * (0.05 + 0.01 * i) * t + i)
            for i in range(len(self._ur_names))
        ]
        msg.velocity = [
            0.3 * 2 * math.pi * (0.05 + 0.01 * i)
            * math.cos(2 * math.pi * (0.05 + 0.01 * i) * t + i)
            for i in range(len(self._ur_names))
        ]
        msg.effort = [0.0] * len(self._ur_names)
        for pub in self._ur_pubs:
            pub.publish(msg)

    def _tick_hand(self) -> None:
        t = self._elapsed()
        msg = JointState()
        msg.header.stamp = _now_msg(self)
        msg.name = self._hand_names
        # Hand joints sweep [-0.3, 0.7]-ish, faster per finger
        msg.position = [
            0.5 + 0.4 * math.sin(2 * math.pi * (0.1 + 0.02 * i) * t + 0.5 * i)
            for i in range(len(self._hand_names))
        ]
        msg.velocity = [0.0] * len(self._hand_names)
        msg.effort = [0.0] * len(self._hand_names)  # mA proxy
        self._hand_pub.publish(msg)

    def _tick_cams(self) -> None:
        t = self._elapsed()
        for name, h, w, pub in self._cam_pubs:
            img = _make_image(h, w, t + hash(name) % 100 * 0.01)
            msg = Image()
            msg.header.stamp = _now_msg(self)
            msg.header.frame_id = name
            msg.height = h
            msg.width = w
            msg.encoding = "rgb8"
            msg.is_bigendian = 0
            msg.step = w * 3
            msg.data = img.tobytes()
            pub.publish(msg)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--robot-config",
        type=Path,
        default=Path("pai_teach/configs/robot.yaml"),
    )
    p.add_argument(
        "--dg5f",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="override config.dg5f.enabled (--no-dg5f to mock without the hand)",
    )
    args = p.parse_args()
    cfg = yaml.safe_load(args.robot_config.read_text())
    if args.dg5f is not None:
        cfg["dg5f"]["enabled"] = bool(args.dg5f)

    rclpy.init()
    node = MockRobotPublisher(cfg)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
