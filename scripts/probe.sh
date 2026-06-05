#!/usr/bin/env bash
# Run the direct-rclpy probe (scripts/probe_subscribe.py). Bypasses the
# `ros2 topic echo` zenoh-init bug that prints `!rclpy.ok()` and never
# delivers a message. Subscribes to each robot.yaml topic with both
# SENSOR_DATA and RELIABLE QoS and prints first message details
# (joint count, image height/width/encoding).
#
# Usage:  docker compose run --rm pai_teach bash scripts/probe.sh
source /opt/ros/${ROS_DISTRO:-jazzy}/setup.bash
exec python -m scripts.probe_subscribe
