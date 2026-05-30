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

## Two-machine workflow

This repository is developed on one machine and executed on another:

1. **Dev machine** (this PC): writes/edits code, pushes to GitHub
2. **Training machine**: pulls and runs (data collection, training, deployment)

Sync via this repo. Datasets and checkpoints are **not** committed — transfer them out-of-band (rsync, HF Hub, etc.).

## Hardware control packages (do **not** modify here)

| Component | Location | Notes |
|-----------|----------|-------|
| UR10E ROS2 stack | `~/colcon_ws/src/` | maintained in a separate session |
| dg5f ROS2 stack | `~/hand_ws/src/dg/` | maintained in a separate session |
| Manus glove | `~/hand_ws/src/manus_glove/` | master side |

This repo only contains thin adapters that *consume* the topics those packages expose.

## Status

- [ ] Robot ROS2 interface survey (`docs/ROBOT_INTERFACE.md`)
- [ ] ros2_bridge: UR10E state/cmd
- [ ] ros2_bridge: dg5f state/cmd
- [ ] data_recorder: write LeRobot-format episodes
- [ ] policy/act: training script
- [ ] policy/runner: ROS2 deployment
