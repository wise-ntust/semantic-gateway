#!/usr/bin/env bash
# Three network namespaces: snd --veth-- ap --veth-- rcv
# The proxy (AP) runs in `ap`; tc netem adds propagation delay on the
# ap<->rcv link. Bandwidth is enforced by the proxy's token bucket (that is
# the emulated wireless link rate), NOT by tc, so the AP can observe its own
# queue. Requires root.
#
#   sudo ./netns.sh up [DELAY_MS]
#   sudo ./netns.sh down
#   sudo ip netns exec sgw-ap  <cmd>   # run proxy here
#   sudo ip netns exec sgw-snd <cmd>   # sender: proxy is 10.77.1.1
#   sudo ip netns exec sgw-rcv <cmd>   # receiver: listens on 10.77.2.2
set -euo pipefail

DELAY_MS="${2:-2}"

up() {
  ip netns add sgw-snd
  ip netns add sgw-ap
  ip netns add sgw-rcv
  ip link add v-snd type veth peer name v-aps
  ip link add v-apr type veth peer name v-rcv
  ip link set v-snd netns sgw-snd
  ip link set v-aps netns sgw-ap
  ip link set v-apr netns sgw-ap
  ip link set v-rcv netns sgw-rcv
  ip netns exec sgw-snd ip addr add 10.77.1.2/24 dev v-snd
  ip netns exec sgw-ap  ip addr add 10.77.1.1/24 dev v-aps
  ip netns exec sgw-ap  ip addr add 10.77.2.1/24 dev v-apr
  ip netns exec sgw-rcv ip addr add 10.77.2.2/24 dev v-rcv
  for ns in sgw-snd sgw-ap sgw-rcv; do
    ip netns exec "$ns" ip link set lo up
  done
  ip netns exec sgw-snd ip link set v-snd up
  ip netns exec sgw-ap  ip link set v-aps up
  ip netns exec sgw-ap  ip link set v-apr up
  ip netns exec sgw-rcv ip link set v-rcv up
  ip netns exec sgw-ap  tc qdisc add dev v-apr root netem delay "${DELAY_MS}ms"
  ip netns exec sgw-rcv tc qdisc add dev v-rcv root netem delay "${DELAY_MS}ms"
  echo "netns up: snd(10.77.1.2) -> ap(10.77.1.1 / 10.77.2.1) -> rcv(10.77.2.2), ${DELAY_MS}ms each way"
}

down() {
  for ns in sgw-snd sgw-ap sgw-rcv; do
    ip netns del "$ns" 2>/dev/null || true
  done
  echo "netns down"
}

case "${1:-}" in
  up) up ;;
  down) down ;;
  *) echo "usage: $0 up [delay_ms] | down" >&2; exit 1 ;;
esac
