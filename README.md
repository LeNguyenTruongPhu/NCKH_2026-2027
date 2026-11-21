# NCKH 2026–2027 · Robot hai chân BIPED-C3 (60 cm): leo bậc thang, vượt vật cản và dọn đồ trong mô phỏng

## Giới thiệu

**BIPED-C3** (chữ **TLS** trên ngực) là robot hai chân cao **60 cm**, nặng khoảng **4,5 kg**, có 14 khớp
dùng servo **Dynamixel MX-106**. Nhóm thiết kế robot dưới dạng mô hình vật lý **MuJoCo**. Hiện robot
chỉ có trong mô phỏng, chưa có bản cứng.

Robot không được lập trình từng bước đi. Chuyển động của nó do các **mạng nơ-ron (policy, định dạng
ONNX)** quyết định. Các mạng này được huấn luyện bằng **học tăng cường (PPO)** trong MuJoCo.

BIPED-C3 được thiết kế với cùng 14 khớp như robot vịt **Microduck** của Pollen Robotics: cùng tên,
cùng thứ tự, cùng chiều quay và cùng tư thế đứng. Nhờ vậy chương trình điều khiển của Microduck,
`robotd` (Rust, vòng điều khiển 50 Hz), chạy được trên BIPED-C3 mà không phải viết lại. `duck-sim` chạy
đúng `robotd` đó với trình mô phỏng thay cho phần cứng. Vì vậy, kiểm chứng trong mô phỏng là kiểm chứng
trên chính phần mềm sẽ chạy trên robot.

Đề tài gồm 5 phần:

1. **Đi bộ và vượt vật cản** trên sàn phẳng.
2. **Leo lên rồi xuống cầu thang**: 5 bậc cao 3 cm, chiếu nghỉ, rồi 5 bậc xuống. Có một kỹ năng leo
   riêng "nhìn thấy" mép bậc.
3. **Đi trọn một đường đua**: bãi vật cản → cầu thang → vào căn hộ → **dọn đồ**. Robot tìm các đồ vật
   đặt ngẫu nhiên trong các phòng và mang từng món về một đĩa đỏ.
4. **Camera trên đầu robot có chống rung**, để xem từ mắt robot.
5. **Đánh giá khách quan**: chấm theo vị trí thật trong mô phỏng, không theo đồ thị huấn luyện.

## Kết quả chính

Tất cả kết quả đo trong `duck-sim` (MuJoCo + `robotd` thật).

| Bài | Policy | Kết quả |
|---|---|---|
| Vòng qua bãi vật cản tới đĩa đỏ | `alpha_walking` | Tới đích, khoảng **17 s** |
| Cầu thang 5 bậc 3 cm lên + xuống | `alpha_walking` + kỹ năng `climb` | **5/5** lượt qua thang, **0 lần lùi bước**, 7,7–8,1 s mỗi lượt |
| Trọn đường đua + dọn 5 đồ ngẫu nhiên | như trên | **5/5** đồ mang về đĩa, **0 lần đá đổ**, xong sau **320 s** (tới cửa căn hộ sau 38 s) |
| Camera khi leo thang | bộ chống rung trong mô phỏng | Chân trời nghiêng **15° → 0°**; ảnh còn rung khoảng 9 px/khung hình (640×360) |

Quá trình làm cho việc leo thang tốt dần lên, đo trên cùng cầu thang trong `duck-sim`:

| Cách leo | Thời gian qua thang | Lùi bước / lượt | Ghi chú |
|---|---|---|---|
| Chỉ dùng policy đi bộ (`stairs_v5`) | 13,5 s | 2,4 | "Bước lên tuột xuống" |
| Thêm kỹ năng leo `climb_v2` | 7–8 s | 0 (8/8 lượt) | Đầu nghiêng 17° suốt lúc leo |
| Kỹ năng leo `climb_v5` (đang dùng) | 7,7–8,1 s | 0 | Đầu thẳng (nghiêng ~1°), thân bớt lắc (31,9 → 29,8 °/s) |

## Những gì đã làm

### 1. Thiết kế robot

Mô hình được sinh ra bằng một script, `make_biped60.py` trong repo huấn luyện. Script tạo ra:

- bản dùng để huấn luyện: chỉ bàn chân chạm đất;
- bản dùng trong mô phỏng: thân, đầu, chân đều va chạm với vật xung quanh;
- lớp vỏ hiển thị.

Servo được mô phỏng bằng mô hình **BAM** của MX-106, khớp với servo thật hơn bộ điều khiển PD có sẵn
của MuJoCo: với PD thường, robot té trong chưa tới 1 giây. Khối lượng từng phần là ước lượng (servo +
giá đỡ + vỏ), chưa phải số đo từ bản CAD.

### 2. Huấn luyện đi bộ và leo thang

Huấn luyện bằng mjlab + MuJoCo Warp, PPO, trên GPU RTX 4060 Laptop 8 GB (2048 môi trường song song,
khoảng 2 s mỗi vòng).

| Phiên bản | Ý chính | Kết quả |
|---|---|---|
| `flat_v2` | Đi trên sàn phẳng, ép đối xứng trái/phải | Đứng yên, đi thẳng, quay tốt; té ngay bậc 3 cm đầu tiên |
| `stairs_v2` | Học thêm trên bậc cao 1–5 cm | Lần đầu đi trọn đường đua (126 s) |
| `stairs_v4` | Rải đều độ cao bậc, bỏ curriculum địa hình | Đường đua 96 s; thân lắc nhiều (37 °/s) |
| `stairs_v5` | Thưởng giữ thân và đầu ổn định | Bớt lắc, camera bớt rung khoảng 35%; vẫn lùi bước trên thang. **Đang dùng để đi bộ** |
| `climb_v2` | Kỹ năng leo riêng, nhìn thấy mép bậc | Hết lùi bước, leo nhanh gần gấp đôi |
| `climb_v5` | Phạt lệnh khớp vượt giới hạn cơ khí | Hết nghiêng đầu, thân êm hơn. **Đang dùng để leo** |

Các vấn đề tìm ra và cách sửa:

| Vấn đề | Bằng chứng | Cách sửa |
|---|---|---|
| Reward bám tốc độ quay của mjlab tính cả tốc độ lắc ngang và lắc dọc của thân vào sai số quay. Trên bậc thang thân lắc nhiều nên reward này gần như bằng 0 | Policy quên cách quay: trong cùng một bài thử quay tại chỗ, góc quay được giảm từ 298° xuống 85° | Viết reward chỉ tính quay quanh trục đứng (`track_yaw_rate_exp`) |
| Lúc huấn luyện, lệnh servo có độ trễ và vận tốc khớp đọc về bị cũ một nhịp (giống servo thật). Trình mô phỏng của `duck-sim` lại áp lệnh tức thì | Đánh giá trên CPU leo được, vào `duck-sim` thì té. Thử riêng từng khác biệt: chỉ cần độ trễ khác lúc huấn luyện (1 bước thay vì 3–6) là 0/3 lần leo được | Thêm độ trễ servo (4 bước) và vận tốc trễ vào trình mô phỏng cho khớp với lúc huấn luyện |
| Policy đi bộ không nhìn thấy bậc. Bàn chân dài 15 cm, mặt bậc 30 cm, nên khoảng **50%** lần đặt chân khi lên thang bị gác lên mép bậc, dễ tuột xuống | Đo vị trí từng lần đặt chân | Huấn luyện một **kỹ năng leo riêng** nhận 3 thông tin về bậc phía trước: khoảng cách tới mép thứ nhất, độ cao của mép đó, khoảng cách tới mép thứ hai |
| Phạt việc dẫm lên mép bậc thì policy **dừng hẳn trước cầu thang**, vì đứng yên thì không bị phạt | 4 lần thử (v8, v9, v9b, climb_v1): cải thiện rất ít, dừng trước bậc, hoặc không chịu leo | Thêm reward **tiến về phía trước** tăng tuyến tính, để đứng yên cũng bị thiệt |
| Reward giữ đầu ổn định khiến policy **ra lệnh cho khớp đầu vượt qua chốt chặn cơ khí**: ép khớp vào chốt thì đầu cứng hơn là để PD giữ | Đầu nghiêng 17° suốt lúc leo, tới đỉnh thì lật sang bên kia. 81% thời gian khớp đầu bị ép vào chốt. Trên robot thật, servo sẽ đẩy vào chốt liên tục và nóng lên | Phạt mọi lệnh khớp vượt giới hạn (`joint_target_beyond_limits_l2`). Phạt góc nghiêng của đầu thì không có tác dụng, vì khớp đã kẹt ở chốt |
| Leo chậm thì kém hơn | Trên bậc 3 cm: 0/6 lượt qua được ở 0,2 m/s, 5/6 ở 0,35 m/s, 6/6 ở 0,6 m/s | Các script cho robot đi nhanh hơn khi lên thang |

Bài học: **đánh giá trên CPU đạt chưa có nghĩa là trong `duck-sim` đạt**. Đã có lúc hai cách đo cho kết
quả ngược nhau. Vì vậy mỗi policy đều được chạy trong `duck-sim` trước khi đưa vào dùng.

### 3. Nối kỹ năng leo vào `robotd`

Những thay đổi ở `duck-control`, `robotd`, `robotd-params` và `robotctl`:

- **Kỹ năng nối tiếp (`chain`)**: robot chuyển từ policy đi bộ sang kỹ năng `climb` mà không dừng bước.
- **`live_twist`**: kỹ năng nhận lệnh tốc độ trực tiếp trong lúc chạy.
- **Thông tin địa hình**: được đưa vào 3 ô của vector quan sát. Các policy không được huấn luyện với địa
  hình thì 3 ô này luôn bằng 0. File ONNX được đánh dấu `sees_terrain=true` thì mới nhận dữ liệu thật.

`biped60-goal.py` và `biped60-fetch.py` tự gọi `robot.do climb` khi robot tới chân cầu thang.

### 4. Camera chống rung

Rung của camera chủ yếu đến từ **đầu robot**, không phải từ thân: khi đi, đầu xoay nhanh gấp khoảng 3
lần thân. Bộ chống rung (`sim/camera.py`) làm 4 việc:

- giữ hướng nhìn theo hướng đi của thân, lọc qua 2 tầng 0,3 s;
- làm mượt việc đầu nhún lên xuống và lắc ngang, tối đa 2,5 cm, không bao giờ lùi camera ra sau;
- giữ đường chân trời luôn nằm ngang;
- bỏ qua bước giữ ngang khi robot nhìn gần như thẳng xuống hoặc thẳng lên.

Đo trên bản ghi lúc leo thang, so với bộ lọc đầu tiên:

| Chỉ số | Bộ lọc đầu tiên | Bộ lọc hiện tại |
|---|---|---|
| Ảnh xoay mỗi khung hình | 7,9 px | 6,0 px |
| Nhún | 19,6 mm | 14,4 mm |
| Chân trời nghiêng | 15° | 0° |

Đổi lại, khi robot cúi nhìn xuống, ảnh theo chậm hơn một chút.

### 5. Dọn đồ: `biped60-fetch.py`

- **Mỗi lượt đặt ngẫu nhiên** tối đa 6 món, lấy từ 10 loại đồ: khối vuông, lon, khối cao, sách.
  Mỗi phòng có tối đa 2 món.
- **Tìm đường bằng A\*** qua các phòng, tránh tường, đồ đạc, lỗ cầu thang và các món khác. Robot tính
  một lần cho cả 16 hướng tiếp cận, mất 0,03–0,08 s.
- **Tới gần món đồ**: vừa đi vừa cúi nhìn xuống, "nhặt" ngay khi với tới, bước ngang để canh cho thẳng.
- **Mang về đĩa đỏ**, xếp quanh tâm đĩa.

So với bản đầu, cùng 5 khối vuông: 328 s → 238 s.

## Cấu trúc repo

```
.                        runtime gốc của Microduck (Pollen Robotics)
microduck/               bản làm việc của đề tài
├── scripts/
│   ├── duck-sim             chạy robot trong MuJoCo bằng robotd thật (mặc định là BIPED-C3)
│   ├── biped60-goal.py      đi tới đĩa đỏ: bãi vật cản, hoặc trọn đường đua
│   ├── biped60-fetch.py     đi đường đua rồi dọn đồ ngẫu nhiên trong căn hộ
│   ├── biped60-dance.py     bài nhảy (thử nghiệm, đã tạm dừng)
│   └── duck-cam.py          xem / chụp camera trên đầu robot
├── policies-biped60/        các policy ONNX mà duck-sim nạp
├── duck-control/ robotd/ robotd-params/ robotctl/    runtime Rust (đã sửa, xem mục 3)
└── ...                  phần còn lại của runtime Microduck
```

Các policy trong `policies-biped60/`:

| File | Vai trò |
|---|---|
| `alpha_walking.onnx` | Đi bộ chính (`stairs_v5`, vòng 9800) |
| `climb.onnx` | Kỹ năng leo thang (`climb_v5`, vòng 11600) |
| `climb_v2.onnx` | Bản leo cũ, để so sánh hoặc quay lại |
| `alpha_walking_flat.onnx` | Chỉ đi sàn phẳng (`flat_v2`) |
| `alpha_walking_stairs_v2.onnx`, `alpha_walking_stairs_v4.onnx`, `alpha_walking_iter3000.onnx` | Các bản cũ |
| `alpha_dance.onnx` | Nhảy (`dance_v3`), chỉ dùng trên map `stage` |

`duck-nav.py`, `stairs-eval.py`, `duck-fetch.py`, `evaluate_multiterrain.py` và các file `*.md` trong
`microduck/` là từ giai đoạn trước, khi đề tài còn làm với Microduck. Không dùng chúng cho BIPED-C3:
odometry và cảm biến ToF trong `robotd` vẫn tính theo mô hình của vịt.

> **Lưu ý:** phần huấn luyện và trình mô phỏng nằm trong bản sửa đổi của repo
> [`microduck_rl`](https://github.com/pollen-robotics/microduck_rl). Phần này gồm mô hình robot, các map,
> các bài huấn luyện, trình mô phỏng `body_server` và bộ chống rung camera. Bản sửa đổi đó **chưa được
> đưa lên GitHub**. Vì vậy sau khi clone repo này, `duck-sim` chưa chạy được nếu không có nó.

## Cài đặt

Đã thử trên Ubuntu 22.04, GPU RTX 4060 Laptop 8 GB. Chỉ cần GPU khi huấn luyện; chạy mô phỏng chỉ cần
CPU.

1. **Rust** (`cargo`): `duck-sim` tự build `robotd`, `robotctl`, `tofd` ở lần chạy đầu.
2. **`microduck_rl`** (bản sửa đổi) đặt tại `~/Pollen/microduck_rl`, hoặc đặt biến `DUCK_SIM_RL`. Cần
   môi trường Python `.venv` chứa MuJoCo, mjlab và onnxruntime.
3. **OpenCV** cho Python của hệ thống, để xem camera: `python3 -c "import cv2"`.

```bash
git clone https://github.com/LeNguyenTruongPhu/NCKH_2026-2027.git
cd NCKH_2026-2027/microduck
```

## Chạy mô phỏng

Chạy trong thư mục `microduck/`, mỗi lệnh một terminal:

```bash
DUCK_SIM_CAMERAS=a DUCK_SIM_SCENE=course scripts/duck-sim   # terminal 1: mở map đường đua
scripts/biped60-fetch.py                                    # terminal 2: đi đường đua rồi dọn đồ
scripts/duck-cam.py                                         # terminal 3: xem camera (s: lưu ảnh, q: thoát)
```

Tắt mô phỏng: `scripts/duck-sim down`. Policy và bộ chống rung được nạp **lúc mở map**. Muốn đổi policy
thì phải tắt mô phỏng rồi mở lại.

| Map (`DUCK_SIM_SCENE`) | Nội dung | Lệnh ở terminal 2 |
|---|---|---|
| `course` | Bãi vật cản → cầu thang → căn hộ | `scripts/biped60-fetch.py` (dọn đồ) hoặc `scripts/biped60-goal.py` (chỉ đi tới đích) |
| `obstacles` | Bãi vật cản | `scripts/biped60-goal.py` |
| `apartment_fetch` | Chỉ căn hộ | `scripts/biped60-fetch.py` |
| `steps`, `steps_easy`, `steps_hard`, `steps_down`, `ramp` | Bậc thang các độ cao, dốc | Chưa có script dẫn đường riêng cho các map này |
| `stage` | Sân khấu trống | `scripts/biped60-dance.py` |

Một số tùy chọn:

```bash
scripts/biped60-fetch.py --seed 7 --count 6     # lặp lại đúng một cách đặt đồ, 6 món
scripts/biped60-fetch.py --keep                 # không đặt lại, dọn những món đang có
DUCK_SIM_VIEWER=0 ...                           # tắt cửa sổ 3D nếu máy chậm
DUCK_SIM_CAMERA_STABILIZE=off ...               # xem ảnh camera chưa chống rung, để so sánh
DUCK_SIM_POLICIES=<thư-mục> ...                 # dùng bộ policy khác
```

Muốn quay về bản leo cũ thì chép `policies-biped60/climb_v2.onnx` đè lên `climb.onnx`.

## Huấn luyện (trong `microduck_rl`)

```bash
scripts/train_biped60.sh                                # đi sàn phẳng (Mjlab-Velocity-Flat-Biped60)
scripts/train_biped60_stairs.sh 2000 <tên-run>          # học thêm trên bậc thang
TASK=Mjlab-Velocity-Stairs-Climb-Biped60 \
  FROM_RUN=<run-climb_v2> FROM_CKPT=model_10400.pt \
  scripts/train_biped60_stairs.sh 1500 biped60_stairs_climb_v5   # kỹ năng leo

.venv/bin/python scripts/export.py Mjlab-Velocity-Stairs-Climb-Biped60 \
  --checkpoint-file <run>/model_11600.pt --onnx-file exports/climb.onnx --num-envs 1

.venv/bin/tensorboard --logdir logs/rsl_rl/biped60_velocity     # xem biểu đồ huấn luyện
```

Hai script đánh giá trên CPU, chạy nhanh hơn `duck-sim`:

- `scripts/biped60_eval.py`: các bài đứng yên, đi, lùi, bước ngang, quay, tới đích.
- `scripts/biped60_stairs_rate.py`: tỉ lệ qua cầu thang theo từng độ cao bậc.

Sau cùng vẫn phải chạy lại trong `duck-sim`.

## Hạn chế

- **Mọi kết quả đều trong mô phỏng.** BIPED-C3 chưa có bản cứng. Khối lượng là ước lượng, chưa có số đo
  từ CAD.
- **Cầu thang chỉ thử tới bậc 3 cm**, đi thẳng vào thang. Kỹ năng leo được huấn luyện với bậc 2–4 cm.
- **Robot "nhìn thấy" bậc nhờ đọc bản đồ của trình mô phỏng.** Trên robot thật, cần cảm biến (ToF,
  camera độ sâu) để đo mép bậc.
- **Các script dẫn đường lấy vị trí robot trực tiếp từ trình mô phỏng.** Odometry của `robotd` vẫn tính
  theo mô hình của vịt nên chưa dùng được.
- **Nhặt đồ là mẹo của mô phỏng.** Robot không có tay hay mỏ để gắp; trình mô phỏng "gắn" đồ vào robot
  khi chạm tới.
- **Phần làm mượt vị trí camera chỉ có trong mô phỏng.** Camera thật không dịch chuyển được. Muốn giữ
  ngang chân trời thì phải xoay và cắt ảnh.
- **Thân robot vẫn lắc khoảng 30 °/s khi leo.** Phạt lắc mạnh hơn thì robot dừng trước bậc thay vì leo.
- **Bước ngang còn yếu** (đi được khoảng 0,5 m khi được lệnh 1,25 m). Robot đi khoảng 85% tốc độ được
  lệnh.

## Hướng phát triển

- Dùng cảm biến thật (ToF hoặc camera độ sâu) để đo bậc, và huấn luyện với dữ liệu cảm biến có nhiễu.
- Viết odometry theo mô hình BIPED-C3 để robot tự dẫn đường, không cần vị trí từ trình mô phỏng.
- Kỹ năng leo bậc cao hơn, cầu thang có chỗ rẽ, và đi xuống mượt hơn.
- Thiết kế CAD và kiểm chứng trên robot thật.
- Đưa bản sửa đổi của `microduck_rl` lên GitHub để người khác chạy lại được.
