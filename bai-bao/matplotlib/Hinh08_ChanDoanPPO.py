# -*- coding: utf-8 -*-
"""
Hình 8 – Các đại lượng nội tại của PPO cho flat_v2 (xanh) và climb_v5 (cam).

Chạy:   python Hinh08_ChanDoanPPO.py
Cần:    matplotlib (numpy đi kèm matplotlib), không cần pandas.
Kết quả: Hinh08_ChanDoanPPO.png (300 dpi, chèn vào Word)
         Hinh08_ChanDoanPPO.svg (ảnh vector)

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
from matplotlib.ticker import ScalarFormatter

# ------------------------------------------------------------------ cấu hình
LOG_DIR = Path(__file__).resolve().parents[2] / "training-logs" / "runs"
OUT = Path(__file__).resolve().parent / "Hinh08_ChanDoanPPO"   # ảnh lưu cạnh script
WINDOW = 25                                # cửa sổ trung bình trượt (số vòng lặp)

# hai lần huấn luyện được so sánh: (tên thư mục, nhãn chú giải, màu)
RUNS = [("flat_v2", "flat_v2", "#257de0"),
        ("stairs_climb_v5", "climb_v5", "#f47230")]

# (cột trong scalars.csv, tiêu đề ô, trục tung logarit?)
PANELS = [
    ("Loss/value",         "(a) Mất mát giá trị $L^{V}$",      True),
    ("Loss/surrogate",     "(b) Mất mát surrogate",            False),
    ("Loss/entropy",       "(c) Entropy chính sách",           False),
    ("Policy/mean_std",    "(d) Độ lệch chuẩn $\\sigma$",      False),
    ("Loss/learning_rate", "(e) Tốc độ học thích nghi",        True),
    ("Loss/symmetry",      "(f) Mất mát đối xứng $L^{sym}$",   False),
]

# ------------------------------------------------------------------ kiểu chữ
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
    "text.color": "#191919",
})


class CommaFormatter(ScalarFormatter):
    """Số thập phân dùng dấu phẩy theo cách viết tiếng Việt (0,20 thay vì 0.20)."""
    def __call__(self, x, pos=None):
        return super().__call__(x, pos).replace(".", ",")


# ------------------------------------------------------------------ đọc log
def load_run(name, columns):
    """Trả về dict: 'iteration' và từng cột cần dùng, dạng mảng numpy."""
    found = sorted(LOG_DIR.glob(f"*biped60_{name}"))
    if len(found) != 1:
        raise SystemExit(f"Không tìm thấy (hoặc tìm thấy nhiều hơn một) thư mục log cho '{name}' trong {LOG_DIR}")
    data = {c: [] for c in ["iteration"] + columns}
    with open(found[0] / "scalars.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for c in data:
                v = row.get(c, "")
                data[c].append(float(v) if v not in ("", None) else np.nan)
    return {c: np.array(v) for c, v in data.items()}


def moving_average(y, w=WINDOW):
    """Trung bình trượt về phía trước, bỏ qua ô trống (giống pandas rolling(w, min_periods=1).mean())."""
    ok = ~np.isnan(y)
    c = np.cumsum(np.insert(np.where(ok, y, 0.0), 0, 0.0))
    k = np.cumsum(np.insert(ok.astype(float), 0, 0.0))
    n = np.arange(1, len(y) + 1)
    lo = np.maximum(n - w, 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return (c[n] - c[lo]) / (k[n] - k[lo])


# ------------------------------------------------------------------ vẽ
columns = [p[0] for p in PANELS]
logs = [(load_run(name, columns), label, color) for name, label, color in RUNS]

fig, axs = plt.subplots(2, 3, figsize=(7.2, 4.3))
for ax, (col, title, logy) in zip(axs.flat, PANELS):
    for d, label, color in logs:
        x = d["iteration"] - d["iteration"][0]          # số vòng lặp kể từ đầu lần train
        ax.plot(x, moving_average(d[col]), color=color, lw=1.4, label=label)
    ax.set_title(title, loc="left", fontsize=8.5)
    if logy:
        ax.set_yscale("log")
    else:
        ax.yaxis.set_major_formatter(CommaFormatter(useOffset=False))
    ax.xaxis.set_major_formatter(CommaFormatter(useOffset=False))

axs[0, 0].legend(loc="upper right")
for ax in axs[1]:
    ax.set_xlabel("Số vòng lặp kể từ đầu lần train")

fig.tight_layout(h_pad=1.2, w_pad=0.8)
fig.savefig(f"{OUT}.png", dpi=300, bbox_inches="tight", pad_inches=0.04, facecolor="white")
fig.savefig(f"{OUT}.svg", bbox_inches="tight", pad_inches=0.04)
print(f"Đã lưu {OUT}.png và {OUT}.svg")
