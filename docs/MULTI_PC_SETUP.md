# Multi-PC setup (zenoh, two-PC)

Both PCs now run **Ubuntu 24.04 + ROS Jazzy**, so the `ros-jazzy-rmw-zenoh-cpp`
apt build is the same release on each side → wire-compatible. The training
PC subscribes to the controller PC's topics live; `record_demo`,
`train_act`, and `run_policy` all run on the training PC.

```
Controller NUC (24.04 + Jazzy, 10.42.0.214)         Training PC (24.04 + Jazzy, 10.42.0.1)
─────────────────────────────────                   ─────────────────────────────────
zenohd  (router, dials in to .1)                    zenohd  (router, listens on .1:7447)
ur10e_teleop_unilateral_vive (native)               docker compose run pai_teach
realsense2_camera × 2          (native)             ├─ record_demo  (subscribes via zenoh)
                                                    ├─ train_act    (uses GPU)
                                                    └─ run_policy   (publishes JTC / MultiDOFCommand)
```

The controller PC's router connects outward to the training PC
(`tcp/10.42.0.1:7447`) — that direction is what we found actually works
on the lab switch (multicast scout is filtered).

---

## One-time install

### Dev PC
Nothing beyond `git`. `python -m pytest tests/` runs with no ROS / torch / lerobot.

### Both PCs (controller NUC + training PC)
```bash
# Docker. Pick whichever doesn't conflict with what's installed.
sudo apt install docker.io                              # or docker-ce stack
sudo usermod -aG docker "$USER"                          # re-login

# nvidia-container-toolkit on the training PC (and on the NUC if you'll
# run run_policy there); record-only doesn't need GPU.
echo "deb [trusted=yes] https://nvidia.github.io/libnvidia-container/stable/deb/$(dpkg --print-architecture) /" | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update && sudo apt install nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

git clone git@github.com:LeonJung/ss_prep_260530.git ~/ai_ws
cd ~/ai_ws

# corporate MITM proxy? put the host CA bundle in; otherwise leave empty.
cp /etc/ssl/certs/ca-certificates.crt host-ca-bundle.crt   # or: touch host-ca-bundle.crt

docker compose build                                    # ~15 min first time
```

### zenoh + ROS env (both PCs, native shells)
```bash
echo 'export RMW_IMPLEMENTATION=rmw_zenoh_cpp' >> ~/.bashrc
echo 'export ROS_DOMAIN_ID=15'                  >> ~/.bashrc
```
(The docker image already exports both internally.)

---

## Per-session: what runs where

### Controller NUC (10.42.0.214)

```bash
# Terminal 1 — zenoh router, dialing OUT to the training PC.
bash scripts/start_zenohd_controller.sh
# (default upstream tcp/10.42.0.1:7447; override with TRAINING_ROUTER env)

# Terminal 2 — UR10E unilateral teleop
ros2 launch ur10e_teleop_unilateral_vive_cpp teleop_real.launch.py \
    follower_ip:=169.254.186.92

# Terminal 3 / 4 — RealSense D405. Drop the color profile to 424x240
# (D405 native option) so each frame is ~305 KB instead of 1.22 MB
# — keeps the recorder loop near 30 Hz over zenoh. ACT resizes to
# ~224x224 internally anyway.
ros2 launch realsense2_camera rs_launch.py \
    camera_name:=wrist_cam serial_no:='"218622270770"' \
    rgb_camera.color_profile:=424x240x30
ros2 launch realsense2_camera rs_launch.py \
    camera_name:=scene_cam serial_no:='"218622277871"' \
    rgb_camera.color_profile:=424x240x30
```

### Training PC (10.42.0.1)

```bash
cd ~/ai_ws

# zenohd inside docker, listening on host:7447 — controller dials in.
docker compose up -d zenohd
docker compose logs zenohd | tail -5      # confirm "Zenoh can be reached at: tcp/...:7447"

# Discovery sanity:
docker compose run --rm pai_teach bash -c \
    'source /opt/ros/jazzy/setup.bash && ros2 topic list | grep -E "ur10e|cam"'
# Expect: /ur10e/right/follower/joint_state, /camera/wrist_cam/color/image_raw, /camera/scene_cam/color/image_raw

# Record an episode (dg5f currently unplugged → --no-dg5f).
docker compose run --rm pai_teach bash -c \
    'source /opt/ros/jazzy/setup.bash && python -m scripts.record_demo --no-dg5f \
     --repo-id local/<task> --root datasets/<task> --task <task> --max-seconds 30'

# Train.
docker compose run --rm pai_teach bash -c \
    'source /opt/ros/jazzy/setup.bash && python -m scripts.train_act \
     --root datasets/<task> --repo-id local/<task> --batch-size 32'

# Deploy on the real robot (teleop MUST be off — same controllers).
docker compose run --rm pai_teach bash -c \
    'source /opt/ros/jazzy/setup.bash && python -m scripts.run_policy --no-dg5f \
     --checkpoint checkpoints/act_run/final --max-seconds 30'
```

---

## `--dg5f` / `--no-dg5f`

`record_demo` and `run_policy` accept `--dg5f` / `--no-dg5f` overriding
`config.dg5f.enabled` in `robot.yaml`. The flag must match how the
checkpoint was trained: a 6-dim policy can't deploy on a 26-dim
observation and vice versa. While dg5f is unplugged, use `--no-dg5f` on
both record and deploy.

---

## Hardware reference

| Device                 | IP / Serial         | Notes                                   |
|------------------------|---------------------|-----------------------------------------|
| UR10E (follower)       | `169.254.186.92`    | wired NIC on the NUC                    |
| UR3e (leader, opt)     | `169.254.186.94`    | only when bilateral teleop is on        |
| dg5f right (delto)     | `169.254.186.72`    | currently unplugged                     |
| dg5f left (delto)      | `169.254.186.73`    | at vendor for repair                    |
| RealSense D405 (wrist) | serial `218622270770` |                                       |
| RealSense D405 (scene) | serial `218622277871` |                                       |

---

## Discovery / wire-protocol troubleshooting

- `ros2 topic list` empty in the training-PC container → zenoh isn't routing.
  - Check `docker compose logs zenohd | tail` — last line should be
    `Zenoh can be reached at: tcp/0.0.0.0:7447`.
  - On the NUC, confirm the controller-side zenohd is dialing in: its
    terminal output should show a session opened to `10.42.0.1:7447`.
- `ros2 topic list` works but `record_demo` times out on `cameras` /
  `ur10e` → QoS mismatch. We already use SENSOR_DATA (BEST_EFFORT) on
  the UR10E + camera subscribers
  (`pai_teach/ros2_bridge/{ur10e,dg5f,camera}_io.py`).
- `Failed to create POSIX SHM provider` on rclpy.init → POSIX SHM
  transport disabled in `zenoh_session_config.json5` and
  `scripts/start_zenohd_controller.sh` already; verify those files are
  what's actually being loaded.
