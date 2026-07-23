#!/usr/bin/env bash
# Experiment runner: policy x budget x seed sweep over real manifests.
#
#   sudo ./experiments/run.sh MANIFESTS OUTDIR [options]
#     --policies "semantic tail uniform keyframe"
#     --budgets  "1.0 0.75 0.5 0.375 0.25 0.125"   fraction of stream byte rate
#     --seeds    "0 1 2"    sender shuffle + policy rng seeds
#     --videos   N          limit videos (0 = all in MANIFESTS)
#     --speed    8          time compression
#     --queue-ms 100        AP queue sized from base link rate x this latency
#     --trigger  queue      queue | feedback
#     --rate-spec ""        override proxy rate schedule (RQ2 step tests)
#
# One run dir per (policy, budget, seed): OUTDIR/<policy>-b<budget>-s<seed>/
# Each carries: run.sh args (this cmd), *.run.json (git sha + argv), env.txt,
# events.jsonl (raw), trace.jsonl (raw), summary.json (parsed).
# Requires netns up, or falls back to localhost.
set -euo pipefail

MANIFESTS="$1"; OUTDIR="$2"; shift 2
POLICIES="semantic tail uniform keyframe"
BUDGETS="0.5"
SEEDS="1"
VIDEOS=0
SPEED=8
QUEUE_MS=100
TRIGGER=queue
RATE_SPEC=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --policies) POLICIES="$2"; shift 2 ;;
    --budgets) BUDGETS="$2"; shift 2 ;;
    --seeds) SEEDS="$2"; shift 2 ;;
    --videos) VIDEOS="$2"; shift 2 ;;
    --speed) SPEED="$2"; shift 2 ;;
    --queue-ms) QUEUE_MS="$2"; shift 2 ;;
    --trigger) TRIGGER="$2"; shift 2 ;;
    --rate-spec) RATE_SPEC="$2"; shift 2 ;;
    *) echo "unknown option $1" >&2; exit 1 ;;
  esac
done

cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD"
PY=python3
mkdir -p "$OUTDIR"

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
echo "base stream rate: $BASE_RATE B/s (videos=$VIDEOS speed=x$SPEED queue=${QUEUE_MS}ms)"

env_snapshot() {  # $1 = run dir
  {
    echo "host=$(hostname)"
    echo "date=$(date -Iseconds)"
    echo "git_sha=$(git -C "$PWD/.." rev-parse --short HEAD 2>/dev/null || echo NA)"
    echo "python=$($PY --version 2>&1)"
    echo "kernel=$(uname -sr)"
    echo "manifests=$MANIFESTS base_rate=$BASE_RATE speed=$SPEED queue_ms=$QUEUE_MS"
  } > "$1/env.txt"
}

NS_AP=(); NS_SND=(); NS_RCV=()
# AP_IP: how the SENDER reaches the AP. AP_IP_RCV: how the RECEIVER reaches it
# (for feedback packets). In the netns these are different interfaces of the AP;
# the receiver's namespace cannot route to the sender-side AP IP.
AP_IP=127.0.0.1; AP_IP_RCV=127.0.0.1; RCV_IP=127.0.0.1
if ip netns list 2>/dev/null | grep -q sgw-ap; then
  NS_AP=(ip netns exec sgw-ap); NS_SND=(ip netns exec sgw-snd); NS_RCV=(ip netns exec sgw-rcv)
  AP_IP=10.77.1.1; AP_IP_RCV=10.77.2.1; RCV_IP=10.77.2.2
fi

TOTAL=0; DONE=0
for _ in $POLICIES; do for _ in $BUDGETS; do for _ in $SEEDS; do TOTAL=$((TOTAL+1)); done; done; done

for SEED in $SEEDS; do
  for BUDGET in $BUDGETS; do
    for POLICY in $POLICIES; do
      DONE=$((DONE+1))
      RUN="$OUTDIR/${POLICY}-b${BUDGET}-s${SEED}"
      if [[ -f "$RUN/summary.json" ]]; then
        echo "[$DONE/$TOTAL] skip $POLICY b=$BUDGET s=$SEED (done)"; continue
      fi
      mkdir -p "$RUN"; env_snapshot "$RUN"
      if [[ -n "$RATE_SPEC" ]]; then RATE="$RATE_SPEC"
      else RATE="0:$(awk "BEGIN{printf \"%.0f\", $BUDGET * $BASE_RATE * $SPEED}")"; fi
      echo "[$DONE/$TOTAL] $POLICY b=$BUDGET s=$SEED rate=$RATE"
      "${NS_RCV[@]}" $PY -m semantic_gateway.receiver --manifests "$MANIFESTS" \
        --videos "$VIDEOS" --run-dir "$RUN" --timeout 7200 --proxy-host "$AP_IP_RCV" &
      RCV_PID=$!
      sleep 0.5
      "${NS_AP[@]}" $PY -m semantic_gateway.proxy --policy "$POLICY" \
        --trigger "$TRIGGER" --rate "$RATE" --queue-ms "$QUEUE_MS" --seed "$SEED" \
        --receiver-host "$RCV_IP" --run-dir "$RUN" &
      PROXY_PID=$!
      sleep 0.5
      "${NS_SND[@]}" $PY -m semantic_gateway.sender --manifests "$MANIFESTS" \
        --videos "$VIDEOS" --speed "$SPEED" --seed "$SEED" \
        --proxy-host "$AP_IP" --run-dir "$RUN"
      wait $PROXY_PID $RCV_PID
      $PY -m semantic_gateway.summarize --run-dir "$RUN" --manifests "$MANIFESTS" \
        | grep -E "usable_pct|received_pct|lat_ms_mean" || true
    done
  done
done
echo "sweep complete under $OUTDIR ($TOTAL runs)"
