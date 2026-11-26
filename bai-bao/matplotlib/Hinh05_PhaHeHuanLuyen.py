# -*- coding: utf-8 -*-
"""
Hình 5 – Phả hệ 16 lần huấn luyện theo trục vòng lặp PPO.

Chạy:   pip install matplotlib
        python Hinh05_PhaHeHuanLuyen.py
Kết quả: Hinh05_PhaHeHuanLuyen.png (300 dpi, chèn vào Word)
         Hinh05_PhaHeHuanLuyen.svg (ảnh vector, sửa tiếp được)

Số liệu (vòng lặp đầu/cuối của từng lần huấn luyện) lấy từ
training-logs/runs_summary.csv và đã được chép sẵn vào RUNS bên dưới,
nên script chạy độc lập, không cần file log.
"""
import matplotlib
matplotlib.use("Agg")                      # vẽ không cần cửa sổ; xoá dòng này nếu muốn plt.show()
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from pathlib import Path

OUT = Path(__file__).resolve().parent / "Hinh05_PhaHeHuanLuyen"   # ảnh lưu cạnh script

# ------------------------------------------------------------------ kiểu chữ, màu
plt.rcParams.update({
    "font.family": "DejaVu Sans",          # có sẵn trong matplotlib, đủ dấu tiếng Việt
    "font.size": 9,
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
    "legend.frameon": False,
    "text.color": "#191919",
})
C_WALK = "#257de0"     # chuỗi đi bộ được dùng
C_CLIMB = "#f47230"    # chuỗi kỹ năng leo được dùng
C_DROP = "#cfcfcf"     # nhánh bị loại

# ------------------------------------------------------------------ số liệu
# (tên lần huấn luyện, vòng lặp đầu, vòng lặp cuối) – thứ tự từ trên xuống
RUNS = [
    ("flat_v1",    0,     481),
    ("flat_v2",    0,     5999),
    ("stairs_v1",  5999,  8066),
    ("stairs_v2",  5999,  8998),
    ("stairs_v3",  8000,  9999),
    ("stairs_v4",  8000,  9499),
    ("stairs_v5",  9000,  10104),
    ("stairs_v6",  10100, 10736),
    ("stairs_v7",  9000,  9705),
    ("stairs_v8",  9800,  10403),
    ("stairs_v9b", 9800,  10643),
    ("climb_v1",   9800,  10164),
    ("climb_v2",   9800,  10923),
    ("climb_v3",   10400, 10671),
    ("climb_v4",   10400, 11043),
    ("climb_v5",   10400, 11899),
]
# checkpoint được chọn trên chuỗi đang dùng (vòng lặp)
USED = {"flat_v2": 5999, "stairs_v2": 8000, "stairs_v4": 9000,
        "stairs_v5": 9800, "climb_v2": 10400, "climb_v5": 11600}
# nhãn cho chính sách được xuất ra ONNX
DEPLOY = {"stairs_v5": "alpha_walking.onnx",
          "climb_v2": "climb_v2.onnx (dự phòng)",
          "climb_v5": "climb.onnx"}
# lý do dừng các nhánh bị loại
NOTE = {"flat_v1": "tự xoay khi lệnh đứng yên",
        "stairs_v1": "quên kỹ năng quay",
        "stairs_v3": "không còn leo bậc 3 cm",
        "stairs_v6": "lùi bước nhiều hơn",
        "stairs_v7": "lùi bước nhiều hơn",
        "stairs_v8": "cải thiện rất ít",
        "stairs_v9b": "kém hơn trong duck-sim",
        "climb_v1": "không chịu leo",
        "climb_v3": "đầu nghiêng 17°",
        "climb_v4": "khớp đầu ép vào chốt"}

# ------------------------------------------------------------------ vẽ
fig, ax = plt.subplots(figsize=(7.2, 4.6))

rows = RUNS[::-1]                          # barh vẽ từ dưới lên, nên đảo thứ tự
for i, (name, start, end) in enumerate(rows):
    used = name in USED
    climb = name.startswith("climb")
    color = (C_CLIMB if climb else C_WALK) if used else C_DROP

    ax.barh(i, end - start, left=start, height=0.56,
            color=color, edgecolor="white", linewidth=0.8)

    if used:                               # hình thoi = checkpoint được chọn
        ax.plot(USED[name], i, marker="D", markersize=5.5,
                markerfacecolor="white", markeredgecolor="#191919",
                markeredgewidth=1.1, zorder=5)

    label = DEPLOY.get(name) if name in DEPLOY else NOTE.get(name, "")
    ax.text(end + 60, i, label, va="center", fontsize=6.8,
            color="#333333" if used else "#777777")

ax.set_yticks(range(len(rows)))
ax.set_yticklabels([r[0] for r in rows], fontsize=7.5)
ax.set_xlim(-100, 15200)
ax.set_xlabel("Vòng lặp PPO (đếm nối tiếp qua các lần học tiếp)")
ax.grid(axis="y", visible=False)           # chỉ giữ lưới dọc

legend = [Patch(color=C_WALK, label="chuỗi đi bộ được dùng"),
          Patch(color=C_CLIMB, label="chuỗi kỹ năng leo được dùng"),
          Patch(color=C_DROP, label="nhánh bị loại"),
          Line2D([], [], marker="D", linestyle="", markerfacecolor="white",
                 markeredgecolor="#191919", label="checkpoint được chọn")]
ax.legend(handles=legend, loc="upper right", fontsize=7.5)

fig.tight_layout()
fig.savefig(f"{OUT}.png", dpi=300, bbox_inches="tight",
            pad_inches=0.04, facecolor="white")
fig.savefig(f"{OUT}.svg", bbox_inches="tight", pad_inches=0.04)
print(f"Đã lưu {OUT}.png và {OUT}.svg")
