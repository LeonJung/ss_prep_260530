#!/usr/bin/env bash
# Push a trained checkpoint from the training PC to the controller PC so
# run_policy can pick it up. Run ON THE TRAINING PC, in the repo root.
#
#   scripts/sync_checkpoints.sh                          # push everything in checkpoints/
#   scripts/sync_checkpoints.sh checkpoints/act_run/final/   # one ckpt
#
# Defaults can be overridden with env vars (CONTROLLER, REMOTE_PATH).
set -e

CONTROLLER="${CONTROLLER:-leon@10.42.0.214}"
REMOTE_PATH="${REMOTE_PATH:-~/ai_ws/ss_prep/checkpoints/}"
SRC="${1:-./checkpoints/}"

echo "rsync ${SRC} → ${CONTROLLER}:${REMOTE_PATH}"
exec rsync -avhP --partial "$SRC" "${CONTROLLER}:${REMOTE_PATH}"
