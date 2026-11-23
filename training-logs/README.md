# Log huấn luyện BIPED-C3

Log và cấu hình của **16 lần train** policy đi bộ, leo thang và kỹ năng leo của robot BIPED-C3, từ
18/11 đến 21/11/2026, kèm cấu hình máy và GPU. Tổng cộng **22.851 vòng lặp PPO**, khoảng **13,2 giờ GPU**.

```
training-logs/
├── README.md                     file này
├── runs_summary.csv              mỗi lần train một dòng: bài, checkpoint xuất phát, số vòng, thời gian, tốc độ, kết thúc
├── runs/<lần-train>/
│   ├── console.log.gz            log console đầy đủ (từng vòng: reward, loss, tốc độ, các thành phần reward)
│   ├── scalars.csv               toàn bộ số liệu TensorBoard, mỗi vòng lặp một dòng
│   ├── agent.yaml                cấu hình PPO và mạng nơ-ron
│   └── env.yaml                  cấu hình môi trường: reward, địa hình, nhiễu ngẫu nhiên, mô phỏng
├── system/
│   ├── system_and_software.txt   CPU, RAM, GPU, driver, phiên bản thư viện
│   ├── nvidia-smi-q.txt          thông tin chi tiết GPU (nvidia-smi -q)
│   ├── gpu_samples_probe.csv     mức dùng GPU mỗi giây khi train (xem mục 2)
│   └── probe_train_console.log.gz
└── plots/
    ├── reward_curves.png         reward theo vòng lặp, chuỗi policy đang dùng
    ├── episode_length_curves.png độ dài episode theo vòng lặp
    ├── throughput.png            tốc độ train của từng lần
    └── gpu_usage_probe.png       mức dùng GPU, bộ nhớ, công suất khi train
```

## 1. Cấu hình máy

| Thành phần | Thông số |
|---|---|
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU (Ada Lovelace, compute capability 8.9, 24 SM) |
| Bộ nhớ GPU | 8 GB GDDR6 (8188 MiB), xung nhớ tối đa 8001 MHz |
| Xung GPU tối đa | 3105 MHz |
| Giới hạn công suất GPU | 140 W |
| Kết nối | PCIe Gen 4 x8 |
| Driver | 595.99.02 (CUDA driver 13.2) |
| CPU | Intel Core i7-13620H (10 nhân, 16 luồng) |
| RAM | 16 GB |
| Hệ điều hành | Ubuntu 22.04.5 LTS, kernel 6.8 |

| Phần mềm | Phiên bản |
|---|---|
| Python | 3.12.14 |
| PyTorch | 2.9.1 (CUDA 12.8, cuDNN 9.10) |
| mjlab | 1.3.0 |
| rsl-rl-lib (PPO) | 5.0.1 |
| NVIDIA Warp | 1.12.0 |
| MuJoCo / MuJoCo Warp | 3.10.0 / 3.8.1 |
| ONNX Runtime | 1.24.4 |
| TensorBoard | 2.20.0 |

## 2. Mức dùng GPU khi train

Lúc train thật, mức dùng GPU không được ghi lại. Vì vậy ngày 23/11/2026, bài leo thang (`climb_v5`)
được chạy lại 60 vòng với đúng cấu hình cũ: 2048 môi trường, xuất phát từ cùng checkpoint. Trong lúc
chạy, `nvidia-smi` ghi lại mỗi giây. Tốc độ lần chạy lại là 28.643 bước/giây, gần như bằng lần train
thật (28.731), nên các số dưới đây đại diện được cho lúc train.

| Chỉ số (lúc đang train, 102 giây) | Giá trị |
|---|---|
| Mức dùng GPU | trung bình **78%**, cao nhất 95% |
| Bộ nhớ GPU | **2,9 GiB** / 8 GiB |
| Công suất | trung bình **61 W**, cao nhất 64 W (giới hạn 140 W) |
| Nhiệt độ | trung bình 63 °C, cao nhất 68 °C |
| Xung GPU | khoảng 2,6 GHz |
| Thời gian một vòng lặp | 1,72 s: thu thập dữ liệu (mô phỏng) 1,52 s, cập nhật mạng 0,20 s |
| Khởi động trước vòng đầu | khoảng 15 s: nạp mô hình, dựng địa hình, tạo CUDA graph |

**Số môi trường song song:**
- Đi sàn phẳng (`flat_v1`, `flat_v2`): **4096** môi trường, khoảng 37–40 nghìn bước/giây.
- Bậc thang: **2048** môi trường. Thử 4096 thì bị lỗi hết bộ nhớ GPU ngay lúc tạo CUDA graph (Warp CUDA
  error 2: out of memory, xem `runs/*stairs_v1/console.log.gz`).
  - Bài đi bộ trên bậc: khoảng 25–26 nghìn bước/giây.
  - Kỹ năng leo: khoảng 29 nghìn bước/giây.

## 3. Cấu hình huấn luyện

| Mục | Giá trị |
|---|---|
| Thuật toán | PPO (rsl-rl-lib), thêm loss đối xứng trái/phải (mirror loss, hệ số 0,5; trừ `flat_v1`) |
| Mạng actor / critic | MLP 512 → 256 → 128, kích hoạt ELU, chuẩn hoá quan sát |
| Phân phối hành động | Gauss, độ lệch chuẩn ban đầu 1,0 |
| Số bước mỗi môi trường mỗi vòng | 24 → 49.152 mẫu mỗi vòng (2048 môi trường) |
| Mini-batch / epoch | 4 mini-batch, 5 epoch mỗi vòng |
| Learning rate | 0,001, tự điều chỉnh theo KL (KL mục tiêu 0,01; từ `stairs_v3` trở đi là 0,006) |
| γ / λ (GAE) | 0,99 / 0,95 |
| Hệ số entropy / clip | 0,01 / 0,2 |
| Giới hạn gradient | 1,0 |
| Seed | 42 |
| Lưu checkpoint | mỗi 100 vòng |
| Mô phỏng | bước vật lý 5 ms, điều khiển 50 Hz (mỗi 4 bước vật lý), episode 20 s |

Chi tiết reward, địa hình và nhiễu ngẫu nhiên (khối lượng, trọng tâm, ma sát khớp, xô đẩy, lệch IMU)
của từng lần nằm trong `env.yaml`.

## 4. Các lần train

Số vòng lặp được đếm nối tiếp. Mỗi lần học tiếp từ checkpoint của lần trước, nên vòng lặp không bắt đầu
từ 0.

| Lần train | Bài | Xuất phát từ | Vòng lặp | Thời gian | Kết quả |
|---|---|---|---|---|---|
| `flat_v1` | Đi sàn phẳng | từ đầu | 0–481 | 0:20 | Dừng sớm: robot tự xoay vòng khi được lệnh đứng yên |
| `flat_v2` | Đi sàn phẳng | từ đầu | 0–5999 | 4:26 | Xong. **model_5999** làm nền cho mọi bài sau |
| `stairs_v1` | Lên bậc 1–5 cm | flat_v2 / 5999 | 5999–8066 | 1:06 | Dừng sớm: quên cách quay |
| `stairs_v2` | Lên bậc 1–5 cm | flat_v2 / 5999 | 5999–8998 | 1:35 | Xong. Chọn **model_8000** |
| `stairs_v3` | + giữ thân ổn định | stairs_v2 / 8000 | 8000–9999 | 1:03 | Xong, không dùng: hết leo được bậc 3 cm |
| `stairs_v4` | Rải đều độ cao bậc | stairs_v2 / 8000 | 8000–9499 | 0:47 | Xong. Chọn **model_9000** |
| `stairs_v5` | + giữ thân, đầu ổn định | stairs_v4 / 9000 | 9000–10104 | 0:36 | Dừng sớm. **model_9800 = `alpha_walking.onnx` (đang dùng)** |
| `stairs_v6` | + phạt vấp | stairs_v5 / 10100 | 10100–10736 | 0:21 | Dừng sớm: lùi bước nhiều hơn |
| `stairs_v7` | v4 + giữ hướng nhìn | stairs_v4 / 9000 | 9000–9705 | 0:23 | Dừng sớm: lùi bước nhiều hơn |
| `stairs_v8` | + phạt dẫm mép bậc | stairs_v5 / 9800 | 9800–10403 | 0:20 | Dừng sớm: cải thiện rất ít |
| `stairs_v9_seed` | (không train) | stairs_v5 / 9800 | — | — | Checkpoint được mở thêm ô quan sát địa hình, làm điểm xuất phát |
| `stairs_v9b` | Đi bộ nhìn thấy bậc | v9_seed / 9800 | 9800–10643 | 0:28 | Dừng sớm: kém hơn trong duck-sim |
| `climb_v1` | Kỹ năng leo | v9_seed / 9800 | 9800–10164 | 0:10 | Dừng sớm: không chịu leo. Chỉ còn log console |
| `climb_v2` | Kỹ năng leo + thưởng tiến lên | v9_seed / 9800 | 9800–10923 | 0:31 | Dừng sớm. **model_10400 = `climb_v2.onnx`** (bản leo cũ) |
| `climb_v3` | + giữ đầu ổn định | climb_v2 / 10400 | 10400–10671 | 0:08 | Dừng sớm: đầu nghiêng 17° |
| `climb_v4` | + phạt nghiêng đầu | climb_v2 / 10400 | 10400–11043 | 0:18 | Dừng sớm: khớp đầu càng ép vào chốt |
| `climb_v5` | + phạt lệnh khớp vượt giới hạn | climb_v2 / 10400 | 10400–11899 | 0:43 | Xong. **model_11600 = `climb.onnx` (đang dùng)** |

"Dừng sớm" nghĩa là lần train được dừng tay trước số vòng dự kiến, sau khi đánh giá các checkpoint giữa
chừng cho thấy hướng đó không tốt hơn, hoặc đã có checkpoint tốt. Số liệu đầy đủ (tốc độ, reward, độ
dài episode cuối) nằm trong `runs_summary.csv`.

Thư mục này không gồm các lần train nhảy (`dance`) và lộn (`roll`), vì hai hướng đó đã tạm dừng. Log của
chúng vẫn còn trong `~/Pollen/microduck_rl/logs/rsl_rl/biped60_dance` và `biped60_roll`.

## 5. Cách xem

```bash
zless runs/2026-11-21_14-23-39_biped60_stairs_climb_v5/console.log.gz      # đọc log console
# Biểu đồ tương tác (cần repo huấn luyện):
~/Pollen/microduck_rl/.venv/bin/tensorboard --logdir ~/Pollen/microduck_rl/logs/rsl_rl/biped60_velocity
```

`scalars.csv` mở được bằng Excel hoặc LibreOffice. Các cột hay dùng:

| Cột | Ý nghĩa |
|---|---|
| `Train/mean_reward` | Reward trung bình mỗi episode |
| `Train/mean_episode_length` | Robot trụ được bao nhiêu bước, tối đa 1000 |
| `Perf/total_fps` | Bước mô phỏng mỗi giây |
| `Loss/*` | Các thành phần loss của PPO |
| `Episode_Reward/*` | Từng thành phần reward |

Reward của mỗi bài được tính theo hàm thưởng riêng của bài đó, nên chỉ so được giữa các vòng trong cùng
một bài, không so giữa các bài với nhau.
