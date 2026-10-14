# 🎮 Hướng Dẫn Chi Tiết: Chạy Mô Phỏng Vịt

**Simulator là cách an toàn nhất để test policy trước khi đưa lên robot thực!**

---

## 📋 Yêu Cầu Trước Tiên

### 1. Chuẩn Bị Môi Trường

```bash
# Cần cả 2 repo:
cd ~/Pollen
ls -d microduck microduck_rl

# Nếu chưa có microduck_rl:
git clone https://github.com/pollen-robotics/microduck_rl.git

# Nếu chưa có microduck:
git clone https://github.com/pollen-robotics/microduck.git
```

### 2. Build Microduck (Firmware)

```bash
cd ~/Pollen/microduck

# Kiểm tra Rust
rustc --version  # Phải >= 1.89

# Build release
cargo build --release

# Test (tất cả phải pass)
cargo test --workspace
```

### 3. Setup microduck_rl (Training/Policies)

```bash
cd ~/Pollen/microduck_rl

# Python environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify
python -c "import mujoco; print('MuJoCo OK')"
python -c "import torch; print('PyTorch OK')"
```

---

## 🚀 Lệnh Chạy Mô Phỏng

### **1. Cách Đơn Giản Nhất (Recommended)**

```bash
cd ~/Pollen/microduck

# Chạy simulator
scripts/duck-sim up

# ✓ Một cửa sổ MuJoCo mở ra
# ✓ Vịt đứng dậy
# ✓ Bạn có thể điều khiển từ terminal khác
```

**Ví dụ: Điều khiển từ terminal khác**
```bash
# Terminal 2 - Điều khiển
cd ~/Pollen/microduck

scripts/duck-sim drive 0.15 0     # Đi tiến
scripts/duck-sim drive -0.15 0    # Lùi
scripts/duck-sim drive 0 0.5      # Quay trái
scripts/duck-sim drive 0 -0.5     # Quay phải
scripts/duck-sim drive 0.1 0.2    # Đi xiên

# Dừng
scripts/duck-sim drive 0 0
scripts/duck-sim down             # Tắt simulator
```

---

## 🎯 Các Lệnh Điều Khiển Chi Tiết

### **A. Lệnh Chính**

```bash
cd ~/Pollen/microduck

# Bắt đầu simulator
scripts/duck-sim up

# Dừng simulator
scripts/duck-sim down

# Xem trạng thái
scripts/duck-sim status

# Xem logs
scripts/duck-sim log

# Tail logs (live)
scripts/duck-sim log -f
```

### **B. Điều Khiển Chuyển Động**

```bash
# Cú pháp: scripts/duck-sim drive <vx> <vyaw>
#   vx   = vận tốc trục X (tiến/lùi) -0.5 đến 0.5 m/s
#   vyaw = vận tốc quay (yaw) -1.0 đến 1.0 rad/s

# Đi tiến
scripts/duck-sim drive 0.15 0

# Lùi
scripts/duck-sim drive -0.15 0

# Quay trái
scripts/duck-sim drive 0 0.5

# Quay phải
scripts/duck-sim drive 0 -0.5

# Xiên phải
scripts/duck-sim drive 0.1 -0.3

# Dừng
scripts/duck-sim drive 0 0

# Đi nhanh
scripts/duck-sim drive 0.3 0

# Đi chậm
scripts/duck-sim drive 0.05 0
```

### **C. Hành Động Khác**

```bash
# Đứng im
scripts/duck-sim ctl setSkill stand

# Bước đi
scripts/duck-sim ctl setSkill walk

# Ngồi
scripts/duck-sim ctl setSkill sit

# Lay cái gì đó
scripts/duck-sim ctl setSkill grab

# Kick (đá)
scripts/duck-sim ctl setSkill kick

# Quack (kêu)
scripts/duck-sim ctl quack

# Đứng dậy (nếu ngã)
scripts/duck-sim ctl getup
```

### **D. Monitoring & Debug**

```bash
# Xem sức khỏe (health)
scripts/duck-sim ctl health

# Giám sát chi tiết (monitor)
scripts/duck-sim monitor
# Hiển thị: servo angles, IMU, ToF, contacts

# Xem tốc độ mô phỏng
scripts/duck-sim realtime
# Output: 0.98 = 98% real-time speed

# Xem chi tiết của 1 servo
scripts/duck-sim ctl servo 0

# Thiết lập tốc độ mô phỏng
scripts/duck-sim ctl setTimescale 1.0  # Normal (1x)
scripts/duck-sim ctl setTimescale 2.0  # 2x faster
scripts/duck-sim ctl setTimescale 0.5  # 0.5x slower
```

---

## 📊 Giám Sát Quá Trình Chạy

### **Setup Monitoring (3 Terminal)**

**Terminal 1: Chạy Simulator**
```bash
cd ~/Pollen/microduck
scripts/duck-sim up
```

**Terminal 2: Xem Logs Live**
```bash
cd ~/Pollen/microduck
scripts/duck-sim log -f

# Output:
# [2026-09-11 14:32:10] robotd started
# [2026-09-11 14:32:11] policy loaded: walking.onnx
# [2026-09-11 14:32:12] duck standing
# ...
```

**Terminal 3: Gửi Lệnh & Điều Khiển**
```bash
cd ~/Pollen/microduck

# Chờ vịt đứng dậy
sleep 3

# Test walking
scripts/duck-sim drive 0.15 0
sleep 5
scripts/duck-sim drive 0 0
scripts/duck-sim monitor
```

---

## 🌍 Lệnh Chế Độ Nâng Cao

### **A. Chế Độ Multi-Duck (Nhiều Vịt)**

```bash
cd ~/Pollen/microduck

# Chạy 4 vịt cùng lúc (trong containers)
scripts/duck-sim boot 4

# SSH vào 1 vịt
scripts/duck-sim shell           # → duck-a
scripts/duck-sim shell duck-b    # → duck-b

# Trong container
duck-a$ robotctl health
duck-a$ robotctl monitor
duck-a$ exit

# Dừng tất cả
scripts/duck-sim down
```

### **B. Chế Độ Headless (Không GUI)**

```bash
# Chạy simulator mà không cửa sổ MuJoCo
HEADLESS=1 scripts/duck-sim up

# Vẫn có thể điều khiển từ terminal
scripts/duck-sim drive 0.15 0
```

### **C. Custom Policy**

```bash
# Sử dụng policy khác
export DUCK_POLICY=models/custom_walking.onnx
scripts/duck-sim up

# Hoặc chỉ định thư mục
export DUCK_POLICIES_DIR=/path/to/policies
scripts/duck-sim up
```

---

## 🧪 Test Scenarios (Kịch Bản Test)

### **Scenario 1: Basic Walking Test**
```bash
cd ~/Pollen/microduck
scripts/duck-sim up

# Chờ 2 giây (vịt đứng dậy)
sleep 2

# Test 1: Đi tiến 10 giây
scripts/duck-sim drive 0.15 0
sleep 10
scripts/duck-sim drive 0 0

# Chờ 1 giây
sleep 1

# Test 2: Quay vòng
scripts/duck-sim drive 0 0.5
sleep 4
scripts/duck-sim drive 0 0

# Chờ 1 giây
sleep 1

# Test 3: Xiên
scripts/duck-sim drive 0.1 0.3
sleep 5
scripts/duck-sim drive 0 0

echo "✓ Basic walking test complete"
scripts/duck-sim down
```

### **Scenario 2: Stability Test (Kiểm Tra Ổn Định)**
```bash
cd ~/Pollen/microduck
scripts/duck-sim up

# Đi liên tục 30 giây
for i in {1..6}; do
  echo "Round $i/6..."
  scripts/duck-sim drive 0.15 0
  sleep 5
  scripts/duck-sim drive 0 0.5
  sleep 2
  scripts/duck-sim drive 0 0
  sleep 1
done

# Kiểm tra health
scripts/duck-sim ctl health
# Fall rate should be 0% or very low

scripts/duck-sim down
```

### **Scenario 3: Multi-Terrain Test**
```bash
cd ~/Pollen/microduck
export DUCK_POLICIES_DIR=~/Pollen/microduck_rl/models
scripts/duck-sim up

# Test 1: Default surface
echo "Testing on DEFAULT..."
scripts/duck-sim drive 0.15 0
sleep 5
scripts/duck-sim drive 0 0

# Test 2: Sand terrain (if supported)
# scripts/duck-sim ctl setTerrain sand
# scripts/duck-sim drive 0.10 0  # Slower on sand
# sleep 5
# scripts/duck-sim drive 0 0

# Test 3: Gravel terrain (if supported)
# scripts/duck-sim ctl setTerrain gravel
# scripts/duck-sim drive 0.12 0
# sleep 5
# scripts/duck-sim drive 0 0

scripts/duck-sim down
```

---

## 📈 Xem Metrics & Kết Quả

### **Lệnh Xem Metrics**

```bash
# Real-time monitoring
scripts/duck-sim monitor
# Shows: joint positions, velocities, IMU, foot contacts

# Health status
scripts/duck-sim ctl health
# Output:
#   status: healthy
#   policy_loaded: walking.onnx
#   num_steps: 2500
#   avg_speed: 0.14 m/s
#   falls: 0

# Performance stats
scripts/duck-sim realtime
# Output: 0.97 (97% of real-time speed)
```

### **Lưu Log cho Phân Tích**

```bash
# Capture logs to file
scripts/duck-sim log > simulation_run_$(date +%Y%m%d_%H%M%S).log

# Later: analyze
grep "ERROR" simulation_run_*.log
grep "fall" simulation_run_*.log
grep "policy_loaded" simulation_run_*.log
```

---

## 🔧 Environment Variables (Tùy Chỉnh)

```bash
# Thư mục policy
export DUCK_POLICIES_DIR=~/Pollen/microduck_rl/models

# Bật MuJoCo rendering
export MUJOCO_GL=glfw

# Đặt GPU
export CUDA_VISIBLE_DEVICES=0

# Chế độ debug
export RUST_LOG=debug

# Tốc độ mô phỏng (0.5 = slow-motion, 2.0 = fast-forward)
export MUJOCO_TIMESCALE=1.0

# Số lượng threads
export RAYON_NUM_THREADS=4

# Kết hợp:
export DUCK_POLICIES_DIR=~/Pollen/microduck_rl/models \
       MUJOCO_GL=glfw \
       RUST_LOG=info
scripts/duck-sim up
```

---

## 🎬 Script Tự Động (Automation)

### **Tạo Test Script**

```bash
cat > ~/Pollen/microduck/test_simulator.sh << 'EOF'
#!/bin/bash
set -e

echo "Starting Microduck Simulator Test..."

cd ~/Pollen/microduck
export DUCK_POLICIES_DIR=~/Pollen/microduck_rl/models

# Start simulator
scripts/duck-sim up &
SIM_PID=$!
sleep 3

echo "Running tests..."

# Test 1: Forward
echo "Test 1: Forward walking..."
scripts/duck-sim drive 0.15 0
sleep 5
scripts/duck-sim drive 0 0

# Test 2: Backward
echo "Test 2: Backward walking..."
scripts/duck-sim drive -0.15 0
sleep 5
scripts/duck-sim drive 0 0

# Test 3: Rotation
echo "Test 3: Rotation..."
scripts/duck-sim drive 0 0.5
sleep 4
scripts/duck-sim drive 0 0

# Test 4: Health check
echo "Test 4: Health check..."
scripts/duck-sim ctl health

# Stop simulator
echo "Stopping simulator..."
scripts/duck-sim down

echo "✓ All tests complete!"
wait $SIM_PID
EOF

chmod +x ~/Pollen/microduck/test_simulator.sh

# Run it
~/Pollen/microduck/test_simulator.sh
```

---

## 📱 GUI Commands (Nếu có Web Console)

Nếu simulator có web console:

```bash
# Access web console (nếu available)
http://localhost:8080

# From console, you can:
# - View live camera feed
# - Send commands
# - Monitor sensors
# - See IMU data
# - Check servo positions
```

---

## ⚠️ Troubleshooting Lệnh

### Problem: "Command not found"

```bash
# Fix: Make sure in right directory
cd ~/Pollen/microduck

# Fix: Script needs to be executable
chmod +x scripts/duck-sim

# Fix: Use full path
./scripts/duck-sim up
# or
bash scripts/duck-sim up
```

### Problem: "MuJoCo window doesn't open"

```bash
# Fix: Check display
echo $DISPLAY  # Should not be empty

# Fix: Set display (if SSH)
export DISPLAY=:0
scripts/duck-sim up

# Fix: Use headless mode
HEADLESS=1 scripts/duck-sim up
```

### Problem: "Policy not found"

```bash
# Fix: Set correct policy directory
export DUCK_POLICIES_DIR=~/Pollen/microduck_rl/models
scripts/duck-sim up

# Fix: Check policy file exists
ls -lh $DUCK_POLICIES_DIR/walking.onnx
```

### Problem: "Address already in use"

```bash
# Fix: Previous instance still running
pkill -f duck-sim
pkill -f robotd
pkill -f duck-body

# Then restart
scripts/duck-sim up
```

---

## 📋 Cheatsheet - Lệnh Thường Dùng

```bash
# Quick start
cd ~/Pollen/microduck && scripts/duck-sim up

# Quick stop
scripts/duck-sim down

# Quick test
scripts/duck-sim drive 0.15 0 && sleep 5 && scripts/duck-sim drive 0 0

# Quick health check
scripts/duck-sim ctl health

# Quick logs
scripts/duck-sim log | tail -20

# Clean restart
scripts/duck-sim down; pkill -f duck; sleep 2; scripts/duck-sim up

# Full test cycle
scripts/duck-sim up & sleep 3 && \
  scripts/duck-sim drive 0.15 0 && sleep 5 && \
  scripts/duck-sim drive 0 0 && \
  scripts/duck-sim ctl health && \
  scripts/duck-sim down
```

---

## 🎓 Common Workflows

### **Workflow 1: Policy Testing**

```bash
# 1. Start sim
scripts/duck-sim up

# 2. Wait for startup
sleep 3

# 3. Run your test
scripts/duck-sim drive 0.15 0
sleep 10

# 4. Check if good
scripts/duck-sim monitor

# 5. If good, export policy
cd ~/Pollen/microduck_rl
python -m duck_rl.export --model-path models/best.zip

# 6. Stop sim
cd ~/Pollen/microduck
scripts/duck-sim down
```

### **Workflow 2: Debugging**

```bash
# Terminal 1: Run sim
scripts/duck-sim up

# Terminal 2: Watch logs
scripts/duck-sim log -f

# Terminal 3: Send commands
scripts/duck-sim drive 0.15 0
# Watch Terminal 2 for errors

scripts/duck-sim monitor
# Watch Terminal 2 for debug info

scripts/duck-sim down
```

### **Workflow 3: Recording Data**

```bash
# Terminal 1: Start sim and record
scripts/duck-sim log > run_$(date +%s).log &
scripts/duck-sim up

# Terminal 2: Run test
sleep 3
scripts/duck-sim drive 0.15 0
sleep 10
scripts/duck-sim drive 0 0
scripts/duck-sim ctl health

# Terminal 1: Stop
scripts/duck-sim down

# Analyze
cat run_*.log | grep performance
```

---

## ✅ Checklist: Simulator Ready?

- [ ] Rust installed (`rustc --version`)
- [ ] MuJoCo installed (`python -c "import mujoco"`)
- [ ] PyTorch installed (`python -c "import torch"`)
- [ ] Microduck built (`cargo build --release`)
- [ ] Microduck tests pass (`cargo test --workspace`)
- [ ] microduck_rl cloned
- [ ] duck_rl installed (`python -c "import duck_rl"`)
- [ ] `scripts/duck-sim` executable (`ls -x scripts/duck-sim`)
- [ ] DUCK_POLICIES_DIR set (if needed)
- [ ] Can start: `scripts/duck-sim up` ✓
- [ ] Can control: `scripts/duck-sim drive 0.15 0` ✓
- [ ] Can monitor: `scripts/duck-sim monitor` ✓
- [ ] Can stop: `scripts/duck-sim down` ✓

---

## 📞 Cần Giúp?

```bash
# Get help
scripts/duck-sim --help

# See all commands
scripts/duck-sim
# (lists available commands)

# Check logs for errors
scripts/duck-sim log | grep ERROR

# Check health status
scripts/duck-sim ctl health
```

---

**Ready to simulate!** 🚀

Bất cứ lúc nào gặp vấn đề, hãy check TROUBLESHOOTING.md hoặc logs!
