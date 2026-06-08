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

# D405 native color profiles: 1280x720, 848x480, 640x480, 480x270 @ 5/15/30
# fps. 424x240 was wrong → realsense silently fell back to its default
# 848x480, which is what we saw in the 'open profile stream' log line.
# 480x270 is the smallest D405 supports.
ros2 launch realsense2_camera rs_launch.py \
    camera_name:=wrist_cam serial_no:="\"${WRIST_SERIAL}\"" \
    rgb_camera.color_profile:=480x270x30 \
    enable_depth:=false enable_infra1:=false enable_infra2:=false &
WRIST=$!
sleep 2

ros2 launch realsense2_camera rs_launch.py \
    camera_name:=scene_cam serial_no:="\"${SCENE_SERIAL}\"" \
    rgb_camera.color_profile:=480x270x30 \
    enable_depth:=false enable_infra1:=false enable_infra2:=false &
SCENE=$!

trap "kill $WRIST $SCENE 2>/dev/null || true" EXIT
echo "Cameras up (wrist PID=$WRIST, scene PID=$SCENE). Ctrl-C to stop."
wait
