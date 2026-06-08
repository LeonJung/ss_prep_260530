"""Two RealSense D405s, color-only @ 480x270x30 — direct Node launch.

Bypasses rs_launch.py's argument-forwarding (where
`rgb_camera.color_profile:=...` was being silently ignored at our
realsense2_camera version). Sets the node parameters directly here.

We list several alternative parameter names (`rgb_camera.color_profile`,
`rgb_camera.profile`, plus split width/height/fps) so whichever the
installed realsense2_camera build recognizes wins; the others are
ignored.

Topics published:
    /camera/wrist_cam/color/image_raw
    /camera/scene_cam/color/image_raw

Run NATIVELY on the NUC (ROS sourced):
    ros2 launch ~/ai_ws/launch/d405_color_only.launch.py
"""

from launch import LaunchDescription
from launch_ros.actions import Node


WRIST_SERIAL = "218622270770"
SCENE_SERIAL = "218622277871"


def _params(serial: str, camera_name: str) -> dict:
    return {
        # Identity
        "serial_no": serial,
        "camera_name": camera_name,
        # Streams: color only
        "enable_color": True,
        "enable_depth": False,
        "enable_infra1": False,
        "enable_infra2": False,
        "enable_sync": False,
        "enable_pointcloud": False,
        "enable_accel": False,
        "enable_gyro": False,
        # D405 puts ALL stream profiles (color, depth, infra) under
        # `depth_module.*`, NOT under `rgb_camera.*` like the D435 family.
        # Verified with `ros2 param list /camera/<name> | grep profile`
        # on this hardware: the only profile params that exist are
        #   depth_module.color_profile / .depth_profile / .infra_profile
        # D405 advertises color modes 424x240, 480x270, 640x360, 640x480,
        # 848x480, 1280x720 — all RGB8. We pick the smallest that's
        # comfortably above ACT's typical 224x224 resize.
        "depth_module.color_profile": "424x240x30",
    }


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        Node(
            package="realsense2_camera",
            executable="realsense2_camera_node",
            namespace="camera",
            name="wrist_cam",
            output="screen",
            parameters=[_params(WRIST_SERIAL, "wrist_cam")],
        ),
        Node(
            package="realsense2_camera",
            executable="realsense2_camera_node",
            namespace="camera",
            name="scene_cam",
            output="screen",
            parameters=[_params(SCENE_SERIAL, "scene_cam")],
        ),
    ])
