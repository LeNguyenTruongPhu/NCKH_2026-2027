# 🦆 Huấn Luyện Đa Bề Mặt - Tóm Tắt Thực Thi

**Mục Tiêu:** Huấn luyện vịt có thể đi trên **cát, sỏi, tuyết** mà không bị ngã  
**Timeline:** 7-21 ngày (GPU/CPU)  
**Độ Khó:** Trung bình → Cao

---

## 📚 Tài Liệu Chính

| File | Mục Đích | Đọc Lần Đầu? |
|---|---|---|
| **MULTI_TERRAIN_TRAINING_STRATEGY.md** | Chi tiết chiến lược 5 giai đoạn, reward functions, config | ✅ YES - Bắt buộc |
| **IMPLEMENT_MULTITERRAIN_PLAN.md** | Step-by-step implementation, monitoring, troubleshooting | ✅ YES - Sau đó |
| **configs/multiterrain_training.yaml** | Toàn bộ hyperparameters, terrain settings | 📖 Reference |
| **scripts/train_multiterrain_automated.sh** | Bash script tự động chạy tất cả | ▶️ Chạy trực tiếp |
| **scripts/evaluate_multiterrain.py** | Đánh giá policy sau training | 🧪 Sau training |

---

## 🚀 Quick Start (3 Bước)

### 1️⃣ Setup (15 min)

```bash
# Clone training repo
cd ~/Pollen
git clone https://github.com/pollen-robotics/microduck_rl.git
cd microduck_rl

# Setup Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Optional: GPU support
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

### 2️⃣ Train (7-21 ngày)

```bash
# Automated training (tất cả 5 phase)
cd ~/Pollen/microduck_rl
source venv/bin/activate
../microduck/scripts/train_multiterrain_automated.sh --gpu
# Hoặc không GPU: ../microduck/scripts/train_multiterrain_automated.sh
```

**Monitoring:**
```bash
# Terminal khác - xem logs
tail -f logs/training.log

# Terminal thứ 3 - TensorBoard
tensorboard --logdir=./models --port=6006
# Mở: http://localhost:6006
```

### 3️⃣ Test & Deploy (2 giờ)

```bash
# Evaluate
python ../microduck/scripts/evaluate_multiterrain.py \
    --model-path models/stage4_multiterrain_final.zip

# Test in simulator
cd ../microduck
export DUCK_POLICIES_DIR=../microduck_rl/models
scripts/duck-sim up
scripts/duck-sim drive 0.15 0  # Test walking

# Deploy to robot
scripts/dev-push.sh robot@192.168.1.100
duckctl --robot duck.local drive 0.15 0
```

---

## 🧬 Chiến Lược Chi Tiết

### Tại Sao Domain Randomization?

```
Vấn đề: Policy học trên 1 bề mặt → Không hoạt động trên khác

Giải pháp: Huấn luyện với TẤT CẢ variations:
- Friction: 0.1 (tuyết) → 1.3 (cát)
- Roughness: 0 (smooth) → 0.08 (very rough)
- Mass: 0.5x → 2.0x robot weight
- Wind: 0 → 1.0 force
- Servo: Variation trong response time & torque

Kết quả: 1 policy xử lý mọi thứ!
```

### 5 Giai Đoạn Huấn Luyện

```
┌─────────────────────────────────────────────────────┐
│ Phase 1: BASELINE (Smooth)           [10M steps]    │
│ Learn basic walking gait              (3-4 days)    │
│ Expected return: 280+                              │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ Phase 2: RANDOMIZATION (Easy → Medium) [5M steps]   │
│ Add friction, terrain, mass variation (2-3 days)   │
│ Expected return: 250+                              │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ Phase 3: TERRAIN-SPECIFIC [3+3+3 M steps]          │
│ Sand: High friction, soft               (3 days)   │
│ Gravel: Uneven, unstable                (3 days)   │
│ Snow: Low friction, slippery            (3 days)   │
│ Expected returns: Sand 220, Gravel 200, Snow 180   │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ Phase 4: UNIFIED MULTI-TERRAIN [10M steps]         │
│ 1 policy for all terrains              (5-8 days)  │
│ Curriculum: Easy → Medium → Hard                   │
│ Expected return: 200+ on all                       │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ Phase 5: RECOVERY (Get Up) [2M steps]              │
│ Learn to stand up if falls             (1-2 days)  │
│ Expected success rate: 60%+                        │
└─────────────────────────────────────────────────────┘
```

---

## 📊 Expected Performance

### Metrics to Track

```python
# Phase-by-phase progression:

Phase 1:  Return=280  FallRate=3%   EpisodeLen=50s
Phase 2:  Return=260  FallRate=4%   EpisodeLen=48s
Phase 3:  Return=200+ FallRate=5%   EpisodeLen=45s (each terrain)
Phase 4:  Return=200+ FallRate=4%   EpisodeLen=50s (unified)
Phase 5:  RecoveryRate=65% (getup success)

Final:    ✓ Can walk on all terrains
          ✓ Fall rate < 5%
          ✓ Ready for deployment
```

### Success Criteria

```yaml
Minimum Requirements:
  - Fall rate all terrains: < 10%
  - Average return: > 180
  - Episode length: > 35 steps

Good Target:
  - Fall rate: < 5%
  - Average return: > 200
  - Episode length: > 45 steps

Excellent:
  - Fall rate: < 3%
  - Average return: > 250
  - Episode length: > 55 steps
```

---

## 🔧 Configuration Details

### Key Hyperparameters

```yaml
Learning Rate:       1e-4    (conservative)
Batch Size:          256     (large for stability)
PPO Clip Ratio:      0.2     (prevent divergence)
Entropy Coefficient: 0.01    (less exploration)

Friction Range:      0.1 → 1.3  (snow to sand)
Terrain Roughness:   0.0 → 0.08 (smooth to very rough)
Mass Range:          0.5 → 2.0x (±50% variation)
Wind Force:          0.0 → 1.0  (gentle to strong)

Curriculum Stages:
  1. Easy (0-2M steps):   friction 0.8-1.0, low randomization
  2. Medium (2-5M steps): friction 0.5-1.0, medium randomization
  3. Hard (5-10M steps):  friction 0.1-1.3, full randomization
```

### Reward Function Components

```python
total_reward = (
    1.0 * forward_velocity_reward +        # Primary objective
    0.5 * stability_reward +               # Balance
    0.1 * -energy_penalty +                # Efficiency
    0.2 * terrain_bonus +                  # Terrain-specific
    0.01 * survive_bonus +                 # Survive reward
    -10.0 * fall_penalty                   # Heavy penalty for falling
)
```

---

## 💻 Hardware Requirements

### Minimum (CPU Only)
- 8-core CPU
- 16GB RAM
- 100GB disk
- Timeline: **14-21 days**

### Recommended (GPU)
- NVIDIA GPU (RTX 2060 or better)
- 32GB RAM
- 100GB disk
- Timeline: **7-10 days**

### Optimal (Multi-GPU)
- 2x NVIDIA RTX 3090
- 64GB RAM
- 200GB SSD
- Timeline: **3-5 days**

---

## 🎯 Expected Outcomes

### Simulator Performance
```
SAND:    Return 220±15  Fall Rate 2-3%  Speed 0.12-0.15 m/s
GRAVEL:  Return 205±18  Fall Rate 4-5%  Speed 0.10-0.13 m/s
SNOW:    Return 185±22  Fall Rate 6-8%  Speed 0.08-0.10 m/s
DEFAULT: Return 260±8   Fall Rate 0-1%  Speed 0.15 m/s
```

### Real Robot Performance
```
✓ Walks without falling on:
  - Linoleum/tile (like default)
  - Carpet (rough like gravel)
  - Dirt/sand (high friction)
  - Grass (uneven like gravel)

✓ Handles:
  - Small pushes (< 20N)
  - Uneven surfaces
  - Terrain transitions
  - Environmental noise
```

---

## 📋 Complete Workflow

```
Week 1-3: Training
  Day 1:   Phase 1 (baseline)
  Day 2-3: Phase 2 (randomization)
  Day 4-6: Phase 3 (terrain-specific)
  Day 7-8: Phase 4 (unified)
  Day 9:   Phase 5 (recovery)

Week 3: Evaluation & Deployment
  Day 10:  Export to ONNX
  Day 11:  Evaluate on 20 episodes each
  Day 12:  Test in simulator
  Day 13:  Deploy to robot
  Day 14:  Real-world testing
```

---

## ✅ Before Starting

- [ ] Read MULTI_TERRAIN_TRAINING_STRATEGY.md (30 min)
- [ ] Read IMPLEMENT_MULTITERRAIN_PLAN.md (1 hour)
- [ ] Setup Python environment
- [ ] Test dependencies (python, mujoco, torch)
- [ ] Have backup power/cooling for GPU
- [ ] Monitor disk space (training can use 50GB+)
- [ ] Set up logging/monitoring

---

## 🔄 Iteration Loop

If results not good:

```
Falls too often?
  → More training time (+2-3M steps)
  → Stronger domain randomization
  → Higher curriculum difficulty

Slow movement?
  → Increase reward for velocity
  → Longer training
  → Different network architecture

Unstable on one terrain?
  → Fine-tune that terrain config
  → Resume from good checkpoint
  → More steps just for that terrain
```

---

## 🎓 Learning Resources

**Papers to Read:**
- PPO: https://arxiv.org/abs/1707.06347
- Domain Randomization: https://arxiv.org/abs/1703.06907
- Curriculum Learning: https://arxiv.org/abs/1505.00686

**Similar Work:**
- Boston Dynamics QuadrupedRL
- DeepMind Locomotion
- NVIDIA Isaac Gym

---

## 📞 Help & Support

### If Training Fails

1. Check `logs/training.log` for error messages
2. Check `TROUBLESHOOTING.md` section
3. Check TensorBoard for loss curves
4. Try:
   - Reduce learning rate 10x
   - Increase num_envs
   - Restart from Phase 1

### If Policy Doesn't Work

1. Check evaluation metrics
2. Run more episodes (20+)
3. Check if fall in same place?
4. Try different random seed
5. Extend training time

### Questions?

- GitHub Issues: https://github.com/pollen-robotics/microduck/issues
- Email: hello@pollen-robotics.com
- Discord: (if community exists)

---

## 🎉 Success Condition

✅ **You've Succeeded When:**

1. ✓ All training phases complete
2. ✓ Export to ONNX successful
3. ✓ Evaluation: fall rate < 5% on all terrains
4. ✓ Simulator test: duck walks smoothly
5. ✓ Robot deployment: real duck walks on actual surfaces
6. ✓ Real test: goes 10+ meters without falling

**Result:** One unified policy handles multiple terrains! 🎊

---

## 🚀 Next Steps

1. **Now:** Read MULTI_TERRAIN_TRAINING_STRATEGY.md
2. **Then:** Setup environment following IMPLEMENT_MULTITERRAIN_PLAN.md
3. **Run:** `./train_multiterrain_automated.sh --gpu`
4. **Monitor:** Watch TensorBoard & logs
5. **Evaluate:** Run evaluate_multiterrain.py
6. **Deploy:** Push to robot
7. **Celebrate:** Your multi-terrain duck! 🦆

---

**Timeline Start:** [TODAY]  
**Expected Completion:** 7-21 days  
**Result:** Production-ready multi-terrain walking policy  
**Status:** Ready to implement! 🚀

---

**Good luck! Feel free to reach out if you have questions!** 

📧 Email any updates/results to document progress!
