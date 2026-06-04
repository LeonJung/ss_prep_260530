# Multi-PC setup (no inter-PC ROS comms)

We tried zenoh-over-DDS and zenoh native to bridge ROS Humble (controller
PC) ↔ ROS Jazzy (training PC) and hit wire-protocol mismatches at every
release boundary. Pivoted to a simpler architecture: **no live ROS link
between the two PCs at all**. Instead, run the recorder/runner on the
controller PC (same ROS distro as the teleop nodes, same host so DDS
multicast trivially works) and ship datasets / checkpoints between PCs
with rsync.

```
Dev PC                Controller NUC (Humble, 10.42.0.214)         Training PC (Jazzy, 10.42.0.1)
──────                ────────────────────────────────────         ──────────────────────────────
edit + push  ──git──▶ pai_teach_ctrl docker image                  pai_teach docker image
                      ├─ teleop_unilateral_vive (host)             └─ train_act, GPU
                      ├─ dg5f_bringup       (host, off for now)
                      ├─ realsense2_camera  (host)
                      └─ record_demo / run_policy (in container,
                         talks DDS to the host's ROS nodes)

                                datasets/   ───── rsync ─────▶  datasets/
                                checkpoints/ ◀──── rsync ─────  checkpoints/
```

No zenoh, no fastdds discovery-server, no MITM bridge. Same-host DDS
between the recorder container and the teleop process is rock solid; the
PCs only exchange parquet/mp4 files and ckpt directories over SSH.

---

## One-time install

### Dev PC
Nothing beyond `git`. Tests `python -m pytest tests/` run with no ROS / torch / lerobot.

### Controller NUC (10.42.0.214, Ubuntu 22.04 + ROS Humble)
```bash
# Docker. nvidia-container-toolkit optional — only needed if you'll run
# run_policy on the NUC's RTX 2060.
sudo apt install docker.io   # or docker-ce per your existing setup
sudo usermod -aG docker "$USER"   # re-login

git clone git@github.com:LeonJung/ss_prep_260530.git ~/ai_ws
cd ~/ai_ws

# corporate MITM proxy? put the host CA bundle in; otherwise leave empty.
cp /etc/ssl/certs/ca-certificates.crt host-ca-bundle.crt   # or: touch host-ca-bundle.crt

docker compose -f docker-compose.controller.yml build      # ~15 min first time
```

### Training PC (10.42.0.1, Ubuntu 24.04 + ROS Jazzy)
```bash
sudo apt install docker.io nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
sudo usermod -aG docker "$USER"   # re-login

git clone git@github.com:LeonJung/ss_prep_260530.git ~/ai_ws
cd ~/ai_ws
cp /etc/ssl/certs/ca-certificates.crt host-ca-bundle.crt   # MITM env

docker compose build pai_teach                              # the jazzy/GPU image
```

### SSH key (one-time)
From the training PC, copy your SSH key to the controller NUC so the
sync scripts can rsync without password:
```bash
ssh-copy-id leon@10.42.0.214
```

---

## Per-session: what runs where

### Controller NUC

```bash
# Terminals 1-3 native (no docker): teleop + cameras.
ros2 launch ur10e_teleop_unilateral_vive_cpp teleop_real.launch.py \
    follower_ip:=169.254.186.92
ros2 launch realsense2_camera rs_launch.py \
    camera_name:=wrist_cam serial_no:='"218622270770"'
ros2 launch realsense2_camera rs_launch.py \
    camera_name:=scene_cam serial_no:='"218622277871"'

# Terminal 4: record_demo inside the controller-side container.
# Same host = same DDS multicast domain as the native teleop nodes.
cd ~/ai_ws
docker compose -f docker-compose.controller.yml run --rm pai_teach_ctrl bash -c \
    'source /opt/ros/humble/setup.bash && python -m scripts.record_demo --no-dg5f \
     --repo-id local/<task> --root datasets/<task> \
     --task <task> --max-seconds 30'
```

### Training PC

```bash
cd ~/ai_ws

# 1) Pull the freshly-recorded dataset(s) from the NUC.
scripts/sync_datasets.sh

# 2) Train.
docker compose run --rm pai_teach bash -c \
    'source /opt/ros/jazzy/setup.bash && python -m scripts.train_act \
     --root datasets/<task> --repo-id local/<task> --batch-size 32'

# 3) Push the trained checkpoint back to the NUC.
scripts/sync_checkpoints.sh checkpoints/act_run/final/
```

### Controller NUC (deploy)

```bash
# Same record_demo container, but run_policy this time.
docker compose -f docker-compose.controller.yml run --rm pai_teach_ctrl bash -c \
    'source /opt/ros/humble/setup.bash && python -m scripts.run_policy --no-dg5f \
     --checkpoint checkpoints/act_run/final --max-seconds 30'
```

---

## `--dg5f` / `--no-dg5f`

`record_demo` and `run_policy` accept `--dg5f` / `--no-dg5f`
(BooleanOptionalAction) overriding `config.dg5f.enabled` in `robot.yaml`.
The flag must match how the checkpoint was trained: a 6-dim policy can't
deploy on a 26-dim observation and vice versa. While dg5f is unplugged,
use `--no-dg5f` on both record and deploy.

---

## Hardware reference

| Device                 | IP                 | Notes                                   |
|------------------------|--------------------|-----------------------------------------|
| UR10E (follower)       | `169.254.186.92`   | wired NIC on the NUC                    |
| UR3e (leader, opt)     | `169.254.186.94`   | only when bilateral teleop is on        |
| dg5f right (delto)     | `169.254.186.72`   | currently unplugged                     |
| dg5f left (delto)      | `169.254.186.73`   | at vendor for repair                    |
| RealSense D405 (wrist) | serial `218622270770` |                                       |
| RealSense D405 (scene) | serial `218622277871` |                                       |
