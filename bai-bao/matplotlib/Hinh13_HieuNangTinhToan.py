# -*- coding: utf-8 -*-
"""
Hình 13 – (a) Thông lượng huấn luyện của từng lần huấn luyện;
(b) mức dùng GPU mỗi giây khi chạy lại 60 vòng của climb_v5.

Chạy:   python Hinh13_HieuNangTinhToan.py
Cần:    matplotlib (numpy đi kèm matplotlib), không cần pandas.
Kết quả: Hinh13_HieuNangTinhToan.png (300 dpi, chèn vào Word) và Hinh13_HieuNangTinhToan.svg (ảnh vector),
         lưu ngay cạnh file script.

Số liệu đọc trực tiếp từ project NCKH_2026-2027:
    training-logs/runs_summary.csv và training-logs/system/gpu_samples_probe.csv
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
from matplotlib.patches import Patch

OUT = Path(__file__).resolve().parent / "Hinh13_HieuNangTinhToan"  # ảnh lưu cạnh script
SUMMARY = ROOT / "training-logs" / "runs_summary.csv"
GPU_LOG = ROOT / "training-logs" / "system" / "gpu_samples_probe.csv"

fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.9), gridspec_kw={"width_ratios": [1.2, 1]})

# ---- (a) thông lượng trung bình của mỗi lần huấn luyện, theo thứ tự thời gian bắt đầu
ax = axs[0]
runs = [r for r in read_rows(SUMMARY) if r.get("task")]
runs.sort(key=lambda r: r["started"])
names = [re.sub(r".*biped60_", "", r["run"]).replace("stairs_climb", "climb") for r in runs]
speed = np.array([num(r["steps_per_s_mean"]) for r in runs])
colors = [C2 if "climb" in n else (C3 if "flat" in n else C1) for n in names]
y = np.arange(len(runs))
ax.barh(y, speed / 1000, color=colors, height=0.62)
for yi, v in zip(y, speed):
    ax.text(v / 1000 + 0.4, yi, f"{v / 1000:.1f}k", va="center", fontsize=6.6, color="#333333")
ax.set_yticks(y)
ax.set_yticklabels(names, fontsize=7)
ax.invert_yaxis()
ax.set_xlim(0, 64)
ax.set_xlabel("Nghìn bước mô phỏng / giây")
ax.grid(axis="y", visible=False)
ax.set_title("(a) Thông lượng huấn luyện", loc="left")
ax.legend(handles=[Patch(color=C3, label="sàn phẳng, 4096 env"),
                   Patch(color=C1, label="đi bộ trên bậc, 2048 env"),
                   Patch(color=C2, label="kỹ năng leo, 2048 env")], loc="center right", fontsize=6.6)

# ---- (b) mức dùng GPU mỗi giây (nvidia-smi) khi chạy lại 60 vòng của climb_v5
ax = axs[1]
gpu = read_rows(GPU_LOG)
value = lambda r, c: num(re.search(r"[\d.]+", r[c]).group(0))     # "78 %" -> 78.0
util = np.array([value(r, "utilization.gpu [%]") for r in gpu])
mem = np.array([value(r, "memory.used [MiB]") for r in gpu]) / 1024
power = np.array([value(r, "power.draw [W]") for r in gpu])
t = np.arange(len(gpu))                                              # một mẫu mỗi giây
ax.plot(t, util, color=C1)
ax.set_xlabel("Thời gian (s)")
ax.set_ylim(0, 105)
ax.set_ylabel("Mức dùng GPU (%)")
active = util > 20                                                   # pha train: GPU dùng trên 20%
ax.axvspan(t[active].min(), t[active].max(), color="#f2f2f2", zorder=0)
ax.text(t[active].mean(), 35,
        f"Trong pha train ({active.sum()} s):\n"
        f"GPU trung bình {util[active].mean():.0f}% (đỉnh {util[active].max():.0f}%)\n"
        f"công suất TB {power[active].mean():.0f} W / giới hạn 140 W\n"
        f"VRAM {mem[active].max():.1f} / 8 GiB",
        ha="center", fontsize=6.8, color="#333333", bbox=dict(fc="white", ec="#dddddd", lw=0.6))
ax.set_title("(b) Tải GPU (chạy lại climb_v5, 60 vòng)", loc="left")

fig.tight_layout(w_pad=1.2)
save(fig, OUT)
