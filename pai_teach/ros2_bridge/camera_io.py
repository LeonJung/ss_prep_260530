"""RealSense camera IO: subscribe one or more color streams, expose latest RGB.

Supports both `sensor_msgs/Image` and `sensor_msgs/CompressedImage`. We do
the raw byte → numpy conversion ourselves (NOT via cv_bridge) because
`cv_bridge.boost` is the one ROS jazzy C-extension that's incompatible with
the NumPy 2.x ABI required by lerobot.

Images are stored as HxWx3 uint8 RGB.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage, Image

# RealSense (and most camera drivers) publish images with BEST_EFFORT
# reliability. A default RELIABLE subscription silently fails to receive
# anything from them — symptom: wait_until_ready timeout on "cameras".
_CAMERA_QOS = QoSProfile(
    depth=5,
    reliability=ReliabilityPolicy.BEST_EFFORT,
    history=HistoryPolicy.KEEP_LAST,
)


@dataclass
class CameraSpec:
    name: str
    topic: str
    compressed: bool = False
    width: int | None = None
    height: int | None = None


def _imgmsg_to_rgb(msg: Image) -> np.ndarray | None:
    """sensor_msgs/Image -> HxWx3 uint8 RGB, manually (no cv_bridge)."""
    enc = msg.encoding.lower()
    h, w = int(msg.height), int(msg.width)
    raw = np.frombuffer(msg.data, dtype=np.uint8)
    if enc in ("rgb8", "bgr8"):
        if raw.size != h * w * 3:
            return None
        arr = raw.reshape(h, w, 3)
        return arr if enc == "rgb8" else arr[..., ::-1].copy()
    if enc in ("rgba8", "bgra8"):
        if raw.size != h * w * 4:
            return None
        arr = raw.reshape(h, w, 4)[..., :3]
        return arr if enc == "rgba8" else arr[..., ::-1].copy()
    if enc in ("mono8", "8uc1"):
        if raw.size != h * w:
            return None
        gray = raw.reshape(h, w)
        return np.repeat(gray[..., None], 3, axis=2)
    # Unsupported encoding — caller logs.
    return None


class _SingleCameraIO:
    def __init__(self, node: Node, spec: CameraSpec) -> None:
        self._node = node
        self._spec = spec
        self._lock = threading.Lock()
        self._image: np.ndarray | None = None
        self._stamp = 0.0

        if spec.compressed:
            self._sub = node.create_subscription(
                CompressedImage, spec.topic, self._on_compressed, _CAMERA_QOS
            )
        else:
            self._sub = node.create_subscription(
                Image, spec.topic, self._on_image, _CAMERA_QOS
            )

    def _on_image(self, msg: Image) -> None:
        rgb = _imgmsg_to_rgb(msg)
        if rgb is None:
            self._node.get_logger().warn(
                f"camera '{self._spec.name}' unsupported encoding "
                f"or size mismatch (encoding={msg.encoding}, {msg.height}x{msg.width})"
            )
            return
        rgb = self._maybe_resize(rgb)
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        with self._lock:
            self._image = rgb
            self._stamp = stamp

    def _on_compressed(self, msg: CompressedImage) -> None:
        arr = np.frombuffer(msg.data, dtype=np.uint8)
        bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if bgr is None:
            self._node.get_logger().warn(
                f"camera '{self._spec.name}' imdecode returned None"
            )
            return
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        rgb = self._maybe_resize(rgb)
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        with self._lock:
            self._image = rgb
            self._stamp = stamp

    def _maybe_resize(self, rgb: np.ndarray) -> np.ndarray:
        w, h = self._spec.width, self._spec.height
        if w is None or h is None:
            return rgb
        if rgb.shape[1] == w and rgb.shape[0] == h:
            return rgb
        return cv2.resize(rgb, (w, h), interpolation=cv2.INTER_AREA)

    def snapshot(self) -> tuple[np.ndarray | None, float]:
        with self._lock:
            img = None if self._image is None else self._image.copy()
            return img, self._stamp

    def has_image(self) -> bool:
        with self._lock:
            return self._image is not None


class CameraBank:
    """One subscriber per camera, name-indexed snapshot()."""

    def __init__(self, node: Node, specs: list[CameraSpec]) -> None:
        self._cameras = {spec.name: _SingleCameraIO(node, spec) for spec in specs}

    def names(self) -> list[str]:
        return list(self._cameras.keys())

    def snapshot(self) -> dict[str, np.ndarray]:
        """Return latest RGB per camera. Skips cameras that have no frame yet."""
        out: dict[str, np.ndarray] = {}
        for name, cam in self._cameras.items():
            img, _ = cam.snapshot()
            if img is not None:
                out[name] = img
        return out

    def all_have_images(self) -> bool:
        return all(cam.has_image() for cam in self._cameras.values())

    def wait_for_all(self, timeout_s: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self.all_have_images():
                return True
            time.sleep(0.05)
        return False
