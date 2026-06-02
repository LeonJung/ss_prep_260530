#!/usr/bin/env bash
# Print everything needed to figure out why `import rclpy` works one way and
# breaks another. Run inside the docker container.
source /opt/ros/jazzy/setup.bash

echo "=== env ==="
echo "PATH=$PATH"
echo
echo "PYTHONPATH=$PYTHONPATH"
echo
echo "which python:  $(which python)"
echo "which python3: $(which python3)"
python --version
python3 --version

echo
echo "=== sys.path under venv python ==="
python -c "import sys; [print('  ', p) for p in sys.path]"

echo
echo "=== import rclpy via python ==="
python -c "import rclpy; print('OK:', rclpy.__file__)" 2>&1

echo
echo "=== import rclpy via python3 ==="
python3 -c "import rclpy; print('OK:', rclpy.__file__)" 2>&1

echo
echo "=== record_demo --help ==="
python -m scripts.record_demo --help 2>&1 | head -15
