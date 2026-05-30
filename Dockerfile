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
      ros-jazzy-cv-bridge \
      ros-jazzy-control-msgs \
      ros-jazzy-trajectory-msgs \
      ros-jazzy-sensor-msgs-py \
      ros-jazzy-rmw-zenoh-cpp \
      python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*

# --- Python deps -----------------------------------------------------------
# PyTorch wheel embeds its own CUDA runtime; only the host NVIDIA driver
# matters (nvidia-container-toolkit injects it). cu124 wheel supports
# everything from RTX 2080 (sm_75) up to RTX 5000-class (sm_89).
RUN python3 -m pip install --no-cache-dir --break-system-packages \
      --index-url https://download.pytorch.org/whl/cu124 \
      torch==2.5.1 torchvision==0.20.1

RUN python3 -m pip install --no-cache-dir --break-system-packages \
      numpy \
      pyyaml \
      opencv-python-headless \
      tqdm \
      hydra-core \
      omegaconf \
      "lerobot @ git+https://github.com/huggingface/lerobot.git"

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
