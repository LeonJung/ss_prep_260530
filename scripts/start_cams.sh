#!/usr/bin/env bash
# Run on the NUC (native, ROS humble/jazzy sourced). Brings up both D405
# cameras with USB-friendly settings:
#   - 424x240 RGB at 30 Hz (not the default 848x480 → 1.22 MB/frame)
#   - depth + IR streams off (we only consume color for ACT)
# Together these drop per-camera bandwidth from ~36 MB/s to ~9 MB/s,
# which removes the "no frames 5 sec" cutouts we saw when both D405s
# saturated the NUC's USB controller.
#
# Both launches stay in the foreground via `wait`; Ctrl-C kills both.
set -e
source /opt/ros/${ROS_DISTRO:-jazzy}/setup.bash

WRIST_SERIAL="${WRIST_SERIAL:-218622270770}"
SCENE_SERIAL="${SCENE_SERIAL:-218622277871}"

ros2 launch realsense2_camera rs_launch.py \
    camera_name:=wrist_cam serial_no:="\"${WRIST_SERIAL}\"" \
    rgb_camera.color_profile:=424x240x30 \
    enable_depth:=false enable_infra1:=false enable_infra2:=false &
WRIST=$!
sleep 2

ros2 launch realsense2_camera rs_launch.py \
    camera_name:=scene_cam serial_no:="\"${SCENE_SERIAL}\"" \
    rgb_camera.color_profile:=424x240x30 \
    enable_depth:=false enable_infra1:=false enable_infra2:=false &
SCENE=$!

trap "kill $WRIST $SCENE 2>/dev/null || true" EXIT
echo "Cameras up (wrist PID=$WRIST, scene PID=$SCENE). Ctrl-C to stop."
wait
