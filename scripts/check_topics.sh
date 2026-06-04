#!/usr/bin/env bash
# Show what the recorder will actually see for each robot.yaml topic.
# Run inside the docker container after the controller PC stacks are up:
#   docker compose run --rm pai_teach bash scripts/check_topics.sh
source /opt/ros/jazzy/setup.bash

echo "=== ros2 topic list (ur10e / dg5f / cam) ==="
ros2 topic list 2>&1 | grep -E "ur10e|dg5f|cam" || echo "(nothing matched)"

for topic in /ur10e/right/follower/joint_state \
             /camera/wrist_cam/color/image_raw \
             /camera/scene_cam/color/image_raw ; do
    echo
    echo "=== echo $topic (3 s) ==="
    timeout 3 ros2 topic echo --once --no-arr "$topic" 2>&1 | head -12
done

echo
echo "=== topic info (publisher QoS) ==="
ros2 topic info /ur10e/right/follower/joint_state --verbose 2>&1 | head -12
echo
ros2 topic info /camera/wrist_cam/color/image_raw --verbose 2>&1 | head -12
