#!/usr/bin/env bash
# Run on the CONTROLLER PC (10.42.0.214). Brings up rmw_zenohd in router
# mode and tells it to connect outward to the training PC's router at
# 10.42.0.1:7447. This direction (controller→training) is what we found
# actually works end-to-end on the lab network — the reverse fails
# silently when multicast scout is filtered.
#
# On the training PC side: just `ros2 run rmw_zenoh_cpp rmw_zenohd`
# with no special config. The controller will dial in to it.
#
# Override the training PC endpoint with TRAINING_ROUTER if it moves:
#   TRAINING_ROUTER=tcp/10.42.0.9:7447 scripts/start_zenohd_controller.sh
set -e
source /opt/ros/jazzy/setup.bash

TRAINING_ROUTER="${TRAINING_ROUTER:-tcp/10.42.0.1:7447}"

cat > /tmp/zenohd-controller.json5 <<EOF
{
  mode: "router",
  connect: { endpoints: ["${TRAINING_ROUTER}"] },
  scouting: {
    multicast: { enabled: true },
    gossip: { enabled: true },
  },
}
EOF

echo "starting controller-PC zenohd, will connect to ${TRAINING_ROUTER}"
exec ros2 run rmw_zenoh_cpp rmw_zenohd --config /tmp/zenohd-controller.json5
