# Robot ROS2 interface survey

Survey of the external topic / action / message contracts exposed by the
existing UR10E and dg5f ROS2 stacks. **This repo does not modify those
stacks — it only consumes them.**

Last surveyed: 2026-05-30 (Session #1).

Cameras: not bundled into either workspace — must be brought up separately
(driver TBD, see "Cameras" section).

---

## UR10E (6-DoF arm)

The UR10E stack has **two parallel control paths** depending on how the arm
is being driven:

| Path | When | State source | Command path |
|------|------|-------------|--------------|
| **A. Teleop (RTDE direct-torque)** | bilateral teleop active | `/ur10e/follower/joint_state` | RTDE torque registers (not a ROS topic) |
| **B. ROS2 control native** | autonomous / policy deployment | `/joint_states` | `joint_trajectory_controller` action or `forward_position_controller` topic |

The ACT pipeline likely needs **both**: path A for data recording (during
teleop demos), path B for policy deployment.

### A. Teleop path (`ur10e_teleop_real_py`)

- **State topic**: `/ur10e/follower/joint_state` (and `/ur10e/leader/joint_state`)
  - Type: `sensor_msgs/JointState`
  - Rate: ~50 Hz (state_pub_every=2 over a 250 Hz internal loop)
  - Fields: `position[6]` (rad), `velocity[6]` (rad/s), `effort[6]` (Nm, *computed* contact estimate — not raw)
  - Joint order: `shoulder_pan, shoulder_lift, elbow, wrist_1, wrist_2, wrist_3`
  - Publisher: `ur10e_teleop_real_py/src/follower_real_node.py:189-248`
- **Mode topic**: `/ur10e/mode` — `std_msgs/Float64MultiArray` `[mode, t_start, duration]`
  - mode: 0=ACTIVE (track leader), 1=PAUSED, 2=HOMING, 3=FREEDRIVE (zero torque)
- **Reset topic**: `/ur10e/reset` — `std_msgs/Int32`
- **Launch**:
  ```
  ros2 launch ur10e_teleop_real_py teleop_real.launch.py \
      leader_ip:=<UR3e_IP> follower_ip:=<UR10e_IP>
  ```
  Distributed variants: `teleop_real_leader.launch.py`, `teleop_real_follower.launch.py`.
- **Command path**: not a ROS topic — torques are sent over RTDE register IO directly to the UR firmware (`direct_torque()`, requires UR firmware >= 5.22, controller in Remote Control mode).

### B. ROS2-control native path (`ur10e_ros2`)

- **State topic**: `/joint_states`
  - Type: `sensor_msgs/JointState`
  - Rate: 100 Hz (`state_publish_rate` in `ur10e_controllers.yaml`)
  - Source: `joint_state_broadcaster`
- **Command paths** (choose one controller):
  | Controller | Topic / Action | Type | Interface |
  |-----------|---------------|------|-----------|
  | `joint_trajectory_controller` (default) | `/joint_trajectory_controller/follow_joint_trajectory` (action) | `control_msgs/action/FollowJointTrajectory` | position |
  | `forward_position_controller` | `/forward_position_controller/commands` | `std_msgs/Float64MultiArray` (6 floats) | position |
  | `forward_velocity_controller` | `/forward_velocity_controller/commands` | `std_msgs/Float64MultiArray` (6 floats) | velocity |

  Joint order in `Float64MultiArray` matches the joint list above.
- **Hardware interfaces**: `position`, `velocity` (command); `position`, `velocity`, `effort` (state). Plugin: `ur10e_hardware/UR10EHardwareInterface`.
- **Controller manager update rate**: 500 Hz.
- **Launch**:
  ```
  ros2 launch ur10e_bringup ur10e.launch.py \
      robot_ip:=<IP> robot_controller:=joint_trajectory_controller
  ```
  Args: `robot_ip` (default `192.168.1.100`), `use_fake_hardware`, `frequency` (RTDE Hz, default 500).

---

## dg5f (5-finger hand, 20 DoF)

Single primary control path: ros2_control with `effort_controller` as the
production default. PID-based trajectory variants also exist.

### State

- **Topic**: `/dg5f_right/joint_states` (left hand: `/dg5f_left/joint_states`)
  - Type: `sensor_msgs/JointState`
  - Rate: ~300 Hz (controller_manager `update_rate`; joint_state_broadcaster `state_publish_rate: 100` Hz in some configs — check launched config)
  - Fields: `position[20]`, `velocity[20]`, `effort[20]` (effort = motor current feedback in mA, repurposed into the `effort` field)
  - Joint order (fixed across all controllers): `rj_dg_{f}_{j}` for f in 1..5, j in 1..4 → 20 names total
- **Optional fingertip F/T (if `fingertip_sensor:=true`)**:
  - Topics: `/dg5f_right/right_fingertip_<1..5>_sub/wrench`
  - Type: `geometry_msgs/WrenchStamped`
- **Optional contact-level monitor** (separate node `dg5f_contact_viz`):
  - Topic: `/dg5f_right/contact_level`
  - Type: `std_msgs/Float32MultiArray` (20 floats, normalized [0,1])
  - Note: needs ~60 baseline samples on startup (hand held still)

### Command

| Controller | Topic / Action | Type | Notes |
|-----------|---------------|------|-------|
| `effort_controller` (default / production) | `/dg5f_right/effort_controller/command` | `std_msgs/Float64MultiArray` (20 floats) | direct torque/current cmd |
| `dg5f_right_controller` (JTC w/ PID, effort-driven) | `/dg5f_right/dg5f_right_controller/follow_joint_trajectory` | `control_msgs/action/FollowJointTrajectory` | position target → PID → effort |
| `dg5f_right_pid_all_controller` | `/dg5f_right/dg5f_right_pid_all_controller/command` | `std_msgs/Float64MultiArray` (20 floats) | position cmd via PID |

Hardware-level command interface is **effort only** (motor current). Position control is achieved via a PID loop in the controller (not in hardware).

### Launch

```
ros2 launch dg5f_hand_bringup dg5f_right_bringup.launch.py \
    delto_ip:=169.254.186.72 delto_port:=502 fingertip_sensor:=false
```

Args: `delto_ip` (Modbus TCP IP), `delto_port` (502), `fingertip_sensor`, `ft_broadcaster`, `io`.

Mock variant: `dg5f_right_mock.launch.py` (no device required — useful on this PC).

---

## Cameras

Not part of either workspace. To be brought up by their own driver
(e.g. `realsense2_camera`, `usb_cam`). Once decided, fill in:

| Topic | Type | Resolution | Rate | Mount |
|-------|------|------------|------|-------|
| _TBD_ | `sensor_msgs/Image` or `sensor_msgs/CompressedImage` | _TBD_ | _TBD_ | wrist |
| _TBD_ | … | _TBD_ | _TBD_ | scene |

For single-arm setup: **2 cameras** (e.g. 1 wrist + 1 scene).
For dual-arm: 4 cameras.

---

## Manus glove + VIVE (master side — FYI, not consumed by policy)

Used during teleop only. Listed for completeness:

- `manus_glove` packages: `manus_dg5f_retarget`, `manus_dg5f_sota_retarget_a`, `manus_dg5f_sota_retargeting_a_good`, `manus_dg5f_grasp_mode`
- Message package: `manus_ros2_msgs`
- The follower-side joint_state already contains the *result* of teleop tracking, so the policy doesn't need to know the master inputs.

---

## Design implications for `ros2_bridge`

1. **Data recording** uses path A topics (`/ur10e/follower/joint_state` + `/dg5f_right/joint_states` + camera image topics).
2. **Policy deployment** needs to pick a command interface for each robot. Open questions tracked in `ARCHITECTURE.md`:
   - UR10E: `joint_trajectory_controller` action (chunked trajectory) vs `forward_position_controller` topic (sample-by-sample). ACT-style action chunks map naturally to either.
   - dg5f: `effort_controller` topic (raw torque, harder for ACT to learn) vs PID position controller (smoother target). Recommend PID position for first experiments.
3. **Rate mismatch**: UR ~50–100 Hz, dg5f ~300 Hz, cameras typically 30 Hz. Recorder will use a single common rate (likely 30 Hz, matching cameras) and ZOH-resample / drop the rest.
4. **Joint order is fixed** for both robots — bake the canonical order into `pai_teach/configs/robot.yaml` so the dataset and the runner agree.
