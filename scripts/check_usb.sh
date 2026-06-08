#!/usr/bin/env bash
# Show the USB device tree on the NUC so we can see whether both D405s
# sit under the same root hub (= same controller, saturation likely)
# or different ones (= independent throughput, OK).
#
# Run NATIVELY on the NUC.

echo "=== lsusb -t (tree view) ==="
lsusb -t

echo
echo "=== Intel RealSense devices ==="
lsusb | grep -i "intel\|realsense"

echo
echo "=== suggestion ==="
echo "Both D405s should be under DIFFERENT 'Bus' lines in lsusb -t."
echo "If they're under the same Bus, move one to a USB-C port (if you're"
echo "currently in USB-A) or a different USB-A side of the chassis."
