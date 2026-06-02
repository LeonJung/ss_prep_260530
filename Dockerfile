# pai_teach runtime image: ROS2 Jazzy + PyTorch + LeRobot (ACT).
#
# Single image used by:
#   - Dev/sanity (this PC, RTX 2080)
#   - Training PC (RTX 5000-class)
# for record_demo / train_act / run_policy.
#
# GPU access requires nvidia-container-toolkit on the host and
# `docker run --gpus all` (or `gpus: all` in compose).
#
# Build:   docker build -t pai_teach:latest .
# Run:     docker compose run --rm pai_teach bash
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Seoul \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# --- Host CA bundle (for environments behind an HTTPS-intercepting proxy) --
# Trust the host's CA bundle before any HTTPS fetch (ROS keyring + pip).
# On networks without a MITM proxy, leave host-ca-bundle.crt empty:
#     touch host-ca-bundle.crt
# update-ca-certificates is a no-op for an empty input, so the build still
# works. ca-certificates must be installed first so the command exists; that
# first apt-get update uses http://archive.ubuntu.com so no trust needed.
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY host-ca-bundle.crt /usr/local/share/ca-certificates/host-ca-bundle.crt
RUN update-ca-certificates
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# --- ROS2 Jazzy + system deps ----------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl gnupg lsb-release ca-certificates locales software-properties-common \
      git build-essential pkg-config \
      python3 python3-pip python3-dev \
    && locale-gen en_US.UTF-8 \
    && add-apt-repository universe \
    && curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
        -o /usr/share/keyrings/ros-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
        http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" \
        > /etc/apt/sources.list.d/ros2.list \
    && apt-get update && apt-get install -y --no-install-recommends \
      ros-jazzy-ros-base \
      ros-jazzy-control-msgs \
      ros-jazzy-trajectory-msgs \
      ros-jazzy-sensor-msgs-py \
      ros-jazzy-rmw-zenoh-cpp \
      python3-venv \
      ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# --- Isolated Python venv (sees ROS system site-packages for rclpy) --------
# Using a venv side-steps PEP 668 / Debian-managed package conflicts (e.g.
# `packaging` not having a RECORD file) that --break-system-packages cannot
# work around.
RUN python3 -m venv --system-site-packages /opt/venv
ENV PATH="/opt/venv/bin:${PATH}" \
    VIRTUAL_ENV="/opt/venv"
RUN /opt/venv/bin/pip install --no-cache-dir --upgrade pip wheel setuptools

# --- Python deps (into the venv) -------------------------------------------
# lerobot 0.5+ requires numpy>=2.0, but ROS jazzy was built against numpy 1.x
# — we keep numpy 2.x and skip the one ROS C-extension that can't tolerate
# that (cv_bridge.boost). Image decode is done in pai_teach via
# np.frombuffer instead.
#
# Torch is pinned to a CUDA 12.8 wheel so the lowest-common-denominator
# host driver across our PCs (training PC = 570.x, which supports up to
# CUDA 12.8) is enough. The default cu130 wheel pip would otherwise pick
# requires driver 580+ and fails with "the NVIDIA driver on your system
# is too old". Installed BEFORE lerobot so its resolver sees torch already
# satisfied and doesn't try to upgrade us back to cu130.
# torch + torchvision + torchcodec from cu128 index, with --extra-index-url
# so PyPI stays default. Some PyTorch wheels declare the nvidia-* runtime
# wheels (nvidia-npp-cu12 etc.) only weakly, and pip's resolver skips them
# under `--index-url` alone or with certain extras combinations — so we
# pin them explicitly. This is what makes `libnppicc.so.12` (used by
# torchvision/torchcodec NPP image ops) actually land in the image.
RUN pip install --no-cache-dir \
      --extra-index-url https://download.pytorch.org/whl/cu128 \
      "torch==2.8.0" "torchvision==0.23.0" "torchcodec==0.5.0" \
      "nvidia-cublas-cu12" \
      "nvidia-cuda-cupti-cu12" \
      "nvidia-cuda-nvrtc-cu12" \
      "nvidia-cuda-runtime-cu12" \
      "nvidia-cudnn-cu12" \
      "nvidia-cufft-cu12" \
      "nvidia-curand-cu12" \
      "nvidia-cusolver-cu12" \
      "nvidia-cusparse-cu12" \
      "nvidia-nccl-cu12" \
      "nvidia-nvjitlink-cu12" \
      "nvidia-nvtx-cu12" \
      "nvidia-npp-cu12"

# Register every pip-installed nvidia-*/lib directory with the system
# dynamic linker. torch itself rewires its dlopen path at `import torch`
# time, but torchcodec loads its native libraries via libc dlopen which
# consults /etc/ld.so.cache — without this, `libnppicc.so.12 cannot open
# shared object file` even though the .so is sitting in venv.
RUN find /opt/venv/lib/python3.12/site-packages/nvidia \
        -mindepth 2 -maxdepth 3 -type d -name lib \
        > /etc/ld.so.conf.d/zzz-nvidia-pip.conf && \
    ldconfig && \
    echo "=== ldconfig sees ===" && \
    ldconfig -p | grep -E "libnppicc|libcudart|libcublas" | head -3

RUN pip install --no-cache-dir \
      pyyaml \
      opencv-python-headless \
      tqdm \
      hydra-core \
      omegaconf \
      "lerobot[dataset] @ git+https://github.com/huggingface/lerobot.git"

# --- ROS2 env auto-source for interactive shells ---------------------------
RUN echo "source /opt/ros/jazzy/setup.bash" >> /etc/bash.bashrc \
    && echo "export RMW_IMPLEMENTATION=rmw_zenoh_cpp" >> /etc/bash.bashrc \
    && echo "export ROS_DOMAIN_ID=15" >> /etc/bash.bashrc \
    && echo "export PYTHONPATH=/workspace:\$PYTHONPATH" >> /etc/bash.bashrc

WORKDIR /workspace
ENV PYTHONPATH=/workspace \
    RMW_IMPLEMENTATION=rmw_zenoh_cpp \
    ROS_DOMAIN_ID=15

# Default to a login bash so /etc/bash.bashrc fires (ROS sourcing).
CMD ["bash"]
