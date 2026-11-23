"""Figure for test-logs/: fall rate by riser height (both policies) and by terrain (walking policy)."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e6e5e1"
BLUE, ORANGE = "#2a78d6", "#eb6834"
plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
    "axes.grid": True, "grid.color": GRID, "axes.axisbelow": True, "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left"})
walk = json.loads((HERE / "walking_stairs_v5_model9800/summary.json").read_text())
climb = json.loads((HERE / "climb_v5_model11600/summary.json").read_text())

fig, (a, b) = plt.subplots(1, 2, figsize=(13, 4.8), constrained_layout=True, gridspec_kw={"width_ratios": [1.15, 1]})
for s, color, marker, label in ((walk, BLUE, "o", "Đi bộ (stairs_v5)"), (climb, ORANGE, "s", "Leo thang (climb_v5)")):
    lo, hi = s["riser_range_cm"]
    xs, ys = [], []
    for r, v in s["by_row"].items():
        if v:
            xs.append(lo + (hi - lo) * (int(r) + 0.5) / 10); ys.append(v["fall_rate_pct"])
    a.plot(xs, ys, color=color, linewidth=2, marker=marker, markersize=7, label=label,
           markeredgecolor=SURFACE, markeredgewidth=1.5)
    a.annotate(label, (xs[-1], ys[-1]), xytext=(6, 0 if ys[-1] > 1 else 9), textcoords="offset points", va="center", color=INK2, fontsize=9)
a.set_xlabel("độ cao bậc (cm)")
a.set_ylabel("tỉ lệ ngã (%)")
a.set_xlim(0.8, 5.6)
a.set_ylim(0, 20)
a.legend(loc="upper left", frameon=False)
a.set_title("Tỉ lệ ngã theo độ cao bậc (chỉ ô có bậc thang)")

terr = walk["by_terrain"]
names = {"flat": "sàn phẳng", "pyramid_stairs": "kim tự tháp bậc (đi xuống)",
         "inverted_pyramid_stairs": "hố bậc (đi lên)", "random_grid": "sàn lồi lõm", "pyramid_slope": "dốc (heightfield)*"}
keys = list(terr)
vals = [terr[k]["fall_rate_pct"] for k in keys]
y = list(range(len(keys)))[::-1]
b.barh(y, vals, color=BLUE, height=0.6)
for yi, v, k in zip(y, vals, keys):
    b.text(v + 1, yi, f"{v:.1f}%  ({terr[k]['fell']}/{terr[k]['envs']})", va="center", fontsize=9, color=INK2)
b.set_yticks(y, [names.get(k, k) for k in keys], fontsize=9)
b.tick_params(axis="y", colors=INK2, length=0)
b.grid(axis="y", visible=False)
b.set_xlim(0, 100)
b.set_xlabel("tỉ lệ ngã (%)")
b.set_title("Policy đi bộ: tỉ lệ ngã theo loại địa hình")
fig.text(0.99, 0.005, "* Dốc dựng bằng khối hộp trên CPU MuJoCo: 0/9 lần ngã — xem ramp_cpu_crosscheck.txt", ha="right",
         fontsize=8, color=INK2)
fig.get_layout_engine().set(rect=(0, 0.04, 1, 0.96))
fig.suptitle("Test 1000 môi trường mô phỏng mỗi policy (GPU, 20 s mỗi môi trường)", x=0.01, ha="left", fontweight="bold")
fig.savefig(HERE / "test_results.png", dpi=160)
print("ok")
