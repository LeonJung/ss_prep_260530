"""Entry point: train an ACT policy on a recorded LeRobot dataset.

Usage:
    python -m scripts.train_act \\
        --config pai_teach/configs/act.yaml \\
        [--repo-id leonjung/pai_teach_demos] \\
        [--root datasets/pai_teach_demos] \\
        [--steps 50]            # sanity override

Inside the docker container:
    docker compose run --rm pai_teach \\
        python -m scripts.train_act --config pai_teach/configs/act.yaml --steps 50
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pai_teach.policy.act.config import ACTRunConfig


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--config", type=Path, default=Path("pai_teach/configs/act.yaml"),
        help="ACT YAML config",
    )
    p.add_argument("--repo-id", default=None, help="override dataset.repo_id")
    p.add_argument("--root", type=Path, default=None, help="override dataset.root")
    p.add_argument(
        "--steps", type=int, default=None,
        help="override training_steps (useful for sanity runs)",
    )
    p.add_argument(
        "--device", default=None,
        help="override device (e.g. cpu)",
    )
    p.add_argument(
        "--num-workers", type=int, default=None,
        help="override DataLoader num_workers (set 0 for tiny datasets / sanity runs)",
    )
    p.add_argument(
        "--batch-size", type=int, default=None,
        help="override batch_size",
    )
    return p.parse_args()


def main() -> None:
    args = _parse()
    run_cfg = ACTRunConfig.from_yaml(args.config)
    if args.repo_id:
        run_cfg.repo_id = args.repo_id
    if args.root is not None:
        run_cfg.dataset_root = args.root
    if args.device is not None:
        run_cfg.device = args.device
    if args.num_workers is not None:
        run_cfg.num_workers = args.num_workers
    if args.batch_size is not None:
        run_cfg.batch_size = args.batch_size

    # Defer heavy import until after CLI parsing.
    from pai_teach.policy.act.train import train

    train(run_cfg, override_steps=args.steps)


if __name__ == "__main__":
    main()
