# Kế Hoạch Thực Hiện Chi Tiết: Huấn Luyện Đa Bề Mặt

## 📋 Tổng Quan

Tài liệu này hướng dẫn từng bước triển khai chiến lược huấn luyện chính sách cho vịt có thể đi bộ trên **cát**, **sỏi**, và **tuyết** mà không bị ngã.

**Timeline:** 14-21 ngày huấn luyện (CPU), 7-10 ngày (GPU)  
**Kết quả cuối cùng:** 1 policy unified xử lý tất cả bề mặt

---

## 📂 Các File Đã Tạo

### 1. **MULTI_TERRAIN_TRAINING_STRATEGY.md** (Chính)
   - 📖 Chi tiết từng phase (5 giai đoạn)
   - 🧬 Domain randomization config
   - 🎯 Reward functions cho từng terrain
   - ✅ Success criteria & metrics

### 2. **train_multiterrain_automated.sh** (Script)
   - 🚀 Tự động chạy tất cả 5 phase
   - 📊 Progress tracking & logging
   - ⏱️ Elapsed time reporting
   - 🔄 Resume capability

### 3. **evaluate_multiterrain.py** (Testing)
   - 📈 Đánh giá policy trên từng terrain
   - 📋 Detailed statistics
   - 💾 JSON output results
   - ✅ Pass/Fail criteria

### 4. **configs/multiterrain_training.yaml** (Config)
   - ⚙️ Toàn bộ hyperparameters
   - 🎓 Curriculum learning schedule
   - 🌍 Terrain-specific settings
   - 📊 Evaluation configuration

---

## 🚀 Bước 1: Chuẩn Bị Môi Trường

### A. Clone và Setup

```bash
# Nếu chưa có repo huấn luyện
cd ~/Pollen
git clone https://github.com/pollen-robotics/microduck_rl.git
cd microduck_rl

# Setup Python environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Optional: Cài đặt GPU support (nếu có NVIDIA GPU)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### B. Kiểm Tra Dependencies

```bash
source venv/bin/activate

# Kiểm tra Python
python --version  # Phải >= 3.8

# Kiểm tra MuJoCo
python -c "import mujoco; print(f'MuJoCo: {mujoco.__version__}')"

# Kiểm tra PyTorch
python -c "import torch; print(f'PyTorch: {torch.__version__}')"
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"

# Kiểm tra duck_rl
python -c "import duck_rl; print('duck_rl OK')"
```

### C. Verify Microduck Main Repo

```bash
cd ~/Pollen/microduck

# Build Rust crates
cargo build --release

# Run tests
cargo test --workspace

# Tất cả phải pass
```

---

## 🎓 Bước 2: Hiểu Chiến Lược (30 min)

Đọc các phần này theo thứ tự:

### Recommended Reading Order

1. **MULTI_TERRAIN_TRAINING_STRATEGY.md**
   - Section: "Phân Tích Vấn Đề" (tại sao khó)
   - Section: "Giải Pháp" (domain randomization)

2. **configs/multiterrain_training.yaml**
   - Đọc toàn bộ file
   - Hiểu từng hyperparameter
   - Note các giá trị key (friction ranges, terrain roughness, etc.)

3. **MULTI_TERRAIN_TRAINING_STRATEGY.md**
   - Section: "5 Giai Đoạn Huấn Luyện"
   - Hiểu progressive difficulty

---

## 🧪 Bước 3: Chọn Phương Án Chạy

### Option A: Fully Automated (Khuyên Dùng)

```bash
cd ~/Pollen/microduck_rl
source venv/bin/activate

# Chạy tất cả 5 phase tự động
../microduck/scripts/train_multiterrain_automated.sh

# Hoặc nếu có GPU
../microduck/scripts/train_multiterrain_automated.sh --gpu
```

**Ưu:** Dễ, không cần can thiệp, logs đủ  
**Nhược:** 14-21 ngày chạy, không thể điều chỉnh giữa đường

### Option B: Manual Phases (Linh Hoạt)

Chạy từng phase một, kiểm tra kết quả:

```bash
cd ~/Pollen/microduck_rl
source venv/bin/activate

# Phase 1: Baseline (10M steps)
python -m duck_rl.train \
    --task walking \
    --model-dir ./models/stage1_baseline \
    --total-timesteps 10000000 \
    --learning-rate 3e-4 \
    --num-envs 8

# Kiểm tra metrics
# (Cần return > 280, fall_rate < 2%)
# Nếu OK, lưu:
cp models/stage1_baseline/best_model.zip models/stage1_baseline_final.zip

# Phase 2: Randomization (5M steps)
python -m duck_rl.train \
    --task walking \
    --model-dir ./models/stage2_randomized \
    --total-timesteps 5000000 \
    --learning-rate 2e-4 \
    --num-envs 16 \
    --friction-range "(0.3, 1.2)" \
    --resume-from ./models/stage1_baseline_final.zip

# ... etc (xem MULTI_TERRAIN_TRAINING_STRATEGY.md for details)
```

**Ưu:** Có kiểm soát, có thể điều chỉnh giữa đường  
**Nhược:** Cần can thiệp thường xuyên, dễ quên step

### Option C: Resume from Previous Training

```bash
# Nếu training bị gián đoạn
../microduck/scripts/train_multiterrain_automated.sh --skip-phase 3 --resume-from ./models/stage2_randomized_final.zip
```

---

## 📊 Bước 4: Monitoring Training (Quan Trọng!)

### Terminal 1: Chạy Training

```bash
cd ~/Pollen/microduck_rl
source venv/bin/activate
./train_multiterrain_automated.sh --gpu  # hoặc tên script
```

### Terminal 2: Xem Training Logs

```bash
cd ~/Pollen/microduck_rl
tail -f logs/training.log
```

### Terminal 3: Xem TensorBoard

```bash
cd ~/Pollen/microduck_rl
tensorboard --logdir=./models --port=6006
# Mở browser: http://localhost:6006
```

### Metrics Để Watch

```
Phase 1 (Baseline):
✓ Return nên tăng: 50 → 150 → 280
✓ Episode length: 10s → 25s → 50s+
✓ Fall rate giảm: 15% → 8% → 3%

Phase 2 (Randomized):
✓ Return có thể giảm lúc đầu (normal)
✓ Nên recover: 200 → 260+
✓ Fall rate: 8% → 4%

Phase 3 (Terrain-Specific):
✓ Sand: 200+
✓ Gravel: 180+
✓ Snow: 160+

Phase 4 (Multi-Terrain):
✓ Unified return: 200+
✓ Hoạt động trên tất cả terrain
✓ Fall rate: < 5% on all
```

### Red Flags (Dừng & Fix)

```
🚨 Return diverges to -1000 → LR quá cao, giảm 10x
🚨 Return stuck/decreasing → Không converge, tăng num_envs
🚨 NaN/Inf in loss → Network overflow, giảm learning_rate
🚨 Memory error → Giảm batch_size hoặc num_envs
```

---

## 🔧 Bước 5: Chế Độ Huấn Luyện (GPU vs CPU)

### GPU (Nhanh - Khuyên Dùng Nếu Có)

```bash
# Check GPU
nvidia-smi

# Install GPU support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Run with GPU
export CUDA_VISIBLE_DEVICES=0
./train_multiterrain_automated.sh --gpu

# Timeline:
# - Phase 1: 1-2 ngày
# - Phase 2: 1 ngày
# - Phase 3: 1.5 ngày
# - Phase 4: 2-3 ngày
# - Phase 5: 0.5 ngày
# Total: 7-10 ngày
```

### CPU (Chậm - Nếu Không Có GPU)

```bash
# Just run (no GPU setup needed)
./train_multiterrain_automated.sh

# Timeline:
# - Phase 1: 3-4 ngày
# - Phase 2: 2-3 ngày
# - Phase 3: 3-4 ngày
# - Phase 4: 5-8 ngày
# - Phase 5: 1-2 ngày
# Total: 14-21 ngày

# Optimize: Giảm num_envs
--num-envs 4  # instead of 32
```

---

## ✅ Bước 6: Kiểm Tra Kết Quả Từng Phase

### Sau Mỗi Phase

```bash
# Xem metrics
tail -100 logs/phase1.log | grep -E "(Return|Episode|fall)"

# Xem best model
ls -lh models/stage1_baseline_final.zip
```

### Success Criteria Cho Từng Phase

```yaml
Phase 1 (Baseline):
  - Return: > 280 ✓
  - Episode length: > 45s ✓
  - Fall rate: < 2% ✓

Phase 2 (Randomized):
  - Return: > 250 ✓ (lower ok due to randomization)
  - Episode length: > 40s ✓
  - Fall rate: < 5% ✓

Phase 3 (Terrain-Specific):
  - Sand return: > 200 ✓
  - Gravel return: > 180 ✓
  - Snow return: > 160 ✓

Phase 4 (Multi-Terrain):
  - Unified return: > 200 ✓
  - Fall rate all terrains: < 5% ✓
  - Consistent on transitions ✓

Phase 5 (Recovery):
  - Getup success rate: > 60% ✓
```

---

## 🔄 Bước 7: Export Policies

### Sau Khi Training Hoàn Tất

```bash
cd ~/Pollen/microduck_rl
source venv/bin/activate

# Export main policy
python -m duck_rl.export \
    --model-path models/stage4_multiterrain_final.zip \
    --output ./models/multiterrain_walking.onnx

# Export recovery policy (nếu training được)
python -m duck_rl.export \
    --model-path models/stage5_getup_final.zip \
    --output ./models/multiterrain_getup.onnx

# Verify files
ls -lh models/*.onnx
# Phải có:
# - multiterrain_walking.onnx (~500KB)
# - multiterrain_getup.onnx (~500KB)
```

---

## 🧪 Bước 8: Evaluate Policy

### Test trên từng terrain

```bash
cd ~/Pollen/microduck_rl
source venv/bin/activate

# Chạy evaluation
python ../microduck/scripts/evaluate_multiterrain.py \
    --model-path models/stage4_multiterrain_final.zip \
    --episodes 20 \
    --output results/evaluation.json

# Xem kết quả
cat results/evaluation.json
```

### Expected Output

```
================================================================================
MULTI-TERRAIN POLICY EVALUATION RESULTS
================================================================================

SAND TERRAIN
  Episodes:            20
  Avg Return:          220.5 ± 15.3
  Avg Episode Length:  50.2 ± 3.1 steps
  Success Rate:        97.5%
  Fall Rate:           2.5%
  Avg Distance:        3.45 m

GRAVEL TERRAIN
  Episodes:            20
  Avg Return:          205.3 ± 18.7
  Avg Episode Length:  47.1 ± 4.2 steps
  Success Rate:        95.0%
  Fall Rate:           5.0%
  Avg Distance:        3.28 m

SNOW TERRAIN
  Episodes:            20
  Avg Return:          185.2 ± 22.1
  Avg Episode Length:  44.5 ± 5.3 steps
  Success Rate:        92.5%
  Fall Rate:           7.5%
  Avg Distance:        3.10 m

DEFAULT TERRAIN
  Episodes:            20
  Avg Return:          265.4 ± 8.2
  Avg Episode Length:  58.3 ± 1.9 steps
  Success Rate:        100%
  Fall Rate:           0%
  Avg Distance:        4.02 m

SUMMARY
  ✓✓✓ POLICY IS READY FOR DEPLOYMENT ✓✓✓
```

---

## 🎮 Bước 9: Test trong Simulator

```bash
cd ~/Pollen/microduck
export DUCK_POLICIES_DIR=../microduck_rl/models

# Start simulator
scripts/duck-sim up

# Trong terminal khác - test commands
scripts/duck-sim drive 0.15 0      # Forward
scripts/duck-sim drive -0.15 0     # Backward
scripts/duck-sim drive 0 0.5       # Spin

# Nếu có terrain switching
scripts/duck-sim ctl setTerrain sand
scripts/duck-sim drive 0.10 0      # Slower on sand

scripts/duck-sim ctl setTerrain gravel
scripts/duck-sim drive 0.15 0

scripts/duck-sim ctl setTerrain snow
scripts/duck-sim drive 0.10 0      # Even slower on slippery

# Monitor
scripts/duck-sim monitor
scripts/duck-sim health

# Stop
scripts/duck-sim down
```

---

## 🤖 Bước 10: Deploy lên Robot Thực

### Chuẩn Bị

```bash
cd ~/Pollen/microduck

# Copy policy
cp ../microduck_rl/models/multiterrain_walking.onnx policies/

# Build release
cargo build --release
```

### Deploy

```bash
# Method 1: Over SSH (nếu có mạng)
scripts/dev-push.sh robot@192.168.1.100

# Method 2: Bluetooth (không cần mạng)
duckctl --robot duck.local push --model multiterrain_walking.onnx
```

### Test trên Robot Thực

```bash
# Check if loaded
duckctl --robot duck.local health
# Phải show: "multiterrain_walking.onnx loaded"

# Test walking
duckctl --robot duck.local drive 0.15 0

# Monitor
duckctl --robot duck.local monitor

# Nếu robot ngã
duckctl --robot duck.local stand  # Turn on getup policy
# Robot sẽ tự động đứng dậy
```

---

## 📋 Checklist Hoàn Thành

- [ ] Setup environment (Python, MuJoCo, PyTorch)
- [ ] Clone microduck_rl repo
- [ ] Đọc MULTI_TERRAIN_TRAINING_STRATEGY.md
- [ ] Chạy training (automated hoặc manual)
- [ ] Monitor training với TensorBoard
- [ ] Phase 1 converges (return > 280)
- [ ] Phase 2 stabilizes (return > 250)
- [ ] Phase 3 learns all terrains
- [ ] Phase 4 unified policy works
- [ ] Export policies to ONNX
- [ ] Evaluate on 10+ episodes each terrain
- [ ] Success rate > 90% on all terrains
- [ ] Fall rate < 5% on all terrains
- [ ] Test in simulator (scripts/duck-sim)
- [ ] Deploy to robot
- [ ] Real robot testing passes
- [ ] Document results

---

## 🆘 Troubleshooting

### Training Diverges

```bash
# Giảm learning rate
--learning-rate 5e-5

# Hoặc tăng clip ratio
--clip-ratio 0.15

# Hoặc resume từ checkpoint tốt hơn
--resume-from models/stage1_baseline_final.zip
```

### Memory Error

```bash
# Giảm batch size
--batch-size 128  # instead of 256

# Hoặc giảm num_envs
--num-envs 16  # instead of 32
```

### Falls ngay khi add randomization

```bash
# Sử dụng curriculum learning
--use-curriculum

# Hoặc tăng training time
--total-timesteps 10000000  # instead of 5000000
```

---

## 📞 Support

1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Check training logs in `logs/`
3. Check TensorBoard for curves
4. Check GitHub issues
5. Email: hello@pollen-robotics.com

---

## 🎉 Kết Quả Mong Đợi

Sau khoảng 2-3 tuần:

✅ Một policy duy nhất xử lý được:
- Cát (high friction, soft)
- Sỏi (uneven, unstable)
- Tuyết (low friction, slippery)

✅ Performance:
- Fall rate < 5% on all terrains
- Walking speed: 0.10-0.15 m/s
- Episode length: 40-60 giây
- Recovery rate: 60-80%

✅ Ready for production deployment!

---

**Chúc bạn thành công!** 🦆

Bất cứ câu hỏi nào, hãy check:
- MULTI_TERRAIN_TRAINING_STRATEGY.md
- TROUBLESHOOTING.md
- configs/multiterrain_training.yaml
