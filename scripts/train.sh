#!/usr/bin/env bash
# Train ACT on a recorded LeRobotDataset.
#
# Usage:
#   docker compose run --rm pai_teach bash scripts/train.sh <root> <repo-id> [extra args]
#
# Example:
#   docker compose run --rm pai_teach bash scripts/train.sh \
#       datasets/cabinet_door local/cabinet_door --batch-size 32
#
# Defaults from pai_teach/configs/act.yaml: training_steps=100000,
# batch_size=4, num_workers=4, save_every=5000. Override on the CLI:
#   --steps 50000          shorter run
#   --batch-size 32        bigger batch on the training PC's GPU
#   --num-workers 8        more dataloader workers
#   --device cpu           force CPU
set -e
source /opt/ros/${ROS_DISTRO:-jazzy}/setup.bash

ROOT="${1:?usage: bash scripts/train.sh <root> <repo-id> [extra args]}"
REPO="${2:?repo-id required}"
shift 2

exec python -m scripts.train_act \
    --root "$ROOT" \
    --repo-id "$REPO" \
    "$@"
