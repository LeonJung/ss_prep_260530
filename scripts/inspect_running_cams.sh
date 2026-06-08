#!/usr/bin/env bash
# Run AFTER start_cams.sh is up. Shows:
#  1) what color/rgb-related parameters the running realsense node
#     actually exposes (so we can use the exact name our build understands)
#  2) rs-enumerate-devices stream modes per connected D405 (so we know
#     which color resolutions the hardware itself supports)
#
# Run NATIVELY on the NUC.
source /opt/ros/${ROS_DISTRO:-jazzy}/setup.bash

echo "=== running cam node names ==="
ros2 node list 2>&1 | grep -i cam

NODE="$(ros2 node list 2>&1 | grep -i cam | head -1)"
if [ -n "$NODE" ]; then
    echo
    echo "=== params on $NODE matching color/rgb/profile ==="
    ros2 param list "$NODE" 2>&1 | grep -iE "color|rgb|profile" | head -30
    echo
    echo "=== current values of those params ==="
    for p in $(ros2 param list "$NODE" 2>&1 | grep -iE "color|rgb|profile" | head -10); do
        printf "  %-45s = " "$p"
        ros2 param get "$NODE" "$p" 2>&1 | tail -1
    done
fi

echo
echo "=== rs-enumerate-devices: every stream mode each D405 advertises ==="
rs-enumerate-devices 2>&1 | grep -E "Device|Stream|^ +(Color|Depth|Infrared)" | head -80
