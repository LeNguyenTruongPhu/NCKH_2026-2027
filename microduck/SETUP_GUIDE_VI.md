# Hướng Dẫn Huấn Luyện Vịt Đi Đứng Không Bị Ngã

## 📋 Tổng Quan Dự Án

Microduck là một robot vịt hai chân nhỏ (~25cm, 800g) chạy trên Rockchip RK3566 với các điều khiển được huấn luyện bằng Deep Reinforcement Learning (PPO + MuJoCo).

### Cấu Trúc Dự Án

```
microduck/
├── robotd/              # Daemon điều khiển chính - vòng lặp 50Hz
├── duck-control/        # Core logic: mô hình, bus, IMU, policy
├── duck-detect/         # Phát hiện vịt/cảm biến
├── padd/                # Đọc gamepad
├── mediad/              # Camera, microphone, WebRTC
├── configd/             # WiFi, tên vịt, cấu hình
├── btd/                 # Bluetooth daemon
├── updater/             # Cập nhật phần mềm
├── robotctl/            # CLI điều khiển cục bộ
├── duckctl/             # Client từ laptop qua Bluetooth
├── kinematics/          # Mô hình MJCF, forward kinematics
├── odometry/            # Xác định vị trí từ foot contacts + IMU
├── scripts/             # Duck simulator, tools
├── spaces/              # Ví dụ Gradio apps
└── docs/                # Tài liệu thiết kế
```

## 🚀 Bắt Đầu Nhanh

### 1. Cài Đặt Dependencies

**Yêu cầu:**
- Rust 1.89+ (stable)
- Linux hoặc macOS
- Python 3.10+

**Linux:**
```bash
# Cài C libraries cần thiết
sudo apt-get install -y libudev-dev libgstreamer1.0-dev
sudo apt-get install -y libgstreamer-plugins-base1.0-dev libgstreamer-plugins-bad1.0-dev

# Clone repository chính
cd ~/Pollen/microduck  # hoặc nơi bạn muốn

# Cài Rust (nếu chưa có)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

**macOS:**
```bash
# Chỉ cần Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

### 2. Build & Test

```bash
# Test toàn bộ codebase
cargo test --workspace

# Build release
cargo build --release

# Test một crate cụ thể
cargo test -p duck-control

# Kiểm tra code style
cargo fmt --all
cargo clippy --all
```

## 🦆 Chạy Simulator (Không Cần Robot Vật Lý)

Microduck cung cấp một simulator MuJoCo cho phép bạn phát triển mà không cần robot thực.

### Điều Kiện Tiên Quyết

```bash
# Cần clone repo huấn luyện (chứa MuJoCo, policies, libonnxruntime)
cd ~/Pollen
git clone https://github.com/pollen-robotics/microduck_rl.git
cd microduck_rl
python -m venv venv
source venv/bin/activate  # hoặc `venv\Scripts\activate` trên Windows
pip install -r requirements.txt
```

### Chạy Một Vịt (Simple Mode)

```bash
cd ~/Pollen/microduck
scripts/duck-sim              # Cửa sổ MuJoCo mở, vịt đứng dậy
scripts/duck-sim status       # Kiểm tra trạng thái
scripts/duck-sim drive        # Đi tiến 8 giây (vx=0.15, vyaw=0)
scripts/duck-sim ctl health   # Gọi robotctl commands
scripts/duck-sim monitor      # Xem joints, IMU, ToF, game sticks
scripts/duck-sim log          # Xem logs của robotd
scripts/duck-sim realtime     # Kiểm tra tốc độ chạy
scripts/duck-sim down         # Tắt
```

### Chạy Nhiều Vịt (Container Mode)

```bash
# Cài đặt (lần đầu)
sudo apt-get install -y systemd-container mmdebstrap

# Chạy 4 vịt trong containers, mỗi con là một systemd machine
scripts/duck-sim boot 4

# Đăng nhập vào duck-a
scripts/duck-sim shell
# hoặc
scripts/duck-sim shell duck-c

# Trong machine
duck-a # robotctl health
duck-a # journalctl -u robotd -f

# Dừng tất cả
scripts/duck-sim down
```

## 🧠 Huấn Luyện Policy (Huấn Luyện Để Đi Bộ/Đứng)

**Lưu ý quan trọng:** Huấn luyện policy không nằm trong repo này. Nó nằm trong repo `microduck_rl`.

### Bước 1: Clone & Setup microduck_rl

```bash
cd ~/Pollen
git clone https://github.com/pollen-robotics/microduck_rl.git
cd microduck_rl
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Bước 2: Huấn Luyện Policy

```bash
# Xem README của microduck_rl để chi tiết
cd ~/Pollen/microduck_rl

# Huấn luyện walking policy
python -m duck_rl.train \
    --task walking \
    --model-dir ./models/walking \
    --num-envs 4 \
    --num-steps 10000000

# Huấn luyện standing policy
python -m duck_rl.train \
    --task standing \
    --model-dir ./models/standing \
    --num-envs 4 \
    --num-steps 5000000
```

### Bước 3: Export Policy sang ONNX

```bash
# Policy huấn luyện được lưu dưới dạng PyTorch
# Export sang ONNX để robot có thể tải
python -m duck_rl.export \
    --model-path ./models/walking/checkpoint.pt \
    --output ./models/walking.onnx
```

### Bước 4: Sử Dụng Policy

```bash
# Copy vào thư mục policies của microduck
cp ./models/walking.onnx ~/Pollen/microduck/policies/

# Hoặc sử dụng trực tiếp trong simulator
export DUCK_POLICIES_DIR=~/Pollen/microduck_rl/models
cd ~/Pollen/microduck
scripts/duck-sim drive
```

## 🔧 Kiểu Điều Khiển

### Gamepad

```bash
# Kết nối gamepad
robotctl gamepad pair

# Bấm D-pad để điều khiển
# Left Stick: vận tốc (x, y)
# Right Stick: yaw (quay)
# Buttons: các hành động (bước, tay, ngồi, đứng dậy)
```

### Từ Laptop (duckctl)

```bash
# Điều khiển qua Bluetooth (không cần network)
duckctl --robot duck.local drive 0.15 0  # Đi tiến

# Hoặc qua mô phỏng
scripts/duck-sim ctl drive 0.15 0
```

### Từ Python Script

```python
# Xem spaces/policy-shop/control.py để chi tiết

from shared.control import Rpc

rpc = Rpc()

# Gửi lệnh đi
rpc.call("robot.setSkill", {"skill": "walk", "vx": 0.15, "vyaw": 0})

# Nhận trạng thái
state = rpc.notifications.get("robot.state", {})
print(state)
```

## 📊 Cấu Trúc Mô Hình & Kinematics

### Forward Kinematics

```bash
# Trong thư mục kinematics/
# Mô hình MJCF (MuJoCo XML) mô tả hình học vịt

# 15 joint (servos):
# - 3 trên mỗi chân (hip, knee, ankle)
# - 2 ở bụng (roll, pitch)
# - 2 ở cổ (yaw, pitch)
# - 2 ở tay (shoulder, elbow)
# - 1 ở mỏ (beak)

ls kinematics/models/duck.mjcf
```

## 📝 Quá Trình Kiểm Tra Lỗi

### 1. Kiểm Tra Code

```bash
# Format code
cargo fmt --all

# Lint (catches common mistakes)
cargo clippy --all

# Lint cho aarch64 (target của robot)
RUSTFLAGS="-D warnings" cargo clippy --all-targets --target aarch64-unknown-linux-gnu
```

### 2. Chạy Unit Tests

```bash
cargo test --workspace
cargo test -p duck-control  # Test control logic
cargo test -p robotd        # Test daemon logic
```

### 3. Theo Dõi Logs

```bash
# Simulator
scripts/duck-sim log

# Hoặc trên robot thực
robotctl log
robotctl log -f  # Follow mode (tail -f)
```

### 4. Monitor Trạng Thái

```bash
# Kiểm tra sức khỏe
scripts/duck-sim ctl health

# Chi tiết từng servo
scripts/duck-sim ctl monitor

# Từ Python
duckctl --robot duck.local monitor
```

## 🔌 Deploy lên Robot Thực

### Cơ Bản (Qua SSH)

```bash
# Từ laptop
scripts/dev-push.sh robot@192.168.1.100

# Hoặc sử dụng Docker
scripts/dev-push.sh --docker robot@192.168.1.100
```

### Release (Chính Thức)

```bash
# Ký tên artifact (cần keys)
cargo xtask package
cargo xtask sign
cargo xtask promote

# Hoặc từ CI/CD
git tag v1.0.0
git push origin v1.0.0  # GitHub Actions tự động build & release
```

## 🐛 Vấn Đề Thường Gặp

### Vịt Không Đứng Dậy
- Kiểm tra policy được load chính xác: `scripts/duck-sim ctl health`
- Kiểm tra ONNX runtime: `ls ~/.cache/duck-sim/logs/robotd.log`
- Xác minh ONNX file không bị hỏng: `cargo run -p duck-control --example policy-rehearsal`

### Vịt Bị Ngã
- Điều chỉnh tham số safety trong `robotd/src/safety.rs`
- Kiểm tra kiến thức về balance từ IMU
- Tăng feedback từ foot contact
- Huấn luyện lại policy với domain randomization

### Lỗi ONNX Runtime
```bash
# Kiểm tra version
cat Cargo.toml | grep ort

# Kiểm tra trên robot
ls /opt/onnxruntime/lib/

# Cập nhật nếu cần
scripts/setup-board.sh
```

### MuJoCo Simulator Không Mở
```bash
# Kiểm tra microduck_rl setup
cd ~/Pollen/microduck_rl
source venv/bin/activate
python -c "import mujoco; print(mujoco.__file__)"

# Hoặc chạy duck-body trực tiếp
python -m duck_rl.duck_body
```

## 📚 Tài Liệu Thêm

- **Architecture Overview**: `docs/design/architecture.md`
- **Control Loop Design**: `docs/design/robotd-design.md`
- **Policy Channel**: `docs/design/policy-channel-design.md`
- **Simulation Design**: `docs/design/simulation.md`
- **Update Engine**: `docs/design/updater-design.md`
- **Cheat Sheet**: `docs/robot/cheatsheet.md`
- **Dev Cheat Sheet**: `docs/robot/cheatsheet-dev.md`

## 🔗 Liên Kết Quan Trọng

- [Trang Chủ Pollen Robotics](https://pollen-robotics.com/microduck)
- [Repository Huấn Luyện (microduck_rl)](https://github.com/pollen-robotics/microduck_rl)
- [Repository Chính](https://github.com/pollen-robotics/microduck)

## 💡 Mẹo Phát Triển

1. **Phát triển trước, sau đó test**
   ```bash
   cargo build --release
   cargo test --all
   ```

2. **Sử dụng simulator trước khi push lên robot**
   ```bash
   scripts/duck-sim drive 0.15 0
   # Nếu nó hoạt động trong sim, nó sẽ hoạt động trên robot
   ```

3. **Sử dụng git workflow đúng**
   ```bash
   git checkout -b feature/better-balance
   # ... commit changes ...
   git push origin feature/better-balance
   # Tạo PR, chạy CI, merge
   ```

4. **Giữ cho servo mát**
   - Không để vịt chạy liên tục > 30 phút
   - Kiểm tra nhiệt độ servo: `robotctl ctl --health`
   - Dừng nếu nhiệt độ > 60°C

5. **Lưu trữ logs từ các lần chạy**
   ```bash
   robotctl log > duck_session_$(date +%s).log
   ```

## 🎯 Quy Trình Huấn Luyện Đầy Đủ

```bash
# 1. Clone repo
git clone https://github.com/pollen-robotics/microduck_rl.git
cd microduck_rl
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Huấn luyện policy (đó là phần nặng)
python -m duck_rl.train --task standing --num-steps 5000000

# 3. Export ONNX
python -m duck_rl.export --model-path ./models/standing/latest.pt

# 4. Test trong simulator
cd ../microduck
export DUCK_POLICIES_DIR=../microduck_rl/models
scripts/duck-sim drive 0.15 0

# 5. Nếu tốt, deploy lên robot
scripts/dev-push.sh robot@ip.address

# 6. Test trên robot
duckctl --robot duck.local drive 0.15 0
```

---

**Chúc bạn thành công huấn luyện vịt! 🦆**
