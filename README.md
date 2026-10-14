# NCKH 2026–2027 · Robot vịt hai chân Microduck: leo bậc thang, vượt vật cản và nhặt đồ trong mô phỏng

## Giới thiệu

**Microduck** là một robot hai chân hình con vịt, cao khoảng 25 cm, dùng 14 servo Dynamixel XL330. Robot
không được lập trình từng bước đi: chuyển động của nó do các **mạng nơ-ron (policy, định dạng ONNX)**
quyết định. Các mạng này được huấn luyện bằng **học tăng cường (PPO)** trong trình mô phỏng vật lý
**MuJoCo**. Trên robot, chương trình `robotd` (viết bằng Rust) chạy vòng điều khiển 50 Hz: đọc cảm
biến, đưa vào policy, rồi gửi lệnh cho servo. Cùng chương trình đó chạy được trong mô phỏng
(`duck-sim`), nên những gì kiểm chứng trong mô phỏng là kiểm chứng trên đúng phần mềm của robot.

Đề tài tập trung vào 4 việc:

1. **Huấn luyện policy đi bộ leo lên và xuống bậc thang thấp.**
2. **Tự điều hướng tới đích**, đi vòng qua vật cản bằng cảm biến khoảng cách ToF.
3. **Demo nhặt đồ:** vịt đi khắp căn hộ mô phỏng, cúi xuống "nhặt" từng đồ vật, mang về một mốc đích.
   Có camera để xem từ mắt vịt.
4. **Phương pháp đánh giá khách quan:** chấm điểm theo vị trí thật trong mô phỏng, không theo
   odometry hay đồ thị lúc huấn luyện.

## Kết quả chính

Tất cả kết quả đo trong `duck-sim` (MuJoCo + `robotd` thật), dùng vị trí thật do trình mô phỏng cung cấp.

| Nhiệm vụ | Policy | Kết quả |
|---|---|---|
| Lên 6 bậc cao 1 cm rồi xuống (đích 3 m) | `stairs_v8` (tự huấn luyện) | **8/8** tới đích ở tốc độ 0.35 (thêm 5/5 ở 0.3), 0 lần té. Có 1 lần chạy tay bị lệch hướng rồi kẹt |
| Xuống 6 bậc cao 1 cm (đích 2 m) | `stairs_v8` | **5/5** ở tốc độ 0.35 (ở 0.3: 4/5, một lần không chịu bước) |
| Vòng qua 3 hộp cao 20 cm (đích 2 m) | `seed-v1` (policy chính thức) | **2/2**, khoảng 19 s |
| Nhặt 7 đồ vật trong căn hộ 6 phòng, mang về đích | `seed-v1` + `ground_pick` | **7/7** và **6/7** trong 2 lượt liên tiếp, khoảng 8 phút/lượt |

> Phần **nhặt đồ là demo trong mô phỏng**: vịt mô phỏng không có khớp mỏ, nên khi mỏ chạm đồ vật, trình mô phỏng "gắn" đồ vào mỏ 

## Những gì đã làm

### 1. Huấn luyện leo bậc thang: tìm ra vì sao policy không học leo

Các policy được huấn luyện trong repo [`microduck_rl`](https://github.com/pollen-robotics/microduck_rl)
(mjlab + MuJoCo Warp, PPO). Qua 6 phiên bản (v4 → v9), đề tài tìm và sửa được các nguyên nhân sau:

| Vấn đề phát hiện | Bằng chứng | Cách sửa |
|---|---|---|
| Curriculum địa hình mặc định của mjlab gần như **không bao giờ cho lên cấp**: điều kiện hạ cấp khắt khe hơn điều kiện lên cấp khi lệnh đổi hướng liên tục | Sau 6000 vòng, mức địa hình trung bình chỉ **0.24/9**: policy gần như chỉ học bậc dưới 1 cm | Viết curriculum riêng `terrain_levels_stairs`: lên cấp khi đi xa ≥ 1 m không té, xuống cấp khi té hoặc không rời bục. Mức đạt **~3.9/9** |
| Chỉ có kim tự tháp bậc (xuất phát trên đỉnh), nên **"đi xa" thực chất là đi xuống**; leo lên chỉ tình cờ | v5 leo kém hơn v4 dù chỉ số huấn luyện đẹp hơn | Thêm kim tự tháp ngược (xuất phát dưới hố, đi ra là phải leo) |
| Hàm `out_of_terrain_bounds` của mjlab tính bề rộng sân từ `num_cols` | Thêm loại địa hình thứ 5 thì env ở cột ngoài bị reset sau ~2 bước | Tính `num_cols` từ số loại địa hình |
| Địa hình huấn luyện bị **làm mềm** (`solref` 0.04) để tránh lỗi NaN, nên mép bậc "lún" cho chân trượt qua | Trên bậc cứng, v6 kẹt 8/8 lần; làm mềm bậc thì leo được 2/3 lần | Huấn luyện trên địa hình cứng (`RIGID_TERRAIN`), không phát sinh NaN |
| Reward nhấc chân (`foot_swing_height`) bị nhân với dt, chỉ bằng **~0.2%** reward bám vận tốc | Chân nhấc cao trung bình chỉ 1.35 cm ở mọi phiên bản | Tăng trọng số; chân nhấc **1.35 → 1.55 cm (v8) → 1.8 cm (v9)** |

Lịch sử các phiên bản:

| Phiên bản | Thay đổi | Đánh giá trong `duck-sim` |
|---|---|---|
| v4 | Cấu hình bậc thang ban đầu | Bậc 1 cm đi được; bậc 2 cm té |
| v5 | Curriculum mới (train lại từ đầu) | Kém hơn v4: học đi xuống, không học leo |
| v6 | + kim tự tháp ngược (fine-tune từ v4) | Kẹt ở bậc đầu khi leo (do địa hình mềm) |
| v7 | + địa hình cứng | Leo lại được, nhưng trôi ngang nhiều |
| **v8** | + phạt nhấc chân thấp mạnh hơn | **Tốt nhất trên bậc 1 cm** |
| v9 | + phạt mạnh hơn nữa | Chân nhấc 1.8 cm, vẫn chưa qua được bậc 2 cm |

### 2. Đánh giá và điều hướng (thư mục [`microduck/scripts/`](microduck/scripts))

- **`stairs-eval.py`**: chấm một hoặc nhiều policy trên 4 map (lên bậc, xuống bậc, bậc 1–3 cm, vật
  cản). Mỗi lần chạy khởi động lại mô phỏng, cho vịt tự đi tới đích, rồi chấm theo **vị trí thật**
  (odometry trên bậc thang lệch 8–17 cm).
- **`duck-nav.py`**: điều hướng tới đích có tránh vật cản bằng ToF. Thêm tùy chọn `--retries` để vịt
  tự đứng dậy và đi tiếp sau khi té.
- **`duck-sim`**: vẫn chạy đầy đủ khi bật camera trên máy không build được `mediad` (GStreamer < 1.22).

### 3. Demo nhặt đồ trong căn hộ: `duck-fetch.py`

Mỗi đồ vật đi qua đủ các bước: tìm đường A* qua 6 phòng (tránh tường, đồ đạc, hố cầu thang và các đồ
vật khác) → đi tới, dừng cách đồ vật 10 cm và quay mặt về phía nó → cúi xuống bằng policy `ground_pick`
→ "nhặt" khi mỏ chạm điểm thấp nhất → mang về khu đích, xếp theo lưới 3 × 3 → cúi xuống thả.

Một số điểm rút ra khi làm:

- **Policy đi bộ không bắt đầu quay được từ tư thế đứng yên.** Lệnh chỉ quay thì vịt chỉ lắc nhẹ.
  Phải quay kèm nhích tới 0.2 m/s; muốn lùi phải ra lệnh từ −0.4.
- **Bám đường đi theo tiến độ dọc đường**, không theo từng điểm mốc. Nếu không, vịt có thể chạy vòng
  quanh một góc ngoặt mãi.
- **Mỏ thường đậu lên nóc khối vuông** chứ không xuống tới sàn, nên phải "nhặt" ở điểm thấp nhất
  thực tế, không theo một độ cao cố định.

### 4. Camera từ mắt vịt: `duck-cam.py`

Xem trực tiếp hoặc chụp ảnh từ camera trên đầu vịt mô phỏng (640×360, khoảng 15 hình/giây). Ảnh được
xoay đứng như trên console của robot thật. `duck-fetch.py --camera --snapshots` vừa mở cửa sổ camera,
vừa tự chụp ảnh lúc tiếp cận đồ vật, lúc tới khu đích và sau khi thả.

## Cấu trúc repo

```
.                    runtime gốc của Microduck (Pollen Robotics): robotd, tofd, mediad, robotctl...
microduck/           bản làm việc của đề tài: runtime + các phần bổ sung bên dưới
├── scripts/
│   ├── duck-sim         chạy robot trong MuJoCo (một lệnh)
│   ├── duck-nav.py      tự đi tới đích, tránh vật cản      (+ --retries)
│   ├── stairs-eval.py   chấm policy theo vị trí thật        (mới)
│   ├── duck-fetch.py    demo nhặt đồ trong căn hộ           (mới)
│   └── duck-cam.py      xem / chụp camera của vịt           (mới)
├── policies/            vị trí các policy ONNX mà duck-sim nạp (xem lưu ý bên dưới)
└── *.md                 ghi chú và hướng dẫn của nhóm
```

Phần huấn luyện và trình mô phỏng nằm ở repo **`microduck_rl`** (bản có sửa đổi). Bản đó gồm curriculum
`terrain_levels_stairs`, cấu hình bậc thang, các map `scene_steps*`, `scene_apartment_fetch`, và
`sim/props.py`. <!-- TODO: link tới repo / fork microduck_rl của nhóm -->

> **Lưu ý về policy:** các file trong `microduck/policies/` là liên kết tới file trên máy tác giả, nên
> không dùng được sau khi clone. `duck-sim` tự tải bộ policy chính thức nếu không tìm thấy. Policy tự
> huấn luyện (`stairs_v8.onnx`...) được phát hành riêng. <!-- TODO: link GitHub Releases -->

## Cài đặt

Đã thử trên Ubuntu 22.04, GPU RTX 4060 Laptop 8 GB (chỉ cần GPU khi huấn luyện).

1. **Rust** (`cargo`): `duck-sim` tự build `robotd`, `robotctl`, `tofd` ở lần chạy đầu.
2. **`microduck_rl`** đặt tại `~/Pollen/microduck_rl` (hoặc đặt biến `DUCK_SIM_RL`), có sẵn môi trường
   Python `.venv` chứa MuJoCo, mjlab, onnxruntime.
3. **OpenCV** cho Python của hệ thống (để xem camera): `python3 -c "import cv2"`.

```bash
git clone https://github.com/LeNguyenTruongPhu/NCKH_2026-2027.git
cd NCKH_2026-2027/microduck
```

## Chạy mô phỏng

Mỗi map cần 2–3 terminal, chạy trong thư mục `microduck/`. Policy được nạp **lúc mở map**, nên phải đổi
policy *trước* khi chạy `duck-sim`:

```bash
# map vật cản và căn hộ: policy chính thức seed-v1
ln -sfn ~/.cache/duck-sim/policies/releases/seed-v1/alpha_walking.onnx policies/alpha_walking.onnx
# map bậc thang: policy tự huấn luyện
ln -sfn /đường/dẫn/tới/stairs_v8.onnx policies/alpha_walking.onnx
```

| Map | Terminal 1: mở map | Terminal 3: cho vịt đi |
|---|---|---|
| Vật cản | `DUCK_SIM_CAMERAS=a DUCK_SIM_SCENE=obstacles scripts/duck-sim` | `scripts/duck-nav.py --absolute 2 0 --step-over 0.08 --speed 0.35 --retries 2` |
| Lên & xuống bậc | `DUCK_SIM_CAMERAS=a DUCK_SIM_SCENE=steps scripts/duck-sim` | `scripts/duck-nav.py --absolute 3.0 0 --step-over 0.08 --speed 0.35 --retries 2` |
| Xuống bậc | `DUCK_SIM_CAMERAS=a DUCK_SIM_SCENE=steps_down DUCK_SIM_KEYFRAME=SIT_HIGH scripts/duck-sim` | `scripts/duck-nav.py --absolute 2 0 --step-over 0.08 --speed 0.35 --retries 2` |

Terminal 2 (camera): `python3 scripts/duck-cam.py`. Trong cửa sổ, nhấn `s` để lưu ảnh, `q` để thoát.

**Demo nhặt đồ** (cửa sổ camera tự mở):

```bash
DUCK_SIM_CAMERAS=a DUCK_SIM_SCENE=apartment_fetch scripts/duck-sim     # terminal 1
python3 scripts/duck-fetch.py --camera --snapshots ~/duck-anh           # terminal 2
```

Tắt mô phỏng: `scripts/duck-sim down`. Nếu máy chậm làm vịt hay té, thêm `DUCK_SIM_VIEWER=0` để tắt
cửa sổ 3D.

## Đánh giá một policy

```bash
python3 -u scripts/stairs-eval.py ~/Pollen/microduck_rl/exports/stairs_v8.onnx --runs 5
python3 -u scripts/stairs-eval.py a.onnx b.onnx --courses up,down,obstacles --runs 5   # so sánh
```

## Huấn luyện (trong `microduck_rl`)

Ví dụ: v8 được fine-tune từ v7, khoảng 1.4 giờ trên RTX 4060.

```bash
.venv/bin/train Mjlab-Velocity-Stairs-MicroDuck \
  --env.scene.num-envs 2048 --env.sim.nconmax 100 --agent.max-iterations 2000 \
  --agent.logger tensorboard --agent.run-name stairs_v8 \
  --agent.resume True --agent.load-run <thư-mục-run-v7> --agent.load-checkpoint model_8998.pt \
  --env.rewards.track-linear-velocity.weight 3.0 \
  --env.rewards.foot-clearance.params.target-height 0.025 \
  --env.rewards.foot-swing-height.params.target-height 0.025 \
  --env.rewards.foot-swing-height.weight -4.0

.venv/bin/python scripts/export.py Mjlab-Velocity-Stairs-MicroDuck \
  --checkpoint-file <run>/model_10997.pt --onnx-file exports/stairs_v8.onnx --num-envs 1

.venv/bin/tensorboard --logdir logs/rsl_rl/velocity_stairs     # xem biểu đồ huấn luyện
```

Bài học rút ra: **đồ thị huấn luyện đẹp không có nghĩa là robot đi tốt hơn**. Ví dụ, v5 có chỉ số
huấn luyện tốt hơn v4 nhưng chạy thật kém hơn. Vì vậy mọi phiên bản đều phải chấm bằng `stairs-eval.py`
trước khi dùng.

## Hạn chế

- **Mọi kết quả đều trong mô phỏng**, chưa thử trên robot thật.
- **Bậc thang chỉ tới khoảng 1 cm.** Policy "mù" (không nhìn thấy bậc) đi được bậc 1 cm nhưng té ở bậc
  2 cm, vì chân nhấc cao tối đa khoảng 1.8 cm.
- **Policy leo bậc (v8) quay kém**: đứng im khi phải vừa xuất phát vừa rẽ, và tự lệch trái khi đi
  thẳng (khoảng 9°/s). Vì vậy map vật cản và căn hộ đang dùng policy chính thức `seed-v1`.
- **Nhặt đồ là mẹo của mô phỏng:** vịt mô phỏng không có khớp mỏ nên không gắp thật. Script cũng lấy
  vị trí đồ vật, tường và chính con vịt trực tiếp từ trình mô phỏng, thứ mà robot thật không có.
- **Cả hai policy chỉ đi được khoảng một nửa tốc độ được lệnh** và bỏ qua lệnh dưới 0.2 m/s khi đang
  đứng yên.

## Hướng phát triển

- Huấn luyện **v10**: một policy vừa leo bậc vừa quay tốt (thêm sàn phẳng và bài tập quay tại chỗ).
- Thử policy đi bộ mới của Pollen (`velstand`), được mô tả là bám lệnh quay tốt hơn.
- Cho policy **nhìn thấy bậc** (cảm biến ToF hoặc camera) để vượt bậc cao hơn.
- Thêm **khớp mỏ** vào mô hình MuJoCo theo robot thật và huấn luyện kỹ năng ngậm đồ thật.
- Kiểm chứng trên **robot thật**.

## Ghi công và giấy phép

- Runtime Microduck: © [Pollen Robotics](https://github.com/pollen-robotics/microduck), giấy phép
  **Apache-2.0** (bản sao đầy đủ ở [`microduck/LICENSE`](microduck/LICENSE)). Repo này gồm mã nguồn của
  Pollen Robotics kèm các thay đổi của đề tài liệt kê ở trên.
- Huấn luyện: [`microduck_rl`](https://github.com/pollen-robotics/microduck_rl),
  [mjlab](https://github.com/mujocolab/mjlab), [MuJoCo](https://mujoco.org), rsl_rl (PPO).
- Policy chính thức (`seed-v1`, `ground_pick`, ...):
  [`pollen-robotics/microduck-policies`](https://huggingface.co/pollen-robotics/microduck-policies).
