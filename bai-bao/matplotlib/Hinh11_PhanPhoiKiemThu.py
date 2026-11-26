# -*- coding: utf-8 -*-
"""
Hình 11 – Phân phối kết quả trên 1000 môi trường mỗi chính sách:
(a) sai số v_x, (b) sai số ω_z, (c) tỉ lệ ngã tích lũy theo thời gian.

Chạy:   python Hinh11_PhanPhoiKiemThu.py
Cần:    matplotlib (numpy đi kèm matplotlib), không cần pandas.
Kết quả: Hinh11_PhanPhoiKiemThu.png (300 dpi, chèn vào Word) và Hinh11_PhanPhoiKiemThu.svg (ảnh vector),
         lưu ngay cạnh file script.

Số liệu đọc trực tiếp từ project NCKH_2026-2027:
    test-logs/walking_stairs_v5_model9800/envs.csv và test-logs/climb_v5_model11600/envs.csv
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
OUT = Path(__file__).resolve().parent / "Hinh11_PhanPhoiKiemThu"  # ảnh lưu cạnh script
WALK = read_rows(TEST_DIR / "walking_stairs_v5_model9800" / "envs.csv")
CLIMB = read_rows(TEST_DIR / "climb_v5_model11600" / "envs.csv")
col = lambda rows, c: np.array([num(r[c]) for r in rows])

fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.7))

# ---- (a), (b) hộp phân phối sai số bám lệnh; số bên cạnh là giá trị trung bình
for ax, (c, title, ylim) in zip(axs[:2], [("err_vx", "(a) Sai số $v_x$ (m/s)", (0, 0.35)),
                                          ("err_wz", "(b) Sai số $\\omega_z$ (rad/s)", (0, 1.2))]):
    data = [col(WALK, c), col(CLIMB, c)]
    bp = ax.boxplot(data, widths=0.5, patch_artist=True, showfliers=True,
                    flierprops=dict(marker=".", ms=2.5, mfc="#999999", mec="none"),
                    medianprops=dict(color="#191919", lw=1.2),
                    whiskerprops=dict(color="#777777"), capprops=dict(color="#777777"))
    for patch, color in zip(bp["boxes"], [C1, C2]):
        patch.set_facecolor(color); patch.set_alpha(0.75); patch.set_edgecolor("white")
    ax.set_xticks([1, 2])
    ax.set_xticklabels(["Đi bộ", "Leo thang"])
    for i, dd in enumerate(data):
        ax.text(i + 1.3, np.median(dd), f"{np.mean(dd):.3f}", fontsize=6.8, va="center", color="#333333")
    ax.set_title(title, loc="left")
    ax.grid(axis="x", visible=False)
    ax.set_ylim(*ylim)

# ---- (c) tỉ lệ ngã tích lũy theo thời gian, tính trên toàn bộ 1000 môi trường
ax = axs[2]
t = np.linspace(0, 20, 401)
for rows, color, label in [(WALK, C1, "Đi bộ"), (CLIMB, C2, "Leo thang")]:
    fall_times = np.sort([num(r["survived_s"]) for r in rows if int(num(r["fell"])) == 1])
    F = [(fall_times <= x).sum() / len(rows) * 100 for x in t]
    ax.step(t, F, color=color, where="post", label=label)
ax.set_xlabel("Thời gian (s)")
ax.set_ylabel("Tỉ lệ đã ngã (%)")
ax.set_xlim(0, 20)
ax.legend(loc="upper left", fontsize=7)
ax.set_title("(c) Tỉ lệ ngã tích lũy", loc="left")

fig.tight_layout(w_pad=1.2)
save(fig, OUT)
