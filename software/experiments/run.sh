#!/usr/bin/env bash
# Experiment runner: policy x budget sweep over real manifests.
#
#   sudo ./experiments/run.sh MANIFESTS OUTDIR [options]
#     --policies "semantic tail uniform keyframe"
#     --budgets  "1.0 0.75 0.5 0.25 0.125"   fraction of stream byte rate
#     --videos   N       limit videos (0 = all)
#     --speed    8       time compression
#     --seed     1       sender shuffle + policy rng seed
#     --trigger  queue   queue | feedback
#     --rate-spec ""     override proxy rate schedule entirely (RQ2 steps)
#
# One run directory per (policy, budget): OUTDIR/<policy>-b<budget>/
# Requires netns up (testbed/netns.sh up) or falls back to localhost.
set -euo pipefail

MANIFESTS="$1"; OUTDIR="$2"; shift 2
POLICIES="semantic tail uniform keyframe"
BUDGETS="0.5"
VIDEOS=0
SPEED=8
SEED=1
TRIGGER=queue
RATE_SPEC=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --policies) POLICIES="$2"; shift 2 ;;
    --budgets) BUDGETS="$2"; shift 2 ;;
    --videos) VIDEOS="$2"; shift 2 ;;
    --speed) SPEED="$2"; shift 2 ;;
    --seed) SEED="$2"; shift 2 ;;
    --trigger) TRIGGER="$2"; shift 2 ;;
    --rate-spec) RATE_SPEC="$2"; shift 2 ;;
    *) echo "unknown option $1" >&2; exit 1 ;;
  esac
done

cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD"
PY=python3

# raw stream byte rate (payload bytes per stream-second) over selected videos
BASE_RATE=$($PY - "$MANIFESTS" "$VIDEOS" <<'EOF'
import json, sys
path, limit = sys.argv[1], int(sys.argv[2])
total_b = total_s = 0.0
with open(path) as fh:
    for k, line in enumerate(fh):
        if limit and k >= limit:
            break
        d = json.loads(line)
        total_b += sum(f[1] for f in d["frames"])
        total_s += len(d["frames"]) / d["fps"]
print(f"{total_b / total_s:.0f}")
EOF
)
echo "base stream rate: $BASE_RATE B/s (videos=$VIDEOS speed=x$SPEED)"

NS_AP=(); NS_SND=(); NS_RCV=()
AP_IP=127.0.0.1; RCV_IP=127.0.0.1
if ip netns list 2>/dev/null | grep -q sgw-ap; then
  NS_AP=(ip netns exec sgw-ap); NS_SND=(ip netns exec sgw-snd); NS_RCV=(ip netns exec sgw-rcv)
  AP_IP=10.77.1.1; RCV_IP=10.77.2.2
fi

for POLICY in $POLICIES; do
  for BUDGET in $BUDGETS; do
    RUN="$OUTDIR/${POLICY}-b${BUDGET}-s${SEED}"
    mkdir -p "$RUN"
    if [[ -n "$RATE_SPEC" ]]; then
      RATE="$RATE_SPEC"
    else
      RATE="0:$(awk "BEGIN{printf \"%.0f\", $BUDGET * $BASE_RATE * $SPEED}")"
    fi
    echo "== $POLICY budget=$BUDGET rate=$RATE seed=$SEED =="
    "${NS_RCV[@]}" $PY -m semantic_gateway.receiver --manifests "$MANIFESTS" \
      --videos "$VIDEOS" --run-dir "$RUN" --timeout 7200 --proxy-host "$AP_IP" &
    RCV_PID=$!
    sleep 0.5
    "${NS_AP[@]}" $PY -m semantic_gateway.proxy --policy "$POLICY" \
      --trigger "$TRIGGER" --rate "$RATE" --seed "$SEED" \
      --receiver-host "$RCV_IP" --run-dir "$RUN" &
    PROXY_PID=$!
    sleep 0.5
    "${NS_SND[@]}" $PY -m semantic_gateway.sender --manifests "$MANIFESTS" \
      --videos "$VIDEOS" --speed "$SPEED" --seed "$SEED" \
      --proxy-host "$AP_IP" --run-dir "$RUN"
    wait $PROXY_PID $RCV_PID
    $PY -m semantic_gateway.summarize --run-dir "$RUN" --manifests "$MANIFESTS" \
      | grep -E "usable_pct|received_pct|lat_ms"
  done
done
echo "runs complete under $OUTDIR"
