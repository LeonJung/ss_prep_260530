"""Entry point: record a teleop demonstration into a LeRobot-format dataset.

Usage:
    python -m scripts.record_demo \\
        --config pai_teach/configs/robot.yaml \\
        --repo-id leonjung/pai_teach_demos \\
        --root datasets/pai_teach_demos \\
        --task pick_and_place \\
        --max-seconds 30

The teleop stack (ur10e_teleop_real_py + dg5f_hand_bringup + realsense2_camera)
must be running before invoking this. The recorder only consumes their topics.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pai_teach.data_recorder import Recorder


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--config",
        type=Path,
        default=Path("pai_teach/configs/robot.yaml"),
        help="robot.yaml describing topics, joint order, cameras",
    )
    p.add_argument(
        "--repo-id",
        required=True,
        help="LeRobotDataset repo_id (e.g. leonjung/pai_teach_demos)",
    )
    p.add_argument(
        "--root",
        type=Path,
        required=True,
        help="local dataset root directory",
    )
    p.add_argument(
        "--task",
        required=True,
        help="task string baked into every frame's metadata",
    )
    p.add_argument(
        "--max-seconds",
        type=float,
        default=None,
        help="auto-stop after this many seconds (Ctrl-C stops earlier)",
    )
    return p.parse_args()


def main() -> None:
    args = _parse()
    print(f"[record_demo] config={args.config} task={args.task} root={args.root}")
    print("[record_demo] Press Ctrl-C to stop recording.")
    with Recorder(
        config_path=args.config,
        repo_id=args.repo_id,
        dataset_root=args.root,
        task=args.task,
    ) as rec:
        n = rec.record_episode(max_seconds=args.max_seconds)
        print(f"[record_demo] saved episode with {n} frames")


if __name__ == "__main__":
    main()
