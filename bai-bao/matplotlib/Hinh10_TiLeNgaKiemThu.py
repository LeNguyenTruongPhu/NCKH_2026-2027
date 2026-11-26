# -*- coding: utf-8 -*-
"""
Hình 10 – Tỉ lệ ngã trong kiểm thử 1000 môi trường:
(a) theo loại địa hình, (b) theo độ cao bậc (chỉ các ô cầu thang).

Chạy:   python Hinh10_TiLeNgaKiemThu.py
Cần:    matplotlib (numpy đi kèm matplotlib), không cần pandas.
Kết quả: Hinh10_TiLeNgaKiemThu.png (300 dpi, chèn vào Word) và Hinh10_TiLeNgaKiemThu.svg (ảnh vector),
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
OUT = Path(__file__).resolve().parent / "Hinh10_TiLeNgaKiemThu"   # ảnh lưu cạnh script
WALK = read_rows(TEST_DIR / "walking_stairs_v5_model9800" / "envs.csv")
CLIMB = read_rows(TEST_DIR / "climb_v5_model11600" / "envs.csv")
POLICIES = [(WALK, C1, "Đi bộ (stairs_v5)", "o"), (CLIMB, C2, "Leo thang (climb_v5)", "s")]
TERRAINS = [("flat", "Sàn phẳng"),
            ("pyramid_stairs", "Kim tự tháp bậc\n(đi xuống)"),
            ("inverted_pyramid_stairs", "Hố bậc\n(đi lên)"),
            ("random_grid", "Sàn lồi lõm\n(0–2,5 cm)"),
            ("pyramid_slope", "Dốc heightfield\n(3–12%)")]
STAIRS = {"pyramid_stairs", "inverted_pyramid_stairs"}

fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.1), gridspec_kw={"width_ratios": [1.25, 1]})

# ---- (a) tỉ lệ ngã theo loại địa hình, kèm KTC 95% Wilson
ax = axs[0]
for i, (terrain, _) in enumerate(TERRAINS):
    for j, (rows, color, label, marker) in enumerate(POLICIES):
        g = [r for r in rows if r["terrain"] == terrain]
        if not g:
            continue                                   # kỹ năng leo không được thử trên dốc và sàn lồi lõm
        k, n = sum(int(num(r["fell"])) for r in g), len(g)
        p, lo, hi = wilson(k, n)
        yy = i + (-0.17 if j == 0 else 0.17)
        ax.plot([lo * 100, hi * 100], [yy, yy], color=color, lw=1.6, solid_capstyle="round")
        ax.plot(p * 100, yy, marker=marker, ms=6, color=color, mec="white", mew=0.8, label=label if i == 0 else None)
        if hi > 0.6:
            ax.text(lo * 100 * 0.93, yy, f"{k}/{n}", va="center", ha="right", fontsize=6.8, color="#333333")
        else:
            ax.text(hi * 100 * 1.07 + 0.3, yy, f"{k}/{n}", va="center", fontsize=6.8, color="#333333")
ax.set_yticks(range(len(TERRAINS)))
ax.set_yticklabels([t[1] for t in TERRAINS], fontsize=7.5)
ax.invert_yaxis()
ax.set_xscale("symlog", linthresh=10)               # tuyến tính dưới 10%, logarit phía trên
ax.set_xlim(0, 100)
ax.set_xticks([0, 2, 5, 10, 20, 50, 100])
ax.set_xticklabels(["0", "2", "5", "10", "20", "50", "100"])
ax.set_xlabel("Tỉ lệ ngã (%) – điểm: ước lượng; đoạn: KTC 95% Wilson")
ax.grid(axis="y", visible=False)
ax.set_title("(a) Theo loại địa hình", loc="left")
ax.legend(loc="upper right", fontsize=7)

# ---- (b) tỉ lệ ngã theo độ cao bậc, chỉ các ô cầu thang
ax = axs[1]
for rows, color, label, marker in POLICIES:
    by_row = {}
    for r in rows:
        if r["terrain"] in STAIRS:
            by_row.setdefault(int(num(r["row"])), []).append(r)
    xs, ps, los, his = [], [], [], []
    for row_id in sorted(by_row):
        g = by_row[row_id]
        a, b = (float(v) for v in g[0]["riser_cm"].split("-"))   # ví dụ "2.0-2.2"
        k, n = sum(int(num(r["fell"])) for r in g), len(g)
        p, lo, hi = wilson(k, n)
        xs.append((a + b) / 2); ps.append(p * 100); los.append(lo * 100); his.append(hi * 100)
    ax.fill_between(xs, los, his, color=color, alpha=0.13, lw=0)
    ax.plot(xs, ps, color=color, marker=marker, ms=5, mec="white", mew=0.8, label=label)
ax.axvline(3.0, color="#555555", ls=(0, (4, 3)), lw=0.9)
ax.text(3.05, 33, "bậc 3 cm\n(map course)", fontsize=6.8, color="#333333", va="top")
ax.set_xlabel("Độ cao bậc (cm, tâm khoảng của hàng)")
ax.set_ylabel("Tỉ lệ ngã (%)")
ax.set_ylim(0, 48)
ax.set_title("(b) Theo độ cao bậc (chỉ ô cầu thang)", loc="left")
ax.legend(loc="upper left", fontsize=7)

fig.tight_layout(w_pad=1.5)
save(fig, OUT)
