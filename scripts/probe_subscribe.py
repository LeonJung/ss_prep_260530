"""Direct rclpy subscribe probe — bypasses ros2 daemon / cli.

Spins for ~5 s per attempt and prints first message received (or NO
MESSAGE) per topic in robot.yaml. Tries BOTH default RELIABLE and
SENSOR_DATA QoS so we can see which one the publisher actually matches.

    docker compose run --rm pai_teach bash -c \\
        'source /opt/ros/jazzy/setup.bash && python -m scripts.probe_subscribe'
"""

from __future__ import annotations

import time
from pathlib import Path

import rclpy
import yaml
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, qos_profile_sensor_data
from sensor_msgs.msg import Image, JointState

CFG_PATH = Path(__file__).parent.parent / "pai_teach" / "configs" / "robot.yaml"


def probe(node: Node, topic: str, msg_type, qos, label: str, wait_s: float = 5.0):
    got: list = []

    def cb(msg):
        if not got:
            got.append(msg)

    sub = node.create_subscription(msg_type, topic, cb, qos)
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline and not got:
        rclpy.spin_once(node, timeout_sec=0.1)
    node.destroy_subscription(sub)

    if not got:
        print(f"  [{label:>11s}] NO MESSAGE after {wait_s:.0f}s")
        return None
    m = got[0]
    if isinstance(m, JointState):
        print(f"  [{label:>11s}] OK  {len(m.name)} joints, first 3 = {list(m.name)[:3]}")
    elif isinstance(m, Image):
        print(f"  [{label:>11s}] OK  {m.height}x{m.width} encoding={m.encoding}")
    else:
        print(f"  [{label:>11s}] OK  type={type(m).__name__}")
    return m


def main():
    cfg = yaml.safe_load(CFG_PATH.read_text())
    reliable = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)
    rclpy.init()
    node = Node("pai_teach_probe")

    topic = cfg["ur10e"]["state_topic_teleop"]
    print(f"=== {topic} (JointState) ===")
    probe(node, topic, JointState, qos_profile_sensor_data, "SENSOR_DATA")
    probe(node, topic, JointState, reliable, "RELIABLE")

    for cam in cfg.get("cameras", []):
        print(f"=== {cam['topic']} (Image) ===")
        probe(node, cam["topic"], Image, qos_profile_sensor_data, "SENSOR_DATA")
        probe(node, cam["topic"], Image, reliable, "RELIABLE")

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
