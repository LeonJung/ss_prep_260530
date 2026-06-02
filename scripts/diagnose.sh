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

echo
echo "=== installed torch / nvidia / lerobot wheels ==="
pip list 2>/dev/null | grep -iE "torch|nvidia|lerobot" || true

echo
echo "=== torch + cuda + npp probe ==="
python -c "
import ctypes, glob
try:
    import torch
    print('torch:', torch.__version__, 'cuda avail:', torch.cuda.is_available())
    if torch.cuda.is_available():
        print('gpu:', torch.cuda.get_device_name(0))
except Exception as e:
    print('torch FAIL:', e)

# Find libnppicc on disk
hits = glob.glob('/opt/venv/lib/**/libnppicc*', recursive=True) + \
       glob.glob('/usr/**/libnppicc*', recursive=True)
print('libnppicc found at:', hits or '(none)')

# Try loading torchcodec
try:
    import torchcodec
    print('torchcodec:', torchcodec.__version__)
except Exception as e:
    print('torchcodec FAIL:', e)
"

echo
echo "=== ffmpeg / libav versions ==="
ffmpeg -version 2>&1 | head -3
ldconfig -p 2>/dev/null | grep -E "libavutil|libavcodec" | head -5
