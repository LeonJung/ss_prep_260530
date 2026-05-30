"""LeRobotDataset writer for UR10E + dg5f teleop demonstrations.

The dataset layout follows LeRobot's standard format (parquet meta + mp4
videos). State/action are flat float32 vectors concatenating UR10E and dg5f
joint positions in canonical order.

The `lerobot` package is imported lazily so this module can be imported on
the dev box (no torch / lerobot installed).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from ..ros2_bridge.types import Action, Observation

if TYPE_CHECKING:
    pass


def _import_lerobot_dataset():
    """Locate LeRobotDataset across the package's churning module paths."""
    last_err: Exception | None = None
    for modpath in (
        "lerobot.common.datasets.lerobot_dataset",
        "lerobot.datasets.lerobot_dataset",
    ):
        try:
            mod = __import__(modpath, fromlist=["LeRobotDataset"])
            return mod.LeRobotDataset
        except ImportError as e:
            last_err = e
    raise ImportError(
        "Could not import LeRobotDataset from lerobot. "
        "Install via requirements-training.txt on the training PC. "
        f"Last error: {last_err}"
    )


@dataclass
class CameraInfo:
    name: str
    height: int
    width: int


class LeRobotWriter:
    """One writer instance per dataset (collection of episodes)."""

    def __init__(
        self,
        repo_id: str,
        root: str | Path,
        fps: int,
        ur10e_joint_names: list[str],
        dg5f_joint_names: list[str],
        cameras: list[CameraInfo],
        use_videos: bool = True,
    ) -> None:
        self._fps = fps
        self._ur10e_names = list(ur10e_joint_names)
        self._dg5f_names = list(dg5f_joint_names)
        self._cameras = list(cameras)
        self._state_dim = len(ur10e_joint_names) + len(dg5f_joint_names)
        self._dataset: Any = None
        self._root = Path(root)
        self._repo_id = repo_id
        self._use_videos = use_videos

    # ---- lazy dataset creation ------------------------------------------

    def _features(self) -> dict[str, dict]:
        state_names = self._ur10e_names + self._dg5f_names
        feats: dict[str, dict] = {
            "observation.state": {
                "dtype": "float32",
                "shape": (self._state_dim,),
                "names": state_names,
            },
            "action": {
                "dtype": "float32",
                "shape": (self._state_dim,),
                "names": state_names,
            },
        }
        img_dtype = "video" if self._use_videos else "image"
        for cam in self._cameras:
            feats[f"observation.images.{cam.name}"] = {
                "dtype": img_dtype,
                "shape": (cam.height, cam.width, 3),
                "names": ["height", "width", "channels"],
            }
        return feats

    def _ensure_dataset(self) -> None:
        if self._dataset is not None:
            return
        LeRobotDataset = _import_lerobot_dataset()
        self._dataset = LeRobotDataset.create(
            repo_id=self._repo_id,
            fps=self._fps,
            features=self._features(),
            root=self._root,
            use_videos=self._use_videos,
        )

    # ---- per-frame -------------------------------------------------------

    @staticmethod
    def _state_vec(obs: Observation) -> np.ndarray:
        return np.concatenate(
            [obs.state.ur10e_position, obs.state.dg5f_position]
        ).astype(np.float32)

    @staticmethod
    def _action_vec(action: Action) -> np.ndarray:
        return np.concatenate(
            [action.ur10e_position, action.dg5f_position]
        ).astype(np.float32)

    def add_frame(self, obs: Observation, action: Action, task: str) -> None:
        """Append one synchronized obs/action pair to the current episode."""
        self._ensure_dataset()
        frame: dict[str, Any] = {
            "observation.state": self._state_vec(obs),
            "action": self._action_vec(action),
            "task": task,
        }
        for cam in self._cameras:
            img = obs.images.get(cam.name)
            if img is None:
                raise RuntimeError(
                    f"camera '{cam.name}' missing from observation "
                    f"(have {list(obs.images.keys())})"
                )
            frame[f"observation.images.{cam.name}"] = img
        self._dataset.add_frame(frame)

    def save_episode(self) -> None:
        if self._dataset is None:
            raise RuntimeError("no frames added; cannot save_episode")
        self._dataset.save_episode()

    def num_episodes(self) -> int:
        if self._dataset is None:
            return 0
        return int(getattr(self._dataset, "num_episodes", 0))
