"""Generate a tiny synthetic LeRobotDataset for sanity-checking train_act.

No robot, no cameras — just random observations + smooth-ish actions in the
correct schema. Used to verify the docker image, lerobot install, and the
ACT training loop end-to-end before running real teleop.

Usage (inside the docker container):
    python -m scripts.make_dummy_dataset \\
        --root datasets/dummy \\
        --repo-id local/dummy \\
        --episodes 2 \\
        --frames 64
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import yaml

from pai_teach.data_recorder.lerobot_writer import CameraInfo, LeRobotWriter
from pai_teach.ros2_bridge.types import Action, Observation, RobotState


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--repo-id", default="local/dummy")
    p.add_argument(
        "--robot-config",
        type=Path,
        default=Path("pai_teach/configs/robot.yaml"),
    )
    p.add_argument("--episodes", type=int, default=2)
    p.add_argument("--frames", type=int, default=64)
    p.add_argument("--task", default="dummy_pick")
    p.add_argument("--seed", type=int, default=0)
    return p.parse_args()


def _random_obs(
    ur_dof: int, hand_dof: int, cams: list[CameraInfo], rng: np.random.Generator
) -> Observation:
    state = RobotState(
        ur10e_position=rng.standard_normal(ur_dof).astype(np.float32) * 0.1,
        ur10e_velocity=rng.standard_normal(ur_dof).astype(np.float32) * 0.05,
        dg5f_position=rng.standard_normal(hand_dof).astype(np.float32) * 0.3,
        dg5f_velocity=rng.standard_normal(hand_dof).astype(np.float32) * 0.1,
        dg5f_effort=rng.standard_normal(hand_dof).astype(np.float32) * 0.1,
    )
    images = {
        cam.name: rng.integers(0, 256, size=(cam.height, cam.width, 3), dtype=np.uint8)
        for cam in cams
    }
    return Observation(state=state, images=images)


def main() -> None:
    args = _parse()
    cfg = yaml.safe_load(args.robot_config.read_text())
    ur_names = cfg["ur10e"]["joint_names"]
    hand_names = cfg["dg5f"]["joint_names"]
    cams = [
        CameraInfo(name=c["name"], height=int(c["height"]), width=int(c["width"]))
        for c in cfg["cameras"]
    ]
    writer = LeRobotWriter(
        repo_id=args.repo_id,
        root=args.root,
        fps=int(cfg.get("record_rate_hz", 30)),
        ur10e_joint_names=ur_names,
        dg5f_joint_names=hand_names,
        cameras=cams,
        use_videos=bool(cfg.get("use_videos", True)),
    )
    rng = np.random.default_rng(args.seed)
    for ep in range(args.episodes):
        prev_obs = _random_obs(len(ur_names), len(hand_names), cams, rng)
        for _ in range(args.frames):
            obs = _random_obs(len(ur_names), len(hand_names), cams, rng)
            action = Action(
                ur10e_position=obs.state.ur10e_position.copy(),
                dg5f_position=obs.state.dg5f_position.copy(),
            )
            writer.add_frame(prev_obs, action, task=args.task)
            prev_obs = obs
        writer.save_episode()
        print(f"[dummy] episode {ep + 1}/{args.episodes} saved ({args.frames} frames)")
    print(f"[dummy] wrote dataset to {args.root}")


if __name__ == "__main__":
    main()
