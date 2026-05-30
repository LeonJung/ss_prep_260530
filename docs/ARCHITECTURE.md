# Architecture (draft)

Status: **draft** — fill in once robot interface survey is done.

## Layers

### 1. Robot control (external, untouched)
- `~/colcon_ws/src/ur10e_*` — UR10E ROS2 packages
- `~/hand_ws/src/dg/*` — dg5f ROS2 packages
- `~/hand_ws/src/manus_glove/*` — Manus glove (master)

These are maintained in other sessions. pai_teach only **consumes** their topics.

### 2. ros2_bridge (this repo)
Thin Python adapters using `rclpy`:
- Subscribe to UR10E joint state, TCP pose, dg5f joint state, camera images
- Publish UR10E joint command, dg5f joint command
- Provide a synchronous `RobotIO` interface so the recorder and runner don't depend on ROS internals

### 3. data_recorder
- Reads `RobotIO` at fixed rate (e.g. 30 Hz)
- Writes episodes in **LeRobot dataset format** (parquet + videos)
- Episode = one teleop demonstration

### 4. policy/act
- Wraps LeRobot's ACT training entry point
- Custom config in `pai_teach/configs/` describing UR10E+dg5f obs/action spaces

### 5. policy/runner
- Loads checkpoint
- Reads obs from `RobotIO`, predicts action chunk, publishes via `RobotIO`
- Action chunking horizon and temporal ensemble per LeRobot defaults

## Open design questions

- Action representation: joint position vs joint velocity vs EE pose? (depends on what UR10E controller accepts)
- Hand action representation: joint angles vs grasp primitive id?
- Sync strategy across heterogeneous topic rates (UR10E vs dg5f vs cameras)
- Where to do image resizing / normalization (recorder vs runtime)
