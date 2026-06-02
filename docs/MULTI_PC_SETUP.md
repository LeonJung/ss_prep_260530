# Multi-PC ROS2 setup

`pai_teach` runs across three machines:

```
┌─────────────────────┐   teleop, sensor pubs   ┌────────────────────┐
│  Controller PC      │ ────────────────────▶  │  Training PC       │
│  10.42.0.214        │      zenoh + ROS2       │  10.42.0.1         │
│  (UR10E teleop,     │     DOMAIN_ID = 15      │  (record_demo,     │
│   dg5f bringup,     │                         │   train_act,       │
│   realsense2)       │                         │   run_policy)      │
└──────────┬──────────┘                         └─────────┬──────────┘
           │                                              │
           │ RTDE / Modbus / USB                          │
           ▼                                              ▼
  UR10E + dg5f + RealSense                       GPU (RTX 5000-class)
```

The **Dev PC** (this repo's editor) only pushes code. It is not part of
the runtime ROS2 graph.

---

## One-time install

### Dev PC
Nothing required beyond git; pytest is optional for the 6 unit tests.

### Training PC (10.42.0.1)
```bash
sudo apt install docker.io nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
sudo usermod -aG docker "$USER"        # re-login after this

git clone git@github.com:LeonJung/ss_prep_260530.git ~/ai_ws
cd ~/ai_ws
docker build -t pai_teach:latest .     # ~15 min first time
```

Verify GPU inside the image:
```bash
docker run --rm --gpus all pai_teach:latest python3 -c \
    "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

### Controller PC (10.42.0.214)
`colcon_ws` (UR) and `hand_ws` (dg5f) are assumed already built. Add zenoh
+ the env:

```bash
sudo apt install ros-jazzy-rmw-zenoh-cpp

# Put in ~/.bashrc so every terminal inherits it
echo 'export RMW_IMPLEMENTATION=rmw_zenoh_cpp' >> ~/.bashrc
echo 'export ROS_DOMAIN_ID=15'                  >> ~/.bashrc
```

The training PC's image already bakes both env vars in.

---

## Per-session: what runs where

### Controller PC (10.42.0.214)

```bash
# Terminal 1 — zenoh router (leave running; restart if you reboot)
ros2 run rmw_zenoh_cpp rmw_zenohd

# Terminal 2 — UR10E teleop (pick ONE)
#   (a) UNILATERAL (current default — VIVE tracker → IK):
ros2 launch ur10e_teleop_unilateral_vive_cpp teleop_real.launch.py \
    follower_ip:=169.254.186.92
#   (b) BILATERAL (force-feedback, needs UR3e leader):
# ros2 launch ur10e_teleop_real_py teleop_real.launch.py \
#     leader_ip:=169.254.186.94 follower_ip:=169.254.186.92
#
# Both publish /ur10e/follower/joint_state + /ur10e/mode identically;
# pai_teach is agnostic to which is running.

# Terminal 3 — dg5f right hand  (SKIP while the hand is unplugged;
# pass --no-dg5f to pai_teach scripts instead, see below)
# ros2 launch dg5f_hand_bringup dg5f_right_bringup.launch.py \
#     delto_ip:=169.254.186.72

# Terminal 4 — RealSense, one per camera (or compose into a single launch)
ros2 launch realsense2_camera rs_launch.py \
    camera_name:=wrist_cam serial_no:='"<wrist serial>"'
ros2 launch realsense2_camera rs_launch.py \
    camera_name:=scene_cam serial_no:='"<scene serial>"'
```

### Training PC (10.42.0.1)

All commands run inside the docker image. The image auto-sets
`RMW_IMPLEMENTATION` + `ROS_DOMAIN_ID` and starts in `/workspace` (mounted
to the repo). ROS needs to be sourced once per shell because
`/etc/bash.bashrc` only fires for interactive shells.

```bash
cd ~/ai_ws

# Open an interactive shell in the image (ROS auto-sourced)
docker compose run --rm pai_teach

# inside the container:
ros2 topic list | grep -E "(ur10e|dg5f|cam)"        # discovery check
ros2 topic hz /ur10e/follower/joint_state           # expect ~50 Hz
ros2 topic hz /wrist_cam/color/image_raw            # expect ~30 Hz

python -m scripts.record_demo --no-dg5f \
    --repo-id leonjung/pai_teach_demos \
    --root datasets/pai_teach_demos \
    --task pick_and_place --max-seconds 30

python -m scripts.train_act \
    --root datasets/pai_teach_demos \
    --repo-id leonjung/pai_teach_demos \
    --batch-size 32                                 # bump on RTX 5000

python -m scripts.run_policy --no-dg5f \
    --checkpoint checkpoints/act_run/final --max-seconds 30
```

Or one-shot per command (auto-sources ROS inside `bash -c`):
```bash
docker compose run --rm pai_teach bash -c \
    'source /opt/ros/jazzy/setup.bash && \
     python -m scripts.record_demo --no-dg5f \
        --repo-id leonjung/pai_teach_demos \
        --root datasets/pai_teach_demos \
        --task pick_and_place --max-seconds 30'
```

### Dev PC (this repo's editor)
```bash
python -m pytest tests/    # 6 unit tests, no rclpy / torch / lerobot needed
```

---

## `--dg5f` / `--no-dg5f`

`mock_robot_publisher`, `record_demo`, and `run_policy` all accept
`--dg5f` / `--no-dg5f` (BooleanOptionalAction). It overrides
`config.dg5f.enabled` in `robot.yaml`.

| flag | effect |
|------|--------|
| (omit) | use `robot.yaml`'s `dg5f.enabled` (default `true`) |
| `--dg5f` | force enabled (require dg5f topic; 26-dim state/action) |
| `--no-dg5f` | force disabled (skip dg5f topic + publisher; **6-dim** state/action) |

**Important**: the flag MUST match how the checkpoint was trained.
`record_demo --no-dg5f` produces a 6-dim dataset → `train_act` produces a
6-dim policy → `run_policy --no-dg5f` is the only valid deploy. Mixing
trains a 26-dim policy that crashes on a 6-dim observation.

While the dg5f hardware is unplugged, use `--no-dg5f` everywhere.

---

## Hardware IPs

| Device                 | IP                 | Source                                  |
|------------------------|--------------------|-----------------------------------------|
| UR10E (follower)       | `169.254.186.92`   | `ur10e_teleop_control_ff_cpp` launches  |
| UR3e (leader)          | `169.254.186.94`   | same                                    |
| dg5f right (delto)     | `169.254.186.72`   | `dg5f_hand_bringup` launch default      |
| dg5f left (delto)      | `169.254.186.73`   | `dg5f_moveit_config` launch (at vendor) |

All robots are on the `169.254.186.0/24` link-local subnet, reached from
the controller PC over a wired NIC. The training PC does NOT talk
directly to the robots — only via the controller PC's ROS2 graph over the
`10.42.0.0/24` network.

---

## Network checklist (when discovery breaks)

1. `RMW_IMPLEMENTATION` and `ROS_DOMAIN_ID` set on **every** terminal that
   runs a ROS2 binary, **before** `ros2` / `python -m scripts.X`. (The
   docker image bakes them in; controller PC needs them in `~/.bashrc`.)
2. `rmw_zenohd` is running on the controller PC.
3. Firewall: zenoh router default port is **TCP 7447** — open it between
   the two PCs.
4. `ros2 daemon stop` (and `ros2 daemon start`) after changing
   `RMW_IMPLEMENTATION` — the daemon caches the discovery middleware.
5. If `topic list` works but `topic echo` hangs, it's usually a QoS
   mismatch, not a transport problem.
