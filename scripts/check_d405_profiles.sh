#!/usr/bin/env bash
# Print every stream profile the connected D405s actually advertise.
# Useful when an `rgb_camera.color_profile:=...` arg is silently
# ignored by realsense2_camera (the camera doesn't support that combo
# → it falls back to default).
#
# Run NATIVELY on the NUC (no docker). librealsense2-utils provides
# rs-enumerate-devices.
echo "=== rs-enumerate-devices --compact ==="
rs-enumerate-devices --compact 2>&1 | head -40
echo
echo "=== rs-enumerate-devices (full stream modes for each device) ==="
rs-enumerate-devices 2>&1 | grep -E "Device|Stream|Color|Format|fps" | head -60
