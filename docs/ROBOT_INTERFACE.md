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

**Production** uses a single multi-DOF `pid_controller/PidController` named
`rj_dg_pospid` (right) / `lj_dg_pospid` (left). Reference is published as
`control_msgs/MultiDOFCommand` at ~50 Hz on the controller's reference topic:

| Controller | Topic | Type | Notes |
|-----------|-------|------|-------|
| **`rj_dg_pospid`** (production) | `/dg5f_right/rj_dg_pospid/reference` | `control_msgs/MultiDOFCommand` | `dof_names`+`values` (20 position refs), `command_interface: effort`, `reference_and_state_interfaces: [position]`. 50 Hz typical. |
| `dg5f_right_controller` (MoveIt) | `/dg5f_right/dg5f_right_controller/follow_joint_trajectory` | `control_msgs/action/FollowJointTrajectory` | Used by MoveIt integration; NOT the production teleop/policy path. |

`MultiDOFCommand` shape:
```
dof_names: ["rj_dg_1_1", "rj_dg_1_2", ..., "rj_dg_5_4"]   # 20 joints
values:    [pos_rad, ...]                                  # length 20
values_dot:[0.0,    ...]                                   # length 20 (vel ref; 0 for pure pos)
```

Hardware-level command interface is **effort only** (motor current). Position control is achieved via the PID loop in the controller (not in hardware).

### Launch

```
ros2 launch dg5f_hand_bringup dg5f_right_bringup.launch.py \
    delto_ip:=169.254.186.72 delto_port:=502 fingertip_sensor:=false
```

Args: `delto_ip` (Modbus TCP IP), `delto_port` (502), `fingertip_sensor`, `ft_broadcaster`, `io`.

Mock variant: `dg5f_right_mock.launch.py` (no device required — useful on this PC).

---

## Cameras

Not part of either workspace. Driver: **`realsense2_camera`** (Intel RealSense).
Brought up separately from the robot stacks.

Default topic shape from `realsense2_camera` is `/<camera_name>/color/image_raw`
(plus `/depth/image_rect_raw`, `/color/camera_info`, …) where `<camera_name>`
is set per node instance.

For the single-arm setup we plan **2 cameras** (placeholder names — confirm at bringup):

| Topic | Type | Resolution | Rate | Mount |
|-------|------|------------|------|-------|
| `/wrist_cam/color/image_raw` | `sensor_msgs/Image` | TBD (likely 640×480) | 30 Hz | wrist-mounted |
| `/scene_cam/color/image_raw` | `sensor_msgs/Image` | TBD | 30 Hz | scene / overview |

For a future dual-arm setup: 4 cameras (left/right wrist + 2 scene).

Open: do we need depth streams as ACT inputs? Default for now is **RGB only** (ACT recipes generally use RGB).

---

## Manus glove + VIVE (master side — FYI, not consumed by policy)

Used during teleop only. Listed for completeness:

- `manus_glove` packages: `manus_dg5f_retarget`, `manus_dg5f_sota_retarget_a`, `manus_dg5f_sota_retargeting_a_good`, `manus_dg5f_grasp_mode`
- Message package: `manus_ros2_msgs`
- The follower-side joint_state already contains the *result* of teleop tracking, so the policy doesn't need to know the master inputs.

---

## Design implications for `ros2_bridge`

1. **Data recording** uses path A topics (`/ur10e/follower/joint_state` + `/dg5f_right/joint_states` + RealSense color topics).
2. **Policy deployment** command interfaces:
   - UR10E: **`joint_trajectory_controller`** action (`/joint_trajectory_controller/follow_joint_trajectory`). ACT chunks are wrapped as short trajectories with `time_from_start` per step.
   - dg5f: **multi-DOF PidController** publishing `control_msgs/MultiDOFCommand` on `/dg5f_right/rj_dg_pospid/reference` at 50 Hz. ACT outputs joint position targets, controller's PID converts to effort.
3. **Rate mismatch**: UR ~50–100 Hz, dg5f ~300 Hz, RealSense ~30 Hz. Recorder will sample at the camera rate (30 Hz) and use the most-recent robot state via message_filters / latched cache.
4. **Joint order is fixed** for both robots — bake the canonical order into `pai_teach/configs/robot.yaml` so the dataset and the runner agree.

## Decisions (as of 2026-05-30)

| Topic | Decision | Status |
|-------|----------|--------|
| ACT framework | LeRobot | confirmed |
| dg5f command interface | multi-DOF `pid_controller/PidController` (`rj_dg_pospid`), `MultiDOFCommand` on `…/reference` | confirmed 2026-05-30 from hand_ws/src |
| Camera driver | `realsense2_camera`, RGB only (default) | confirmed |
| UR10E policy-deployment controller | **`joint_trajectory_controller` (JTC)** via `FollowJointTrajectory` action | confirmed |
| Number of cameras | 2 (single-arm: 1 wrist + 1 scene) | confirmed |
| ROS2 distro | Jazzy (both PCs) | confirmed |
