"""D405 launch — color-only @ 424x240x30, depth/IR off.

`cams` launch arg selects which camera(s) to bring up:
    cams:=both   (default)  → wrist + scene
    cams:=wrist             → wrist only
    cams:=scene             → scene only

Useful for isolating "no frames 5 sec" — if a single-camera launch is
stable but the two-camera launch isn't, the issue is shared USB
controller saturation, not the per-camera config.

Topics: /camera/wrist_cam/color/image_raw, /camera/scene_cam/color/image_raw

Run NATIVELY on the NUC (ROS sourced):
    ros2 launch ~/ai_ws/launch/d405_color_only.launch.py            # both
    ros2 launch ~/ai_ws/launch/d405_color_only.launch.py cams:=wrist
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


WRIST_SERIAL = "218622270770"
SCENE_SERIAL = "218622277871"


def _params(serial: str, camera_name: str) -> dict:
    return {
        "serial_no": serial,
        "camera_name": camera_name,
        # Streams: color only
        "enable_color": True,
        "enable_depth": False,
        "enable_infra": False,
        "enable_infra1": False,
        "enable_infra2": False,
        "enable_sync": False,
        "enable_rgbd": False,
        "enable_pointcloud": False,
        "enable_accel": False,
        "enable_gyro": False,
        # D405 puts every stream profile under `depth_module.*` (not
        # `rgb_camera.*` like D435). Confirmed on this hardware:
        #   ros2 param list /camera/wrist_cam | grep profile
        #   → depth_module.{color,depth,infra}_profile
        "depth_module.color_profile": "424x240x30",
    }


def _cam_node(name: str, serial: str) -> Node:
    return Node(
        package="realsense2_camera",
        executable="realsense2_camera_node",
        namespace="camera",
        name=name,
        output="screen",
        parameters=[_params(serial, name)],
    )


def _make_nodes(context):
    cams = LaunchConfiguration("cams").perform(context)
    nodes = []
    if cams in ("both", "wrist"):
        nodes.append(_cam_node("wrist_cam", WRIST_SERIAL))
    if cams in ("both", "scene"):
        nodes.append(_cam_node("scene_cam", SCENE_SERIAL))
    if not nodes:
        raise ValueError(f"unknown cams={cams!r}, expected both|wrist|scene")
    return nodes


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument(
            "cams",
            default_value="both",
            description="which cameras to launch: both | wrist | scene",
        ),
        OpaqueFunction(function=_make_nodes),
    ])
