#!/usr/bin/env bash
# Pull recorded datasets from the controller PC into the training PC.
# Run ON THE TRAINING PC, in the repo root.
#
#   scripts/sync_datasets.sh                       # default user/host/path
#   scripts/sync_datasets.sh --dry-run             # see what would copy
#   CONTROLLER=user@10.42.0.214 scripts/sync_datasets.sh
#
# Assumes SSH key auth between training PC and controller PC.
set -e

CONTROLLER="${CONTROLLER:-leon@10.42.0.214}"
REMOTE_PATH="${REMOTE_PATH:-~/ai_ws/ss_prep/datasets/}"
LOCAL_PATH="${LOCAL_PATH:-./datasets/}"

mkdir -p "$LOCAL_PATH"
echo "rsync from ${CONTROLLER}:${REMOTE_PATH} → ${LOCAL_PATH}"
exec rsync -avhP --partial "$@" \
    "${CONTROLLER}:${REMOTE_PATH}" "${LOCAL_PATH}"
