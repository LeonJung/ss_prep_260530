# Robot ROS2 interface survey

**Status:** TODO — to be filled in by reading `~/colcon_ws/src/` and `~/hand_ws/src/`.

This file is the source of truth for which topics / services / messages `ros2_bridge` connects to.

## UR10E (arm)

| Direction | Topic | Type | Rate | Notes |
|-----------|-------|------|------|-------|
| state     | _TBD_ | _TBD_ | _TBD_ | joint positions, velocities, efforts |
| state     | _TBD_ | _TBD_ | _TBD_ | TCP pose |
| cmd       | _TBD_ | _TBD_ | _TBD_ | joint position command |

## dg5f (5-finger hand)

| Direction | Topic | Type | Rate | Notes |
|-----------|-------|------|------|-------|
| state     | _TBD_ | _TBD_ | _TBD_ | finger joint positions |
| state     | _TBD_ | _TBD_ | _TBD_ | tactile / contact (if available) |
| cmd       | _TBD_ | _TBD_ | _TBD_ | finger joint command |

## Cameras

| Topic | Type | Resolution | Rate | Mount |
|-------|------|------------|------|-------|
| _TBD_ | _TBD_ | _TBD_ | _TBD_ | wrist / scene |

(For single-arm setup: 2 cameras. For dual-arm: 4 cameras.)

## Manus glove + VIVE (master, FYI only)

Used for teleop input. Not consumed by the learned policy — listed here only for context, not for the bridge.
