#!/usr/bin/env bash
# Full record -> train -> deploy sanity inside the docker container.
# No real robot needed: mock publisher + zenoh router are spawned in the
# background, and everything runs with --no-dg5f.
#
# Usage:  docker compose run --rm pai_teach bash scripts/sanity_full_cycle.sh
set -e
source /opt/ros/jazzy/setup.bash

echo "=== starting zenoh router ==="
ros2 run rmw_zenoh_cpp rmw_zenohd > /tmp/zenohd.log 2>&1 &
ROUTER=$!
sleep 2

echo "=== starting mock publisher (no dg5f) ==="
python -m scripts.mock_robot_publisher --no-dg5f > /tmp/mock.log 2>&1 &
MOCK=$!
sleep 3

trap "kill $MOCK $ROUTER 2>/dev/null || true" EXIT

echo "=== record_demo (5s) ==="
rm -rf datasets/sanity
python -m scripts.record_demo --no-dg5f --repo-id local/sanity \
    --root datasets/sanity --task arm_only --max-seconds 5

echo "=== train_act (50 step, batch=2) ==="
python -m scripts.train_act --repo-id local/sanity --root datasets/sanity \
    --steps 50 --num-workers 0 --batch-size 2

echo "=== run_policy (5s) ==="
python -m scripts.run_policy --no-dg5f \
    --checkpoint checkpoints/act_run/final --max-seconds 5

echo "=== ALL GREEN ==="
