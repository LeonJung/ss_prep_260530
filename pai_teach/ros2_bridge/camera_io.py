"""RealSense camera IO: subscribe one or more color streams, expose latest RGB.

Supports both `sensor_msgs/Image` and `sensor_msgs/CompressedImage`. The
recorder asks for the latest frame; if the camera is configured to publish
CompressedImage, we decode with OpenCV (jpeg/png) before handing out.

Images are stored as HxWx3 uint8 RGB.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage, Image


@dataclass
class CameraSpec:
    name: str
    topic: str
    compressed: bool = False
    width: int | None = None
    height: int | None = None


class _SingleCameraIO:
    def __init__(self, node: Node, spec: CameraSpec) -> None:
        self._node = node
        self._spec = spec
        self._bridge = CvBridge()
        self._lock = threading.Lock()
        self._image: np.ndarray | None = None
        self._stamp = 0.0

        if spec.compressed:
            self._sub = node.create_subscription(
                CompressedImage, spec.topic, self._on_compressed, 5
            )
        else:
            self._sub = node.create_subscription(
                Image, spec.topic, self._on_image, 5
            )

    def _on_image(self, msg: Image) -> None:
        # cv_bridge returns BGR for "bgr8"; convert to RGB for ML use.
        try:
            bgr = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as e:
            self._node.get_logger().warn(f"camera '{self._spec.name}' decode error: {e}")
            return
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
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
