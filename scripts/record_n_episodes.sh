#!/usr/bin/env bash
# Wrap scripts/record_n_episodes.py with the ROS source step.
#
# Usage (training PC):
#   docker compose run --rm pai_teach bash scripts/record_n_episodes.sh \
#       local/<task> datasets/<task> <task_name> <secs_per_ep> <n_episodes>
set -e
source /opt/ros/${ROS_DISTRO:-jazzy}/setup.bash

REPO="${1:?usage: ... <repo-id> <root> <task> <max_seconds> <episodes>}"
ROOT="${2:?root required}"
TASK="${3:?task required}"
SECS="${4:?max_seconds required}"
N="${5:?episodes required}"

exec python -m scripts.record_n_episodes \
    --repo-id "$REPO" \
    --root "$ROOT" \
    --task "$TASK" \
    --max-seconds "$SECS" \
    --episodes "$N" \
    --no-dg5f
