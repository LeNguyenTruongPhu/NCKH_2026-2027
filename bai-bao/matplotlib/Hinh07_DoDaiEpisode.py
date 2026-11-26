# -*- coding: utf-8 -*-
"""
Hình 7 – Độ dài episode (số bước điều khiển, tối đa 1000 = 20 s) theo vòng lặp PPO
cho chuỗi chính sách được dùng (6 lần huấn luyện).

Chạy:   python Hinh07_DoDaiEpisode.py
Cần:    matplotlib (numpy đi kèm matplotlib), không cần pandas.
Kết quả: Hinh07_DoDaiEpisode.png (300 dpi, chèn vào Word)
         Hinh07_DoDaiEpisode.svg (ảnh vector)

Số liệu đọc trực tiếp từ log huấn luyện của project:
    NCKH_2026-2027/training-logs/runs/<thời gian>_biped60_<tên>/scalars.csv
Script nằm ở NCKH_2026-2027/bai-bao/matplotlib nên tự tìm ra thư mục log.
Nếu chuyển script đi chỗ khác, sửa LOG_DIR bên dưới thành đường dẫn đầy đủ, ví dụ:
    LOG_DIR = Path(r"D:\\NCKH2026-2027\\NCKH_2026-2027\\training-logs\\runs")
"""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                      # vẽ không cần cửa sổ
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import MaxNLocator

# ------------------------------------------------------------------ cấu hình
LOG_DIR = Path(__file__).resolve().parents[2] / "training-logs" / "runs"
COLUMN = "Train/mean_episode_length"       # đổi thành "Train/mean_reward" để vẽ Hình 6
Y_LABEL = "Độ dài episode (bước)"
Y_LIM = (0, 1050)                          # trục tung cố định; đặt None để tự co giãn
WINDOW = 50                                # cửa sổ trung bình trượt (số vòng lặp)
OUT = Path(__file__).resolve().parent / "Hinh07_DoDaiEpisode"   # ảnh lưu cạnh script

# (tên lần huấn luyện, tiêu đề ô, checkpoint được chọn)
CHAIN = [
    ("flat_v2",         "(a) flat_v2 – sàn phẳng",            5999),
    ("stairs_v2",       "(b) stairs_v2 – bậc 1–5 cm",          8000),
    ("stairs_v4",       "(c) stairs_v4 – rải đều bậc",         9000),
    ("stairs_v5",       "(d) stairs_v5 – ổn định thân/đầu",    9800),
    ("stairs_climb_v2", "(e) climb_v2 – kỹ năng leo",          10400),
    ("stairs_climb_v5", "(f) climb_v5 – phạt vượt giới hạn",   11600),
]

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
    "text.color": "#191919",
})
C_WALK, C_WALK_LIGHT = "#257de0", "#a9cbf3"     # chính sách đi bộ
C_CLIMB, C_CLIMB_LIGHT = "#f47230", "#f9c2a6"   # kỹ năng leo


# ------------------------------------------------------------------ đọc log
def load_run(name):
    """Trả về (iteration, giá trị COLUMN) của một lần huấn luyện."""
    found = sorted(LOG_DIR.glob(f"*biped60_{name}"))
    if len(found) != 1:
        raise SystemExit(f"Không tìm thấy (hoặc tìm thấy nhiều hơn một) thư mục log cho '{name}' trong {LOG_DIR}")
    it, val = [], []
    with open(found[0] / "scalars.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get(COLUMN):
                it.append(int(float(row["iteration"])))
                val.append(float(row[COLUMN]))
    return np.array(it), np.array(val)


def moving_average(y, w=WINDOW):
    """Trung bình trượt về phía trước (giống pandas rolling(w, min_periods=1).mean())."""
    c = np.cumsum(np.insert(y, 0, 0.0))
    n = np.arange(1, len(y) + 1)
    lo = np.maximum(n - w, 0)
    return (c[n] - c[lo]) / (n - lo)


# ------------------------------------------------------------------ vẽ
fig, axs = plt.subplots(2, 3, figsize=(7.2, 4.4))

for ax, (name, title, ckpt) in zip(axs.flat, CHAIN):
    x, y = load_run(name)
    ys = moving_average(y)
    climb = "climb" in name
    ax.plot(x, y, color=C_CLIMB_LIGHT if climb else C_WALK_LIGHT, lw=0.6)    # từng vòng lặp
    ax.plot(x, ys, color=C_CLIMB if climb else C_WALK, lw=1.6)              # trung bình trượt

    ax.axvline(ckpt, color="#555555", ls=(0, (4, 3)), lw=0.9)               # checkpoint được chọn
    v = ys[x <= ckpt][-1]
    ax.plot([ckpt], [v], "o", ms=5, mfc="white", mec="#333333", mew=1.2, zorder=5)
    ax.annotate(f"model_{ckpt}\n{v:.0f}", (ckpt, v), xytext=(-5, -24),
                textcoords="offset points", ha="right", fontsize=7, color="#333333")

    ax.set_title(title, loc="left", fontsize=8.5)
    ax.ticklabel_format(axis="x", style="plain")
    ax.xaxis.set_major_locator(MaxNLocator(4))
    if Y_LIM:
        ax.set_ylim(*Y_LIM)

for ax in axs[1]:
    ax.set_xlabel("Vòng lặp PPO")
for ax in axs[:, 0]:
    ax.set_ylabel(Y_LABEL)

fig.tight_layout(h_pad=1.2, w_pad=0.8)
fig.savefig(f"{OUT}.png", dpi=300, bbox_inches="tight", pad_inches=0.04, facecolor="white")
fig.savefig(f"{OUT}.svg", bbox_inches="tight", pad_inches=0.04)
print(f"Đã lưu {OUT}.png và {OUT}.svg")
