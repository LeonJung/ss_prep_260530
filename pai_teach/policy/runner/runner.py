"""Deploy a trained ACT checkpoint onto the real robot via RobotIO.

LeRobot's ACTPolicy.select_action() owns its own action-chunk queue and
temporal-ensemble bookkeeping; per-step we just hand it the latest
observation and publish the action it returns.
"""

from __future__ import annotations

import signal
import time
from pathlib import Path

import numpy as np
import torch
import yaml

from ...ros2_bridge.types import Action


class ACTRunner:
    """Loads a checkpoint, opens RobotIO(deploy), runs the obs→act loop."""

    def __init__(
        self,
        checkpoint_path: str | Path,
        robot_config_path: str | Path,
        device: str = "cuda",
        rate_hz: float | None = None,
    ) -> None:
        self._cfg = yaml.safe_load(Path(robot_config_path).read_text())
        self._rate_hz = float(rate_hz) if rate_hz else float(self._cfg.get("record_rate_hz", 30))
        self._cam_names = [c["name"] for c in self._cfg.get("cameras", [])]
        self._ur_dof = int(self._cfg["ur10e"]["dof"])
        self._hand_dof = int(self._cfg["dg5f"]["dof"])
        self._device = torch.device(device if torch.cuda.is_available() or device == "cpu" else "cpu")

        # Lazy imports: lerobot needs torch + the package; ros2_bridge needs rclpy.
        from lerobot.policies.act.modeling_act import ACTPolicy

        from ...ros2_bridge.robot_io import RobotIO

        self._policy = ACTPolicy.from_pretrained(Path(checkpoint_path))
        self._policy.to(self._device)
        self._policy.eval()
        self._io = RobotIO(self._cfg, mode="deploy")

        self._stop = False
        signal.signal(signal.SIGINT, self._on_sigint)

    def _on_sigint(self, *_: object) -> None:
        self._stop = True

    def _obs_to_batch(self, obs) -> dict[str, torch.Tensor]:
        """Pack a pai_teach Observation into the dict ACTPolicy expects."""
        state_vec = np.concatenate(
            [obs.state.ur10e_position, obs.state.dg5f_position]
        ).astype(np.float32)
        batch: dict[str, torch.Tensor] = {
            "observation.state": torch.from_numpy(state_vec)
            .unsqueeze(0)
            .to(self._device),
        }
        for name in self._cam_names:
            img = obs.images.get(name)
            if img is None:
                raise RuntimeError(
                    f"camera '{name}' has no frame yet — refusing to act on stale obs"
                )
            # HxWx3 uint8 -> 1x3xHxW float32 in [0,1]
            t = (
                torch.from_numpy(img)
                .permute(2, 0, 1)
                .unsqueeze(0)
                .to(self._device, dtype=torch.float32)
                / 255.0
            )
            batch[f"observation.images.{name}"] = t
        return batch

    def _action_from_tensor(self, action_t: torch.Tensor) -> Action:
        """ACTPolicy.select_action returns (1, action_dim). Split into our 26-dim layout."""
        a = action_t.detach().cpu().numpy().reshape(-1)
        if a.size != self._ur_dof + self._hand_dof:
            raise ValueError(
                f"policy emitted {a.size}-dim action; expected "
                f"{self._ur_dof + self._hand_dof} (= {self._ur_dof} UR + {self._hand_dof} dg5f)"
            )
        return Action(
            ur10e_position=a[: self._ur_dof].astype(np.float32),
            dg5f_position=a[self._ur_dof :].astype(np.float32),
        )

    def run(self, max_seconds: float | None = None) -> int:
        """Drive the robot until Ctrl-C or max_seconds elapses. Returns step count."""
        self._io.wait_until_ready(timeout_s=15.0)
        self._policy.reset()
        period = 1.0 / self._rate_hz
        n_steps = 0
        t0 = time.monotonic()
        next_tick = t0
        try:
            while not self._stop:
                if max_seconds is not None and (time.monotonic() - t0) >= max_seconds:
                    break
                next_tick += period
                obs = self._io.get_observation()
                batch = self._obs_to_batch(obs)
                with torch.inference_mode():
                    action_t = self._policy.select_action(batch)
                self._io.send_action(self._action_from_tensor(action_t))
                n_steps += 1

                sleep_for = next_tick - time.monotonic()
                if sleep_for > 0:
                    time.sleep(sleep_for)
                else:
                    next_tick = time.monotonic()
        finally:
            pass
        return n_steps

    def shutdown(self) -> None:
        self._io.shutdown()

    def __enter__(self) -> "ACTRunner":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.shutdown()
