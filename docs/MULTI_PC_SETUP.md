# Multi-PC ROS2 setup

`pai_teach` runs across three machines:

```
┌─────────────────┐   teleop, sensor pubs   ┌─────────────────┐
│  Controller PC  │ ────────────────────▶  │   Training PC   │
│ (ur10e_teleop,  │      zenoh + ROS2       │ (record_demo,   │
│  dg5f_bringup,  │     DOMAIN_ID = 15      │  train_act,     │
│  realsense2)    │                         │  run_policy)    │
└────────┬────────┘                         └────────┬────────┘
         │                                            │
         │ RTDE / Modbus / USB                        │
         ▼                                            │
  UR10E + dg5f + RealSense                            ▼
                                              GPU (RTX 5000-class)
```

The **Dev PC** (this repo's primary editor) only pushes code; it sources ROS2
for import checks but is not part of the runtime network.

---

## ROS2 middleware: zenoh + DOMAIN_ID 15

Both the controller PC and the training PC export, before launching ANY
ROS2 node (including `record_demo.py` and `run_policy.py`):

```bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
export ROS_DOMAIN_ID=15
```

A zenoh **router** must be running so the peer machines can discover each
other across the network (zenoh peers do NOT auto-discover by multicast the
way default Fast-DDS does):

```bash
ros2 run rmw_zenoh_cpp rmw_zenohd
```

Run the router on a stable machine (typically the controller PC). The
default config picks up `ZENOH_ROUTER_CONFIG_URI` / `ZENOH_SESSION_CONFIG_URI`
if you need custom endpoints; otherwise it listens on `tcp/0.0.0.0:7447`.

Verify discovery from the training PC:

```bash
ros2 topic list | grep -E "(ur10e|dg5f|cam)"
ros2 topic echo --once /ur10e/follower/joint_state
ros2 topic hz /dg5f_right/joint_states         # expect ~300 Hz
ros2 topic hz /wrist_cam/color/image_raw       # expect ~30 Hz
```

If `topic list` is empty or topics show 0 Hz, the router is the first thing
to check.

---

## Per-PC responsibilities

### Controller PC

Brings up the robot stacks and the cameras (publishers only):

```bash
# Terminal 1 — zenoh router (leave running)
ros2 run rmw_zenoh_cpp rmw_zenohd

# Terminal 2 — UR10E teleop  (pick ONE)
#
#   (a) UNILATERAL (current default — VIVE tracker → IK → leader/joint_state):
ros2 launch ur10e_teleop_unilateral_vive_cpp teleop_real.launch.py \
    follower_ip:=169.254.186.92
#
#   (b) BILATERAL (force-feedback, requires UR3e leader arm):
# ros2 launch ur10e_teleop_real_py teleop_real.launch.py \
#     leader_ip:=169.254.186.94 follower_ip:=169.254.186.92
#
# Both publish the same topics (/ur10e/follower/joint_state, /ur10e/mode);
# pai_teach is agnostic to which is running.

# Terminal 3 — dg5f right hand (left hand currently at vendor)
ros2 launch dg5f_hand_bringup dg5f_right_bringup.launch.py \
    delto_ip:=169.254.186.72

# Terminal 4 — RealSense, one per camera (or compose into a single launch)
ros2 launch realsense2_camera rs_launch.py \
    camera_name:=wrist_cam serial_no:='"<wrist serial>"'
ros2 launch realsense2_camera rs_launch.py \
    camera_name:=scene_cam serial_no:='"<scene serial>"'
```

### Training PC

Subscribes only. Run from inside this repo:

```bash
# Data collection (one episode per invocation, Ctrl-C to stop)
python -m scripts.record_demo \
    --config pai_teach/configs/robot.yaml \
    --repo-id leonjung/pai_teach_demos \
    --root datasets/pai_teach_demos \
    --task pick_and_place \
    --max-seconds 30

# Training (consumes the dataset above)
python -m scripts.train_act --config pai_teach/configs/act.yaml

# Policy deployment
python -m scripts.run_policy --checkpoint checkpoints/latest.ckpt
```

### Dev PC (this repo's editor)

Only needs Python + ROS2 jazzy for import checks. Tests run without rclpy:

```bash
python -m pytest tests/
```

---

## Hardware IPs (recorded for reference)

| Device                 | IP                 | Source                                  |
|------------------------|--------------------|-----------------------------------------|
| UR10E (follower)       | `169.254.186.92`   | `ur10e_teleop_control_ff_cpp` launches  |
| UR3e (leader)          | `169.254.186.94`   | same                                    |
| dg5f right (delto)     | `169.254.186.72`   | `dg5f_hand_bringup` launch default      |
| dg5f left (delto)      | `169.254.186.73`   | `dg5f_moveit_config` launch (at vendor) |

All robots are on the `169.254.186.0/24` link-local subnet, reached from the
controller PC over a wired NIC. The training PC does NOT talk directly to
the robots — only via the controller PC's ROS2 graph.

---

## Network checklist (when discovery breaks)

1. `RMW_IMPLEMENTATION` and `ROS_DOMAIN_ID` set on **every** terminal that
   runs a ROS2 binary, **before** `ros2` / `python -m scripts.X`.
2. `rmw_zenohd` is running somewhere reachable from both PCs.
3. Firewall: zenoh router default port is **TCP 7447** — open it between the
   two PCs.
4. `ros2 daemon stop` (and `ros2 daemon start`) after changing
   `RMW_IMPLEMENTATION` — the daemon caches the discovery middleware.
5. If `topic list` works but `topic echo` hangs, it's usually a QoS
   mismatch, not a transport problem.
