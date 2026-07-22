#!/usr/bin/env bash
# Miniature end-to-end run through the real harness (G3 smoke experiment).
# Synthetic manifests, 4 videos, semantic vs tail, 50% bandwidth budget.
# Run on the sandbox from software/: sudo ./experiments/smoke.sh
set -euo pipefail

cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD"
PY=python3
OUT="${SMOKE_OUT:-/tmp/sgw-smoke}"
SPEED=8
# synthetic stream is ~225 KB/s of video; 50% budget, wall-clock rate = 0.5 * 225e3 * SPEED
RATE="0:$(awk "BEGIN{print 0.5 * 225e3 * $SPEED}")"

rm -rf "$OUT"; mkdir -p "$OUT"
$PY -m semantic_gateway.manifest --out "$OUT/manifests.jsonl" --videos 4 --frames 240

NS_AP=(); NS_SND=(); NS_RCV=()
if ip netns list 2>/dev/null | grep -q sgw-ap; then
  NS_AP=(ip netns exec sgw-ap); NS_SND=(ip netns exec sgw-snd); NS_RCV=(ip netns exec sgw-rcv)
  AP_IP=10.77.1.1; RCV_IP=10.77.2.2
else
  echo "note: netns not up, running on localhost"
  AP_IP=127.0.0.1; RCV_IP=127.0.0.1
fi

for POLICY in ${SMOKE_POLICIES:-semantic tail uniform keyframe}; do
  RUN="$OUT/$POLICY"
  mkdir -p "$RUN"
  echo "== policy: $POLICY =="
  "${NS_RCV[@]}" $PY -m semantic_gateway.receiver --manifests "$OUT/manifests.jsonl" \
    --run-dir "$RUN" --timeout 120 --proxy-host "$AP_IP" &
  RCV_PID=$!
  sleep 0.5
  "${NS_AP[@]}" $PY -m semantic_gateway.proxy --policy "$POLICY" --trigger queue \
    --rate "$RATE" --receiver-host "$RCV_IP" --run-dir "$RUN" &
  PROXY_PID=$!
  sleep 0.5
  "${NS_SND[@]}" $PY -m semantic_gateway.sender --manifests "$OUT/manifests.jsonl" \
    --speed $SPEED --seed 1 --proxy-host "$AP_IP" --run-dir "$RUN"
  wait $PROXY_PID $RCV_PID
  $PY -m semantic_gateway.summarize --run-dir "$RUN" --manifests "$OUT/manifests.jsonl"
done

echo "smoke done: $OUT/{semantic,tail}/summary.json"
