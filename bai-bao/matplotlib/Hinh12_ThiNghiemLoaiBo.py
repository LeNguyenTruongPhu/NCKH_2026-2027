# -*- coding: utf-8 -*-
"""
Hình 12 – Thí nghiệm loại bỏ:
(a) thành phần phạt liên quan khớp đầu theo vòng lặp (climb_v4 và climb_v5),
(b) tỉ lệ episode kết thúc do ngã trong 50 vòng cuối của từng nhánh.

Chạy:   python Hinh12_ThiNghiemLoaiBo.py
Cần:    matplotlib (numpy đi kèm matplotlib), không cần pandas.
Kết quả: Hinh12_ThiNghiemLoaiBo.png (300 dpi, chèn vào Word) và Hinh12_ThiNghiemLoaiBo.svg (ảnh vector),
         lưu ngay cạnh file script.

Số liệu đọc trực tiếp từ project NCKH_2026-2027:
    training-logs/runs/<thời gian>_biped60_<tên>/scalars.csv của 13 lần huấn luyện
"""
import csv
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                      # vẽ không cần cửa sổ
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.text import Text
from matplotlib.ticker import FixedFormatter, ScalarFormatter

# ------------------------------------------------------------------ đường dẫn
# Script nằm ở NCKH_2026-2027/bai-bao/matplotlib -> thư mục gốc của project ở hai cấp trên.
# Nếu chuyển script đi chỗ khác, sửa ROOT thành đường dẫn đầy đủ, ví dụ:
#     ROOT = Path(r"D:\NCKH2026-2027\NCKH_2026-2027")
ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = ROOT / "training-logs" / "runs"
TEST_DIR = ROOT / "test-logs"

# ------------------------------------------------------------------ kiểu chữ, màu
plt.rcParams.update({
    "font.family": "DejaVu Sans",          # có sẵn trong matplotlib, đủ dấu tiếng Việt
    "font.size": 9,
    "axes.titlesize": 9.5,
    "axes.titleweight": "bold",
    "axes.labelsize": 9,
    "axes.labelcolor": "#333333",
    "axes.edgecolor": "#9a9a9a",
    "axes.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": "#e6e6e6",
    "grid.linewidth": 0.6,
    "xtick.color": "#555555",
    "ytick.color": "#555555",
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "legend.frameon": False,
    "lines.linewidth": 1.5,
    "text.color": "#191919",
})
C1, C2, C3 = "#257de0", "#f47230", "#00b894"    # xanh: đi bộ · cam: kỹ năng leo · xanh lá: sàn phẳng
GRAY, LIGHT1, LIGHT2 = "#9c9c9c", "#a9cbf3", "#f9c2a6"


# ------------------------------------------------------------------ tiện ích
def read_rows(path):
    """Đọc file CSV thành danh sách dict (tên cột đã bỏ khoảng trắng thừa)."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f, skipinitialspace=True)
        header = [h.strip() for h in next(reader)]
        return [dict(zip(header, (v.strip() for v in row))) for row in reader if row]


def num(v):
    """Chuỗi -> số thực; ô trống thành NaN."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return np.nan


def find_run(name):
    found = sorted(RUNS_DIR.glob(f"*biped60_{name}"))
    if len(found) != 1:
        raise SystemExit(f"Không tìm thấy (hoặc tìm thấy nhiều hơn một) thư mục log cho '{name}' trong {RUNS_DIR}")
    return found[0] / "scalars.csv"


def load_run(name, columns=None, prefix=None):
    """Đọc scalars.csv của một lần huấn luyện -> dict {cột: mảng numpy}.
    columns: danh sách cột cần lấy; prefix: lấy mọi cột bắt đầu bằng chuỗi này."""
    with open(find_run(name), newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        keep = list(columns or [])
        if prefix:
            keep += [c for c in reader.fieldnames if c.startswith(prefix)]
        data = {c: [] for c in ["iteration"] + keep}
        for row in reader:
            for c in data:
                data[c].append(num(row.get(c)))
    return {c: np.array(v) for c, v in data.items()}


def moving_average(y, w):
    """Trung bình trượt về phía trước, bỏ qua ô trống (giống pandas rolling(w, min_periods=1).mean())."""
    ok = ~np.isnan(y)
    c = np.cumsum(np.insert(np.where(ok, y, 0.0), 0, 0.0))
    k = np.cumsum(np.insert(ok.astype(float), 0, 0.0))
    n = np.arange(1, len(y) + 1)
    lo = np.maximum(n - w, 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return (c[n] - c[lo]) / (k[n] - k[lo])


def wilson(k, n, z=1.96):
    """Tỉ lệ k/n và khoảng tin cậy 95% Wilson."""
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, centre - half), min(1.0, centre + half)


class CommaFormatter(ScalarFormatter):
    """Số trên trục dùng dấu phẩy thập phân (0,5 thay vì 0.5)."""
    def __call__(self, x, pos=None):
        return super().__call__(x, pos).replace(".", ",")


_DECIMAL = re.compile(r"(\d)\.(\d)")


def save(fig, out):
    """Đổi dấu chấm thập phân thành dấu phẩy ở trục và mọi dòng chữ, rồi lưu PNG 300 dpi và SVG."""
    for ax in fig.axes:
        for axis in (ax.xaxis, ax.yaxis):
            f = axis.get_major_formatter()
            if type(f) is ScalarFormatter:
                axis.set_major_formatter(CommaFormatter(useOffset=False))
            elif isinstance(f, FixedFormatter):
                f.seq = [_DECIMAL.sub(r"\1,\2", s) for s in f.seq]
    fig.canvas.draw()
    for t in fig.findobj(Text):
        s = t.get_text()
        if _DECIMAL.search(s):
            t.set_text(_DECIMAL.sub(r"\1,\2", s))
    fig.savefig(f"{out}.png", dpi=300, bbox_inches="tight", pad_inches=0.04, facecolor="white")
    fig.savefig(f"{out}.svg", bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    print(f"Đã lưu {out}.png và {out}.svg")


# ================================================================== vẽ hình
OUT = Path(__file__).resolve().parent / "Hinh12_ThiNghiemLoaiBo"  # ảnh lưu cạnh script
WINDOW = 25                                                     # trung bình trượt cho ô (a)

fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.9), gridspec_kw={"width_ratios": [1.1, 1]})

# ---- (a) thành phần phạt liên quan khớp đầu: climb_v4 (chỉ phạt nghiêng đầu) và climb_v5
ax = axs[0]
d4 = load_run("stairs_climb_v4", ["Episode_Reward/head_roll"])
d5 = load_run("stairs_climb_v5", ["Episode_Reward/head_roll", "Episode_Reward/targets_beyond_limits"])
curves = [  # (dữ liệu, cột, màu, nét, nhãn, dịch nhãn theo trục tung, màu chữ)
    (d4, "Episode_Reward/head_roll", GRAY, (0, (4, 2)), "climb_v4: head_roll", 0.0, "#555555"),
    (d5, "Episode_Reward/head_roll", C1, "-", "climb_v5: head_roll", -0.01, "#191919"),
    (d5, "Episode_Reward/targets_beyond_limits", C2, "-", "climb_v5:\ntargets_beyond_limits", 0.015, "#191919"),
]
for d, c, color, ls, label, dy, tcolor in curves:
    ys = moving_average(d[c], WINDOW)
    ax.plot(d["iteration"], ys, color=color, lw=1.5, ls=ls)
    ax.text(d["iteration"][-1] + 15, ys[-1] + dy, label, fontsize=6.8, va="center", color=tcolor)
ax.set_xlim(10380, 12450)
ax.set_xlabel("Vòng lặp PPO")
ax.set_ylabel("Thành phần phạt (/20 s)")
ax.set_title("(a) Phạt liên quan khớp đầu", loc="left")

# ---- (b) tỉ lệ episode kết thúc do ngã, trung bình 50 vòng lặp cuối của mỗi lần huấn luyện
ax = axs[1]
NAMES = ["stairs_v1", "stairs_v2", "stairs_v3", "stairs_v4", "stairs_v5", "stairs_v6", "stairs_v7",
         "stairs_v8", "stairs_v9b", "climb_v2", "climb_v3", "climb_v4", "climb_v5"]
USED = {"stairs_v2", "stairs_v4", "stairs_v5", "climb_v2", "climb_v5"}
TERM = ["Episode_Termination/fell_over", "Episode_Termination/time_out", "Episode_Termination/out_of_terrain_bounds"]
vals = []
for n in NAMES:
    d = load_run(n.replace("climb", "stairs_climb"), TERM)
    fell, timeout, bounds = (np.nanmean(d[c][-50:]) for c in TERM)
    vals.append(fell / (fell + timeout + bounds) * 100)
y = np.arange(len(NAMES))
colors = [(C2 if "climb" in n else C1) if n in USED else "#cfcfcf" for n in NAMES]
ax.barh(y, vals, color=colors, height=0.62)
for yi, v in zip(y, vals):
    ax.text(v + 0.6, yi, f"{v:.1f}", va="center", fontsize=6.6, color="#333333")
ax.set_yticks(y)
ax.set_yticklabels(NAMES, fontsize=7)
ax.invert_yaxis()
ax.grid(axis="y", visible=False)
ax.set_xlabel("% episode kết thúc do ngã (50 vòng cuối)")
ax.set_xlim(0, 52)
ax.set_title("(b) Tỉ lệ ngã trong huấn luyện", loc="left")

fig.tight_layout(w_pad=1.0)
save(fig, OUT)
