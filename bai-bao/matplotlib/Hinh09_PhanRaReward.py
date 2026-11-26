# -*- coding: utf-8 -*-
"""
Hình 9 – Phân rã reward của climb_v5 theo thành phần (giá trị trung bình mỗi episode / 20 s),
so sánh 50 vòng đầu với quanh checkpoint đang dùng model_11600.

Chạy:   python Hinh09_PhanRaReward.py
Cần:    matplotlib (numpy đi kèm matplotlib), không cần pandas.
Kết quả: Hinh09_PhanRaReward.png (300 dpi, chèn vào Word) và Hinh09_PhanRaReward.svg (ảnh vector),
         lưu ngay cạnh file script.

Số liệu đọc trực tiếp từ project NCKH_2026-2027:
    training-logs/runs/<thời gian>_biped60_stairs_climb_v5/scalars.csv
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
OUT = Path(__file__).resolve().parent / "Hinh09_PhanRaReward"     # ảnh lưu cạnh script
RUN = "stairs_climb_v5"
START_ROWS = 50                    # "50 vòng đầu" của climb_v5 (bắt đầu từ climb_v2/10400)
END_WINDOW = (11550, 11650)        # các vòng lặp quanh checkpoint đang dùng model_11600
MIN_ABS = 5e-3                     # bỏ các thành phần gần như bằng 0 ở cả hai thời điểm

d = load_run(RUN, prefix="Episode_Reward/")
comps = [c for c in d if c.startswith("Episode_Reward/")]
sel = (d["iteration"] >= END_WINDOW[0]) & (d["iteration"] <= END_WINDOW[1])
terms = []
with np.errstate(all="ignore"):
    for c in comps:
        a = np.nanmean(d[c][:START_ROWS])
        b = np.nanmean(d[c][sel])
        if np.nanmax([abs(a), abs(b)]) > MIN_ABS:
            terms.append((c.split("/", 1)[1], a, b))
terms.sort(key=lambda t: t[2])                     # xếp theo giá trị cuối, nhỏ nhất ở dưới
names = [t[0] for t in terms]
start = np.array([t[1] for t in terms])
end = np.array([t[2] for t in terms])

fig, ax = plt.subplots(figsize=(7.0, 4.6))
y = np.arange(len(terms))
ax.barh(y + 0.2, start, height=0.38, color=LIGHT2, label="50 vòng đầu (từ climb_v2/10400)")
ax.barh(y - 0.2, end, height=0.38, color=C2, label="quanh model_11600 (đang dùng)")
ax.set_yticks(y)
ax.set_yticklabels(names, fontsize=7.5)
ax.axvline(0, color="#555555", lw=0.8)
ax.set_xlim(-0.6, 2.55)
for yi, v in zip(y, end):
    ax.text(v + (0.002 if v >= 0 else -0.002), yi - 0.2, f"{v:+.3f}", va="center",
            ha="left" if v >= 0 else "right", fontsize=6.5, color="#333333")
ax.set_xlabel("Đóng góp vào reward của episode, chia cho 20 s (đã nhân trọng số)")
ax.legend(loc="lower right")
ax.grid(axis="y", visible=False)
fig.tight_layout()
save(fig, OUT)
