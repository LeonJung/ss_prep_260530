"""Entry point: load a trained ACT checkpoint and drive the robot.

The teleop stack MUST be off (no other publisher on the UR10E JTC action
or the dg5f rj_dg_pospid/reference topic) before running this — otherwise
two sources are commanding the same controller.

Usage (inside the docker container, ROS env sourced):
    python -m scripts.run_policy \\
        --checkpoint checkpoints/act_run/final \\
        --config pai_teach/configs/robot.yaml \\
        [--rate 30] [--max-seconds 30]
"""

from __future__ import annotations

import argparse
from pathlib import Path


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--checkpoint", type=Path, required=True,
        help="Path to a LeRobot ACTPolicy save_pretrained directory "
             "(contains config.json + model.safetensors)",
    )
    p.add_argument(
        "--config", type=Path, default=Path("pai_teach/configs/robot.yaml"),
        help="robot.yaml describing topics, joint order, cameras",
    )
    p.add_argument(
        "--device", default="cuda",
        help="torch device for inference ('cuda' or 'cpu')",
    )
    p.add_argument(
        "--rate", type=float, default=None,
        help="control loop rate (Hz); default = record_rate_hz from robot.yaml",
    )
    p.add_argument(
        "--max-seconds", type=float, default=None,
        help="auto-stop after this many seconds (Ctrl-C stops earlier)",
    )
    return p.parse_args()


def main() -> None:
    args = _parse()
    print(f"[run_policy] checkpoint={args.checkpoint} device={args.device}")
    print("[run_policy] WARNING: teleop must NOT be running on the same controllers.")
    print("[run_policy] Press Ctrl-C to stop.")

    # Defer heavy imports until after CLI parsing.
    from pai_teach.policy.runner import ACTRunner

    with ACTRunner(
        checkpoint_path=args.checkpoint,
        robot_config_path=args.config,
        device=args.device,
        rate_hz=args.rate,
    ) as runner:
        n = runner.run(max_seconds=args.max_seconds)
        print(f"[run_policy] sent {n} action steps")


if __name__ == "__main__":
    main()
