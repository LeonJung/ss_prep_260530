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

# Sanity ACT train (uses GPU if --gpus all / compose deploy block is honored)
docker compose run --rm pai_teach \
    python -m scripts.train_act --config pai_teach/configs/act.yaml --steps 50

# Record a teleop demo (host network so we see the host/zenoh ROS2 graph)
docker compose run --rm pai_teach \
    python -m scripts.record_demo --repo-id leonjung/pai_teach_demos \
    --root datasets/pai_teach_demos --task pick_and_place --max-seconds 30
```

`docker-compose.yml` mounts the repo at `/workspace`, sets
`RMW_IMPLEMENTATION=rmw_zenoh_cpp` + `ROS_DOMAIN_ID=15`, and requests all
GPUs. Needs `nvidia-container-toolkit` on the host.

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
- [ ] policy/act: training script
- [ ] policy/runner: ROS2 deployment
