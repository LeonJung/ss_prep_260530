#!/usr/bin/env bash
# Print live publish rate + bandwidth for the topics record_demo consumes.
# Tells us whether a slow record_demo (low frame count per second) is
# caused by the camera publisher itself, zenoh transport dropping frames,
# or our recorder being slow on the data flush side.
#
# Usage:  docker compose run --rm pai_teach bash scripts/check_rates.sh
source /opt/ros/${ROS_DISTRO:-jazzy}/setup.bash

echo "=== camera rate / bw (wrist_cam, 10s each) ==="
echo "-- hz --"
timeout 10 ros2 topic hz /camera/wrist_cam/color/image_raw 2>&1 | tail -5
echo "-- bw --"
timeout 5 ros2 topic bw /camera/wrist_cam/color/image_raw 2>&1 | tail -3

echo
echo "=== camera rate / bw (scene_cam, 10s each) ==="
echo "-- hz --"
timeout 10 ros2 topic hz /camera/scene_cam/color/image_raw 2>&1 | tail -5
echo "-- bw --"
timeout 5 ros2 topic bw /camera/scene_cam/color/image_raw 2>&1 | tail -3

echo
echo "=== ur10e rate (5s) ==="
timeout 5 ros2 topic hz /ur10e/right/follower/joint_state 2>&1 | tail -3
