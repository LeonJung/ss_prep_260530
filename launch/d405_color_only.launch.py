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
        # Force 424x240 @ 30. The correct realsense2_camera parameter
        # name is `rgb_camera.profile` (NOT `rgb_camera.color_profile` —
        # that's the wrong name that gets silently ignored, see
        # realsense-ros issues #3112 and #3306). D405's native color
        # resolutions are 1280x720, 848x480, 640x480, 424x240; 480x270
        # is D435 territory and the D405 silently falls back to default
        # 848x480 when asked for it.
        "rgb_camera.profile": "424x240x30",
        "rgb_camera.color_format": "RGB8",
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
