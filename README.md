# pai_teach — Physical AI Direct Teaching Framework

Teleoperation-based imitation learning framework for the **UR10E arm + dg5f 5-finger hand** platform.

Master side: VIVE tracker + Manus glove
Slave / learner side: UR10E + dg5f
First policy: **ACT** (Action Chunking Transformer), via [LeRobot](https://github.com/huggingface/lerobot)

## Workflow

```
                +------------------+         +---------------------+
   VIVE / Manus | ros2_bridge      |  state  | data_recorder       |
   teleop  ---->|  (UR10E, dg5f)   |-------->|  -> LeRobot dataset |
                +------------------+         +----------+----------+
                       ^                                |
                       | action                         v
                       |                       +-----------------+
                       |                       | policy/act      |
                       |                       |  (LeRobot ACT)  |
                       |                       +--------+--------+
                +------+-----------+                    |
                | policy/runner    |<-------------------+
                |  (deploy ckpt)   |    inference
                +------------------+
```

## Repository layout

```
pai_teach/
├── ros2_bridge/        ROS2 <-> Python adapters (state sub, action pub)
├── data_recorder/      Collect teleop demonstrations into LeRobot dataset
├── policy/
│   ├── act/            ACT training (LeRobot config)
│   └── runner/         Load checkpoint and act on the robot
├── utils/              Timestamp sync, image utils, transforms
└── configs/            YAML configs (robot, sensors, policy)
scripts/                Entry-point CLI scripts
datasets/               Recorded demos (git-ignored, sync separately)
checkpoints/            Trained policies (git-ignored)
docs/                   Design / interface notes
tests/                  Unit tests
```

## Three-machine workflow

| Role | Runs |
|------|------|
| **Dev PC** (this repo's editor) | edits code, pushes to GitHub, light import / unit tests |
| **Controller PC** | `ur10e_teleop_real_py`, `dg5f_hand_bringup`, `realsense2_camera` (publishers only) |
| **Training PC** (RTX 5000-class GPU) | pulls this repo, runs `record_demo` / `train_act` / `run_policy` |

ROS2 middleware: **`rmw_zenoh_cpp`**, `ROS_DOMAIN_ID=15`. A `rmw_zenohd`
router must be running on the controller PC. Full setup, IPs, and
discovery troubleshooting in [`docs/MULTI_PC_SETUP.md`](docs/MULTI_PC_SETUP.md).

Datasets and checkpoints are **not** committed — transfer them out-of-band
(rsync, HF Hub, etc.).

## Docker (single image for Controller-PC & Training-PC use)

```bash
docker build -t pai_teach:latest .

# Sanity check (no robot needed — generates a tiny dataset + trains 5 steps)
docker compose run --rm pai_teach bash -c '
    source /opt/ros/jazzy/setup.bash &&
    python -m scripts.make_dummy_dataset --root datasets/dummy \
        --repo-id local/dummy --episodes 2 --frames 64 &&
    python -m scripts.train_act --config pai_teach/configs/act.yaml \
        --repo-id local/dummy --root datasets/dummy \
        --steps 5 --num-workers 0 --batch-size 2
'

# Record a teleop demo (host network so we see the host/zenoh ROS2 graph)
docker compose run --rm pai_teach bash -c '
    source /opt/ros/jazzy/setup.bash &&
    python -m scripts.record_demo --repo-id leonjung/pai_teach_demos \
        --root datasets/pai_teach_demos --task pick_and_place --max-seconds 30
'
```

`docker-compose.yml` mounts the repo at `/workspace`, sets
`RMW_IMPLEMENTATION=rmw_zenoh_cpp` + `ROS_DOMAIN_ID=15`, `ipc: host` (for
DataLoader shared memory), requests all GPUs, and uses `network_mode: host`
so the in-container ROS2 graph sees the host. Needs
`nvidia-container-toolkit` on the host.

The ROS env must be sourced inside the container before running any
script (`source /opt/ros/jazzy/setup.bash`) — `bash -lc` skips
`/etc/bash.bashrc`. We do this inline above; if you `docker compose exec`
into a shell instead it gets sourced automatically.

## Hardware control packages (do **not** modify here)

| Component | Location | Notes |
|-----------|----------|-------|
| UR10E ROS2 stack | `~/colcon_ws/src/` | maintained in a separate session |
| dg5f ROS2 stack | `~/hand_ws/src/dg/` | maintained in a separate session |
| Manus glove | `~/hand_ws/src/manus_glove/` | master side |

This repo only contains thin adapters that *consume* the topics those packages expose.

## Status

- [x] Robot ROS2 interface survey (`docs/ROBOT_INTERFACE.md`)
- [x] ros2_bridge: UR10E state/cmd (JTC for deploy)
- [x] ros2_bridge: dg5f state/cmd (multi-DOF PidController + `MultiDOFCommand`)
- [x] data_recorder: write LeRobot-format episodes
- [x] policy/act: training script (sanity-tested end-to-end on dummy dataset)
- [x] policy/runner: ROS2 deployment (select_action sanity-tested; live RobotIO loop pending controller PC + robot)
