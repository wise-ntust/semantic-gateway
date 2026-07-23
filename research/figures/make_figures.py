"""Render REPORT.md figures from experiment data. Okabe-Ito CVD-safe palette."""
import csv, json, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import LogLocator

REPO = Path(__file__).resolve().parents[2]  # research/figures/ -> repo root
EXP = REPO / "research/experiments"
FIG = REPO / "research/figures"
FIG.mkdir(parents=True, exist_ok=True)

# Okabe-Ito, fixed order by entity (never cycled)
C = {"semantic": "#0072B2", "uniform": "#E69F00",
     "keyframe": "#009E73", "tail": "#D55E00"}
plt.rcParams.update({"font.size": 11, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True,
                     "grid.alpha": 0.25, "figure.dpi": 130})

# ---- Fig 1: RQ1 accuracy vs budget ----------------------------------------
rows = list(csv.DictReader(open(EXP / "2026-07-23-rq1-policy-sweep/agg.csv")))
data = {}
for r in rows:
    data.setdefault(r["policy"], []).append(
        (float(r["budget"]), float(r["top1_mean"]), float(r["top1_std"])))
fig, ax = plt.subplots(figsize=(6.4, 4.2))
for pol in ["semantic", "uniform", "keyframe", "tail"]:
    pts = sorted(data[pol])
    xs = [p[0] * 100 for p in pts]
    ys = [p[1] * 100 for p in pts]
    es = [p[2] * 100 for p in pts]
    lw = 2.6 if pol == "semantic" else 1.8
    ax.errorbar(xs, ys, yerr=es, marker="o", ms=6, lw=lw, color=C[pol],
                capsize=3, label=("semantic (ours)" if pol == "semantic" else pol),
                zorder=(5 if pol == "semantic" else 3))
    ax.annotate(("semantic (ours)" if pol == "semantic" else pol),
                (xs[-1], ys[-1]), textcoords="offset points", xytext=(8, 0),
                va="center", color=C[pol], fontsize=9.5,
                fontweight=("bold" if pol == "semantic" else "normal"))
ax.axhline(95.7, ls="--", lw=1, color="#666", zorder=1)
ax.annotate("clean-video ceiling 95.7%", (13, 95.7), textcoords="offset points",
            xytext=(0, 4), color="#666", fontsize=8.5)
ax.set_xlabel("Bandwidth budget (% of stream rate)")
ax.set_ylabel("Top-1 accuracy (%)")
ax.set_title("RQ1: task-aware dropping preserves accuracy under scarcity")
ax.set_xlim(8, 108); ax.set_ylim(-3, 100)
fig.tight_layout(); fig.savefig(FIG / "rq1_accuracy_vs_budget.png",
                                bbox_inches="tight"); plt.close(fig)

# ---- Fig 2: RQ3 bytes per clip vs split point -----------------------------
splits = ["stem", "layer1", "layer2", "layer3", "layer4", "avgpool"]
by = []
for s in splits:
    d = json.load(open(EXP / f"2026-07-23-rq3-frame-vs-feature/feat_{s}_int8.json"))
    by.append(d["bytes_per_clip"])
frame_ref = 24186
fig, ax = plt.subplots(figsize=(6.4, 4.2))
bars = ax.bar(splits, by, color="#0072B2", width=0.62, zorder=3)
for b in bars:
    b.set_edgecolor("white"); b.set_linewidth(0.5)
ax.axhline(frame_ref, color="#D55E00", lw=2, zorder=4)
ax.annotate("frame path (16 compressed frames = 24 KB)", (5.4, frame_ref),
            ha="right", va="bottom", color="#D55E00", fontsize=9,
            textcoords="offset points", xytext=(0, 3))
ax.set_yscale("log")
ax.set_ylabel("Feature bytes per clip (log scale)")
ax.set_xlabel("Split point (sender runs everything up to here)")
ax.set_title("RQ3: features beat frames only at avgpool (whole net at sender)")
for b, v in zip(bars, by):
    ax.annotate(f"{v/1000:.0f}KB" if v >= 1000 else f"{v}B",
                (b.get_x() + b.get_width() / 2, v), ha="center", va="bottom",
                fontsize=8.5, color="#333", textcoords="offset points",
                xytext=(0, 2))
fig.tight_layout(); fig.savefig(FIG / "rq3_bytes_vs_split.png",
                                bbox_inches="tight"); plt.close(fig)

# ---- Fig 3: RQ2 pressure level over time ----------------------------------
def level_series(path):
    ts, lv = [0.0], [0]
    rate_steps = []
    for line in open(path):
        e = json.loads(line)
        if e.get("ev") == "level":
            ts.append(e["t"]); lv.append(e["level"])
        elif e.get("ev") == "rate":
            rate_steps.append((e["t"], e["bps"]))
    ts.append(max(ts) + 5); lv.append(lv[-1])
    return ts, lv, rate_steps

import tarfile, tempfile
_tmp = Path(tempfile.mkdtemp())
with tarfile.open(EXP / "2026-07-23-rq2-trigger-latency/traces.tgz") as tf:
    tf.extractall(_tmp)
qx, qy, steps = level_series(_tmp / "queue/semantic-bstep-s2/events.jsonl")
fx, fy, _ = level_series(_tmp / "feedback/semantic-bstep-s4/events.jsonl")
fig, ax = plt.subplots(figsize=(6.4, 4.0))
ax.step(qx, qy, where="post", color=C["semantic"], lw=2.2, label="queue-depth (local)")
ax.step(fx, fy, where="post", color=C["tail"], lw=2.2, label="loss-feedback (end-to-end)")
for t in [15, 35]:
    ax.axvline(t, ls=":", color="#888", lw=1)
ax.annotate("bandwidth\ndrops", (15, 3.2), fontsize=8.5, color="#555", ha="center")
ax.annotate("bandwidth\nrecovers", (35, 3.2), fontsize=8.5, color="#555", ha="center")
ax.set_xlabel("Time (s, real-time)")
ax.set_ylabel("Drop pressure level")
ax.set_yticks([0, 1, 2, 3])
ax.set_title("RQ2: queue signal recovers; loss signal latches at max")
ax.set_xlim(0, min(max(qx), 90)); ax.set_ylim(-0.2, 3.8)
ax.legend(loc="center right", frameon=False, fontsize=9.5)
fig.tight_layout(); fig.savefig(FIG / "rq2_pressure_over_time.png",
                                bbox_inches="tight"); plt.close(fig)

print("wrote:", *[p.name for p in sorted(FIG.glob("*.png"))])
