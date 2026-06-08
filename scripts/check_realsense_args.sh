#!/usr/bin/env bash
# Identify the actual realsense2_camera package + launch arg names on
# the NUC. Different package versions expose different arg names
# (enable_depth vs depth_module.enable, etc.) and different launch
# files. Output here tells us exactly what option strings work.
#
# Run NATIVELY on the NUC (no docker), with ROS sourced:
#   bash scripts/check_realsense_args.sh
source /opt/ros/${ROS_DISTRO:-jazzy}/setup.bash

echo "=== package version ==="
apt show ros-${ROS_DISTRO}-realsense2-camera 2>/dev/null | grep -E "^(Package|Version):" || true
echo
echo "=== package + launch files ==="
ros2 pkg prefix realsense2_camera 2>&1
ros2 pkg executables realsense2_camera 2>&1 | head
find $(ros2 pkg prefix realsense2_camera 2>/dev/null)/share/realsense2_camera/launch -name "*.py" 2>/dev/null
echo
echo "=== launch args (rs_launch.py) ==="
ros2 launch realsense2_camera rs_launch.py --show-args 2>&1 | head -120
