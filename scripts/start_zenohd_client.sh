#!/usr/bin/env bash
# Run a local rmw_zenohd on the training PC that connects upstream to the
# controller PC's router. ROS2 nodes on this host then talk to the local
# router and discover the controller PC's topics through it. Way more
# reliable than depending on rmw_zenoh_cpp's session-config env var.
set -e
source /opt/ros/jazzy/setup.bash

CONTROLLER_ROUTER="${CONTROLLER_ROUTER:-tcp/10.42.0.214:7447}"

cat > /tmp/zenohd-client.json5 <<EOF
{
  mode: "router",
  connect: { endpoints: ["${CONTROLLER_ROUTER}"] },
  scouting: {
    multicast: { enabled: false },
    gossip: { enabled: true },
  },
}
EOF

echo "starting local zenohd, upstream=${CONTROLLER_ROUTER}"
exec ros2 run rmw_zenoh_cpp rmw_zenohd --config /tmp/zenohd-client.json5
