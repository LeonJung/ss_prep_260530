"""Record N consecutive teleop episodes into a single LeRobotDataset.

Uses ONE Recorder instance so LeRobotDataset.create() fires once and
subsequent episodes append to the same parquet/video tree. Between
episodes, prompts the user to reset the robot and press Enter.

Usage (inside the docker container):
    python -m scripts.record_n_episodes \\
        --config pai_teach/configs/robot.yaml \\
        --repo-id local/<task> \\
        --root datasets/<task> \\
        --task <task> \\
        --max-seconds 30 \\
        --episodes 10 \\
        [--no-dg5f]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pai_teach.data_recorder import Recorder


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, default=Path("pai_teach/configs/robot.yaml"))
    p.add_argument("--repo-id", required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--task", required=True)
    p.add_argument("--max-seconds", type=float, required=True)
    p.add_argument("--episodes", type=int, required=True)
    p.add_argument(
        "--dg5f", action=argparse.BooleanOptionalAction, default=None,
        help="override config.dg5f.enabled",
    )
    return p.parse_args()


def main() -> None:
    args = _parse()
    print(f"[rec_n] target {args.episodes} episodes × {args.max_seconds}s into {args.root}")
    print("[rec_n] reset the robot between episodes; Ctrl-C at the prompt to stop early.")

    with Recorder(
        config_path=args.config,
        repo_id=args.repo_id,
        dataset_root=args.root,
        task=args.task,
        dg5f_enabled=args.dg5f,
    ) as rec:
        for i in range(1, args.episodes + 1):
            try:
                input(f"\n=== episode {i}/{args.episodes} — reset robot, press Enter ===")
            except (EOFError, KeyboardInterrupt):
                print("\n[rec_n] aborted by user before episode start")
                break
            # Recorder.record_episode keeps self._stop=True after a Ctrl-C
            # in a previous run; reset it so a fresh episode can record.
            rec._stop = False
            n = rec.record_episode(max_seconds=args.max_seconds)
            print(f"[rec_n] ep{i}: {n} frames saved")


if __name__ == "__main__":
    main()
