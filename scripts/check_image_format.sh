#!/usr/bin/env bash
# Inspect what message type / resolution / encoding the camera topics
# actually publish. ros2 topic bw showed 1.22 MB/s for /camera/wrist_cam,
# which is way below the 27.6 MB/s expected for raw 640x480 RGB at 30 Hz
# — figure out whether the publisher is small, compressed, or zenoh is
# dropping frames.
#
# Usage:  docker compose run --rm pai_teach bash scripts/check_image_format.sh
source /opt/ros/${ROS_DISTRO:-jazzy}/setup.bash

for topic in /camera/wrist_cam/color/image_raw \
             /camera/scene_cam/color/image_raw ; do
    echo "=== $topic ==="
    echo "-- type --"
    ros2 topic type "$topic" 2>&1 | head -2
    echo "-- header / width / height / encoding (one message, no pixel data) --"
    timeout 5 ros2 topic echo --once --no-arr "$topic" 2>&1 | head -15
    echo
done

echo "=== other camera topics (compressed?) ==="
ros2 topic list 2>&1 | grep -E "/camera/.*image" || true
