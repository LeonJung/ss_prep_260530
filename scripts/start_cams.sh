#!/usr/bin/env bash
# Launch both D405 cameras on the NUC via our direct-Node launch file
# (launch/d405_color_only.launch.py). Color only @ 480x270x30 so the
# NUC's USB controller doesn't drop frames.
#
# Run NATIVELY on the NUC (no docker), ROS sourced via ~/.bashrc:
#   bash scripts/start_cams.sh
set -e
source /opt/ros/${ROS_DISTRO:-jazzy}/setup.bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCH_FILE="$(dirname "$SCRIPT_DIR")/launch/d405_color_only.launch.py"

if [ ! -f "$LAUNCH_FILE" ]; then
    echo "launch file not found: $LAUNCH_FILE" >&2
    exit 1
fi

# CAMS env: both (default) | wrist | scene — use single-camera to test
# whether USB controller saturation is the cause of the 5-sec frame
# cutouts:
#   CAMS=wrist bash scripts/start_cams.sh
exec ros2 launch "$LAUNCH_FILE" cams:="${CAMS:-both}"
