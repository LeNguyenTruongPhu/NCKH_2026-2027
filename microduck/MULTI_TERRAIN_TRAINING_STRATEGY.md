# Chiến Lược Huấn Luyện Chính Sách Đa Bề Mặt

## 🎯 Mục Tiêu

Huấn luyện chính sách (policy) để vịt có thể:
- ✅ Đi trên **cát** (bề mặt soft, nhiều friction)
- ✅ Đi trên **sỏi** (bề mặt uneven, unstable)
- ✅ Đi trên **tuyết** (bề mặt slippery, sinking)
- ✅ Giữ **cân bằng** trên tất cả các bề mặt
- ✅ **Không bị ngã** ngay cả khi bị push

---

## 📊 Phân Tích Vấn Đề

### Tại Sao Khó?

| Bề Mặt | Thách Thức | Impact |
|---|---|---|
| **Cát** | Cao friction, sinking, energy-intensive | Cần lực lớn hơn, mất năng lượng |
| **Sỏi** | Uneven, unstable contact, sliding | Cân bằng khó, foot placement quan trọng |
| **Tuyết** | Low friction, sinking, deformable | Dễ trượt, cần lực bé hơn |

### Giải Pháp

**Domain Randomization** là chìa khóa:
- Thay đổi friction coefficient mỗi episode
- Thay đổi height map (terrain roughness)
- Thay đổi mass distribution
- Thay đổi wind force
- Thay đổi servo response time

Policy được huấn luyện với **tất cả** các variation → **một policy** xử lý tất cả bề mặt

---

## 🏗️ Chuẩn Bị Dự Án

### Bước 1: Clone & Setup

```bash
# Nếu chưa có repo
cd ~/Pollen
git clone https://github.com/pollen-robotics/microduck_rl.git
cd microduck_rl

# Setup Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Hoặc nếu chỉ có microduck
cd ~/Pollen/microduck
git clone https://github.com/pollen-robotics/microduck_rl.git ../microduck_rl
```

### Bước 2: Kiểm Tra Cấu Trúc Training

```bash
# Kiểm tra cấu trúc
cd ~/Pollen/microduck_rl
find . -type f -name "*.py" | grep -E "(train|config|env)" | head -20

# Key files để chỉnh sửa:
# - duck_rl/train.py (script chính)
# - duck_rl/env.py hoặc duck_rl/envs/ (MuJoCo environment)
# - duck_rl/config.py (hyperparameter defaults)
# - duck_rl/reward.py (reward function)
```

---

## 🎓 Chiến Lược Huấn Luyện Chi Tiết

### Phase 1: Huấn Luyện Trên Bề Mặt Mặc Định (5 ngày)

**Mục đích:** Học gait cơ bản trước khi add complexity

```bash
# Train on default smooth surface
python -m duck_rl.train \
    --task walking \
    --model-dir ./models/stage1_baseline \
    --total-timesteps 10000000 \
    --learning-rate 3e-4 \
    --num-envs 8 \
    --seed 42 \
    --friction-range "(0.8, 0.8)" \
    --terrain-roughness 0 \
    --no-randomization
```

**Kết quả mong đợi:**
- Return: > 300
- Episode length: > 45 giây
- Fall rate: < 2%
- Save best model: `stage1_baseline/best_model.zip`

**Commit checkpoint:**
```bash
cp models/stage1_baseline/best_model.zip models/stage1_baseline_final.zip
git add models/stage1_baseline_final.zip
git commit -m "Stage 1: Baseline walking on smooth surface"
```

---

### Phase 2: Thêm Domain Randomization Cơ Bản (3 ngày)

**Mục đích:** Giúp policy adapts với variations

```bash
# Train with basic randomization
python -m duck_rl.train \
    --task walking \
    --model-dir ./models/stage2_randomized \
    --total-timesteps 5000000 \
    --learning-rate 2e-4 \
    --num-envs 16 \
    --seed 42 \
    --friction-range "(0.3, 1.2)" \
    --terrain-roughness "0.02" \
    --mass-range "(0.6, 1.5)" \
    --wind-force 0.5 \
    --resume-from ./models/stage1_baseline_final.zip
```

**Configuration:**
```python
# Trong duck_rl/config.py, thêm vào:

RANDOMIZATION_CONFIG = {
    'friction': {
        'enabled': True,
        'range': (0.3, 1.2),  # Từ slippery đến grippy
        'schedule': 'constant',
    },
    'terrain': {
        'enabled': True,
        'roughness': 0.02,     # Height variation
        'frequency': 0.5,      # Wave frequency
        'octaves': 2,          # Complexity
    },
    'mass': {
        'enabled': True,
        'range': (0.6, 1.5),   # ±40% variation
    },
    'wind': {
        'enabled': True,
        'force_range': (0, 0.5),
        'direction_variation': True,
    },
    'servo': {
        'enabled': True,
        'response_delay': (0, 0.01),
        'max_torque_variation': (0.9, 1.1),
    },
}

# Curriculum learning (tăng dần độ khó)
CURRICULUM = {
    'friction_schedule': [
        (0, 5e6, (0.8, 0.8)),      # First 5M: smooth
        (5e6, 10e6, (0.5, 1.0)),   # Next 5M: some variation
        (10e6, 15e6, (0.2, 1.5)),  # Final: full range
    ],
    'terrain_schedule': [
        (0, 5e6, 0.0),
        (5e6, 10e6, 0.01),
        (10e6, 15e6, 0.03),
    ],
}
```

**Kết quả mong đợi:**
- Return: > 250 (slightly lower due to randomization)
- Episode length: > 40 giây
- Fall rate: < 5%
- Hoạt động trên smooth, medium friction, rough terrains

---

### Phase 3: Terrain-Specific Training (5 ngày)

Huấn luyện separate policies cho từng loại bề mặt, sau đó combine.

#### A. Sand Terrain Policy

```bash
# Cát có high friction + soft (sinking)
python -m duck_rl.train \
    --task walking \
    --model-dir ./models/stage3_sand \
    --total-timesteps 3000000 \
    --learning-rate 1.5e-4 \
    --num-envs 8 \
    --seed 43 \
    --friction-range "(0.9, 1.3)" \
    --terrain-roughness 0.04 \
    --soft-ground True \
    --sinking-depth 0.02 \
    --resume-from ./models/stage2_randomized/best_model.zip
```

**Sand-specific parameters** (thêm vào `reward.py`):
```python
def compute_sand_reward(obs, action):
    # Penalize energy use (cát nhiều friction = tốn năng lượng)
    energy_penalty = -0.1 * torch.sum(action ** 2)
    
    # Reward smooth stride (avoid sinking deeper)
    stride_reward = 0.1 * torch.exp(-foot_sinking_depth)
    
    # Reward low center of mass (stability on soft ground)
    height_penalty = -0.05 * (com_height - target_height) ** 2
    
    return velocity_reward + energy_penalty + stride_reward + height_penalty
```

#### B. Gravel Terrain Policy

```bash
# Sỏi: uneven, unstable, diverse friction
python -m duck_rl.train \
    --task walking \
    --model-dir ./models/stage3_gravel \
    --total-timesteps 3000000 \
    --learning-rate 1.5e-4 \
    --num-envs 8 \
    --seed 44 \
    --friction-range "(0.4, 1.0)" \
    --terrain-roughness 0.08 \
    --terrain-type "rocky" \
    --randomize-foot-contact True \
    --resume-from ./models/stage2_randomized/best_model.zip
```

**Gravel-specific reward**:
```python
def compute_gravel_reward(obs, action):
    # Reward stable foot contact (avoid sliding)
    contact_stability = compute_contact_stability(foot_forces)
    
    # Penalize abrupt joint accelerations (rocky → slipping)
    smoothness_penalty = -0.05 * torch.sum(torch.abs(joint_accelerations))
    
    # Reward correct foot placement (critical on rocks)
    placement_reward = compute_foot_placement_reward(foot_positions, terrain_map)
    
    return velocity_reward + contact_stability + smoothness_penalty + placement_reward
```

#### C. Snow Terrain Policy

```bash
# Tuyết: low friction + deformable, energy-intensive
python -m duck_rl.train \
    --task walking \
    --model-dir ./models/stage3_snow \
    --total-timesteps 3000000 \
    --learning-rate 1.5e-4 \
    --num-envs 8 \
    --seed 45 \
    --friction-range "(0.1, 0.4)" \
    --terrain-roughness 0.03 \
    --deformable-surface True \
    --require-higher-step-frequency True \
    --resume-from ./models/stage2_randomized/best_model.zip
```

**Snow-specific reward**:
```python
def compute_snow_reward(obs, action):
    # Penalize slipping (track relative foot velocity)
    slip_penalty = -0.15 * compute_slip_ratio(foot_vel, terrain_vel)
    
    # Reward frequent stepping (shallow steps on slippery surface)
    step_frequency_reward = 0.1 * measure_step_frequency()
    
    # Penalize energy (snow = harder to walk)
    # But allow higher relative energy cost
    energy_penalty = -0.05 * torch.sum(action ** 2)
    
    return velocity_reward + slip_penalty + step_frequency_reward + energy_penalty
```

**Kết quả mong đợi (mỗi terrain):**
- Sand: return > 200, chậm hơn nhưng ổn định
- Gravel: return > 220, chút fluctuation nhưng không ngã
- Snow: return > 180, cần higher step frequency nhưng hoạt động

---

### Phase 4: Kết Hợp Tất Cả Terrains (3 ngày)

**Mục đích:** Một policy có thể xử lý tất cả bề mặt

```bash
# Train with ALL terrain randomization
python -m duck_rl.train \
    --task walking \
    --model-dir ./models/stage4_multiterrain \
    --total-timesteps 10000000 \
    --learning-rate 1e-4 \
    --num-envs 32 \
    --seed 42 \
    --friction-range "(0.1, 1.3)" \
    --terrain-roughness "random(0.0, 0.08)" \
    --terrain-type "random" \
    --mass-range "(0.5, 2.0)" \
    --wind-force 1.0 \
    --use-curriculum True \
    --curriculum-schedule "aggressive"
```

**Multi-terrain configuration**:
```python
MULTITERRAIN_CONFIG = {
    'friction_distribution': {
        'sand': 0.4,      # 40% episodes on sand
        'gravel': 0.35,   # 35% on gravel
        'snow': 0.25,     # 25% on snow
    },
    'randomization_intensity': {
        'early_training': 0.5,      # Easier at start
        'mid_training': 0.75,       # Medium difficulty
        'late_training': 1.0,       # Full randomization
    },
    'curriculum_steps': [
        (0, 2e6, {'sand': 0.7, 'gravel': 0.2, 'snow': 0.1}, 0.5),
        (2e6, 5e6, {'sand': 0.4, 'gravel': 0.35, 'snow': 0.25}, 0.75),
        (5e6, 10e6, {'sand': 0.33, 'gravel': 0.33, 'snow': 0.34}, 1.0),
    ],
}

# Adaptive reward based on terrain
def compute_adaptive_reward(obs, action, terrain_type):
    base_reward = compute_forward_velocity_reward(obs)
    
    if terrain_type == 'sand':
        return base_reward + compute_sand_reward(obs, action)
    elif terrain_type == 'gravel':
        return base_reward + compute_gravel_reward(obs, action)
    elif terrain_type == 'snow':
        return base_reward + compute_snow_reward(obs, action)
    else:
        return base_reward
```

**Kết quả mong đợi:**
- Return: > 200 across all terrains
- Episode length: > 35 giây trên bất kỳ bề mặt
- Fall rate: < 5% on each terrain type
- Consistent behavior across terrain transitions

---

### Phase 5: Robust Testing & Recovery (2 ngày)

**Huấn luyện recovery policy (getup)** để duck có thể đứng dậy nếu bị ngã

```bash
# Train getup policy specific to different terrains
for terrain in sand gravel snow; do
    python -m duck_rl.train \
        --task getup \
        --model-dir ./models/stage5_getup_$terrain \
        --total-timesteps 2000000 \
        --learning-rate 2e-4 \
        --friction-range "specific_to_$terrain" \
        --seed $((100 + $RANDOM))
done

# Combine getup policies
python scripts/combine_policies.py \
    --policies stage5_getup_sand stage5_getup_gravel stage5_getup_snow \
    --output models/multiterrain_getup.onnx
```

**Fallback mechanism** (trong `robotd`):
```rust
// duck-control/src/policy.rs
pub fn select_policy(state: &RobotState) -> PolicyId {
    if state.is_fallen() {
        return PolicyId::GetUp;  // Use recovery policy
    }
    
    // Detect current terrain
    let terrain = estimate_terrain(&state.foot_contact, &state.imu);
    
    match terrain {
        Terrain::Sand => PolicyId::WalkSand,
        Terrain::Gravel => PolicyId::WalkGravel,
        Terrain::Snow => PolicyId::WalkSnow,
        Terrain::Unknown => PolicyId::WalkMultiterrain,
    }
}
```

---

## 🚀 Quy Trình Thực Thi

### Bước 1: Chuẩn Bị Environment

```bash
cd ~/Pollen/microduck_rl
source venv/bin/activate

# Kiểm tra có MuJoCo không
python -c "import mujoco; print(f'MuJoCo version: {mujoco.__version__}')"

# Nếu không có:
pip install mujoco

# Kiểm tra GPU (nếu có)
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```

### Bước 2: Tạo Script Huấn Luyện Tự Động

```bash
cat > train_multiterrain.sh << 'EOF'
#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Multi-Terrain Training Strategy ===${NC}\n"

# Phase 1: Baseline
echo -e "${GREEN}[PHASE 1] Training baseline on smooth surface...${NC}"
python -m duck_rl.train \
    --task walking \
    --model-dir ./models/stage1_baseline \
    --total-timesteps 10000000 \
    --learning-rate 3e-4 \
    --num-envs 8 \
    --seed 42 \
    --friction-range "(0.8, 0.8)" \
    --terrain-roughness 0

cp models/stage1_baseline/best_model.zip models/stage1_baseline_final.zip

# Phase 2: Basic randomization
echo -e "${GREEN}[PHASE 2] Adding domain randomization...${NC}"
python -m duck_rl.train \
    --task walking \
    --model-dir ./models/stage2_randomized \
    --total-timesteps 5000000 \
    --learning-rate 2e-4 \
    --num-envs 16 \
    --seed 42 \
    --friction-range "(0.3, 1.2)" \
    --terrain-roughness 0.02 \
    --resume-from ./models/stage1_baseline_final.zip

cp models/stage2_randomized/best_model.zip models/stage2_randomized_final.zip

# Phase 3: Terrain-specific
echo -e "${GREEN}[PHASE 3] Training terrain-specific policies...${NC}"

echo "  - Sand terrain..."
python -m duck_rl.train \
    --task walking \
    --model-dir ./models/stage3_sand \
    --total-timesteps 3000000 \
    --learning-rate 1.5e-4 \
    --num-envs 8 \
    --seed 43 \
    --friction-range "(0.9, 1.3)" \
    --terrain-roughness 0.04 \
    --resume-from ./models/stage2_randomized_final.zip

echo "  - Gravel terrain..."
python -m duck_rl.train \
    --task walking \
    --model-dir ./models/stage3_gravel \
    --total-timesteps 3000000 \
    --learning-rate 1.5e-4 \
    --num-envs 8 \
    --seed 44 \
    --friction-range "(0.4, 1.0)" \
    --terrain-roughness 0.08 \
    --resume-from ./models/stage2_randomized_final.zip

echo "  - Snow terrain..."
python -m duck_rl.train \
    --task walking \
    --model-dir ./models/stage3_snow \
    --total-timesteps 3000000 \
    --learning-rate 1.5e-4 \
    --num-envs 8 \
    --seed 45 \
    --friction-range "(0.1, 0.4)" \
    --terrain-roughness 0.03 \
    --resume-from ./models/stage2_randomized_final.zip

# Phase 4: Multi-terrain
echo -e "${GREEN}[PHASE 4] Training unified multi-terrain policy...${NC}"
python -m duck_rl.train \
    --task walking \
    --model-dir ./models/stage4_multiterrain \
    --total-timesteps 10000000 \
    --learning-rate 1e-4 \
    --num-envs 32 \
    --seed 42 \
    --friction-range "(0.1, 1.3)" \
    --terrain-roughness "random(0.0, 0.08)" \
    --terrain-type "random" \
    --use-curriculum True

cp models/stage4_multiterrain/best_model.zip models/stage4_multiterrain_final.zip

# Phase 5: Recovery
echo -e "${GREEN}[PHASE 5] Training recovery (getup) policy...${NC}"
python -m duck_rl.train \
    --task getup \
    --model-dir ./models/stage5_getup \
    --total-timesteps 2000000 \
    --learning-rate 2e-4 \
    --num-envs 8 \
    --seed 50

echo -e "${GREEN}✓ All training phases completed!${NC}"
echo -e "${BLUE}Next: Export policies and test in simulator${NC}"
echo -e "  python -m duck_rl.export --model-path models/stage4_multiterrain_final.zip"
echo -e "  cd ../microduck && scripts/duck-sim up"
EOF

chmod +x train_multiterrain.sh
```

### Bước 3: Chạy Huấn Luyện

```bash
# Nếu có GPU (nhanh hơn)
export CUDA_VISIBLE_DEVICES=0
./train_multiterrain.sh

# Hoặc chỉ CPU (chậm hơn, ~3-5 ngày)
./train_multiterrain.sh
```

**Theo dõi tiến độ:**
```bash
# Terminal khác - xem training curves
tensorboard --logdir=./models

# Hoặc tail logs
tail -f models/stage4_multiterrain/logs/training.log
```

---

## 📊 Evaluation & Testing

### 1. Simulator Testing

```bash
# Export policy
python -m duck_rl.export \
    --model-path models/stage4_multiterrain_final.zip \
    --output ../microduck/policies/multiterrain_walking.onnx

# Test in simulator
cd ../microduck
export DUCK_POLICIES_DIR=../microduck_rl/models

scripts/duck-sim up

# Test commands (mỗi cái 30 giây)
scripts/duck-sim drive 0.15 0      # Forward on default
scripts/duck-sim drive -0.15 0     # Backward

# Force terrain switch (nếu supported)
scripts/duck-sim ctl setTerrain sand
scripts/duck-sim drive 0.15 0
scripts/duck-sim ctl setTerrain gravel
scripts/duck-sim drive 0.15 0
scripts/duck-sim ctl setTerrain snow
scripts/duck-sim drive 0.15 0
```

### 2. Quantitative Metrics

```python
# evaluate.py
import numpy as np
from duck_rl.env import make_env
from duck_rl.policy import load_policy

policy = load_policy('models/stage4_multiterrain_final.zip')
env = make_env(terrain='random', num_envs=10)

metrics = {
    'sand': {'return': [], 'fall_rate': [], 'ep_len': []},
    'gravel': {'return': [], 'fall_rate': [], 'ep_len': []},
    'snow': {'return': [], 'fall_rate': [], 'ep_len': []},
}

for terrain in ['sand', 'gravel', 'snow']:
    env.set_terrain(terrain)
    
    for episode in range(10):  # 10 episodes per terrain
        obs = env.reset()
        done = False
        episode_reward = 0
        step_count = 0
        fell = False
        
        while not done:
            action = policy.predict(obs)
            obs, reward, done, info = env.step(action)
            episode_reward += reward
            step_count += 1
            
            if info.get('fell'):
                fell = True
        
        metrics[terrain]['return'].append(episode_reward)
        metrics[terrain]['fall_rate'].append(1.0 if fell else 0.0)
        metrics[terrain]['ep_len'].append(step_count)

# Print results
for terrain, data in metrics.items():
    print(f"\n{terrain.upper()}:")
    print(f"  Avg Return: {np.mean(data['return']):.1f}")
    print(f"  Fall Rate: {np.mean(data['fall_rate'])*100:.1f}%")
    print(f"  Avg Episode Length: {np.mean(data['ep_len']):.0f}")

# Success criteria
success = all(
    np.mean(metrics[t]['fall_rate']) < 0.05  # < 5% fall rate
    for t in ['sand', 'gravel', 'snow']
)
print(f"\n✓ Multi-terrain policy successful: {success}")
```

### 3. Real Robot Testing

```bash
# Deploy to robot
scripts/dev-push.sh robot@192.168.1.100

# Enable policy
duckctl --robot duck.local setSkill multiterrain_walking

# Test on different surfaces
# Test 1: Indoor floor (like training default)
duckctl --robot duck.local drive 0.15 0 --duration 30

# Test 2: Outdoor carpet (rough)
duckctl --robot duck.local drive 0.15 0 --duration 30

# Test 3: Dirt/sand (if available)
duckctl --robot duck.local drive 0.10 0 --duration 30  # Slower, more cautious

# Monitor performance
duckctl --robot duck.local monitor
```

---

## 📈 Expected Results

### Success Criteria

| Metric | Target | Acceptable |
|---|---|---|
| **Fall Rate (Sand)** | < 2% | < 5% |
| **Fall Rate (Gravel)** | < 3% | < 7% |
| **Fall Rate (Snow)** | < 5% | < 10% |
| **Forward Speed** | 0.15 m/s | 0.10 m/s |
| **Episode Length** | 60+ seconds | 40+ seconds |
| **Recovery Rate** | 80% (getup) | 60% |

### Performance Curves Over Time

```
Phase 1 (Baseline):
Epoch   Return    Fall%   Ep_Len
100     50        15%     10s
500     150       8%      25s
1000    280       3%      50s

Phase 2 (Randomized):
1500    200       8%      40s      (drop due to randomization)
2000    240       6%      45s
2500    260       4%      50s

Phase 3 (Terrain-Specific):
Sand:   220       4%      50s
Gravel: 200       6%      45s
Snow:   180       7%      42s

Phase 4 (Multi-Terrain):
2000    180       8%      40s      (handling all terrains)
4000    200       6%      45s
6000    220       4%      50s
Final:  240       3%      55s      (converged!)
```

---

## 🔧 Configuration Template

**File: `config/multiterrain.yaml`**

```yaml
training:
  total_timesteps: 10000000
  learning_rate: 1.0e-4
  num_envs: 32
  batch_size: 256
  n_epochs: 20
  clip_ratio: 0.2
  entropy_coeff: 0.01

randomization:
  friction:
    enabled: true
    range: [0.1, 1.3]
    schedule: curriculum
  
  terrain:
    enabled: true
    roughness_range: [0.0, 0.08]
    type: random  # sand, gravel, snow, random
  
  mass:
    enabled: true
    range: [0.5, 2.0]
  
  servo:
    enabled: true
    response_delay_range: [0.0, 0.01]
    max_torque_range: [0.9, 1.1]

curriculum:
  enabled: true
  stages:
    - name: easy
      steps: 2000000
      friction_range: [0.8, 1.0]
      terrain_roughness: 0.0
    
    - name: medium
      steps: 3000000
      friction_range: [0.5, 1.0]
      terrain_roughness: 0.02
    
    - name: hard
      steps: 5000000
      friction_range: [0.1, 1.3]
      terrain_roughness: 0.08

reward:
  velocity_weight: 1.0
  stability_weight: 0.5
  energy_weight: 0.1
  terrain_bonus: 0.2  # Adaptive based on terrain

evaluation:
  episodes_per_terrain: 10
  terrains: [sand, gravel, snow, default]
  target_fall_rate: 0.05
  target_avg_return: 200
```

---

## ⚠️ Troubleshooting

### Training Diverges

```bash
# Giảm learning rate
--learning-rate 5e-5

# Tăng clip ratio (conservative updates)
--clip-ratio 0.15

# Giảm entropy (less exploration)
--entropy-coeff 0.001
```

### Falls Ngay Khi Add Randomization

```python
# Sử dụng curriculum learning - tăng dần độ khó
CURRICULUM = {
    'friction_schedule': [
        (0, 1e6, (0.8, 1.0)),      # Start easy
        (1e6, 3e6, (0.5, 1.0)),
        (3e6, 10e6, (0.1, 1.3)),   # End hard
    ]
}
```

### Terrain-Specific Policy Không Improve

```bash
# Tăng training time cho terrain đó
--total-timesteps 5000000  # Instead of 3000000

# Hoặc sử dụng different learning rate
--learning-rate 2e-4  # Slower learning
```

---

## 📋 Checklist Trước Khi Deploy

- [ ] Phase 1 baseline converges (return > 280)
- [ ] Phase 2 randomized works on all surfaces
- [ ] Phase 3 terrain-specific policies xử lý được riêng
- [ ] Phase 4 multi-terrain policy hoạt động trên tất cả
- [ ] Phase 5 recovery policy có > 60% success rate
- [ ] Evaluation metrics pass on all terrains
- [ ] Real robot testing không bị ngã
- [ ] Policy được export thành ONNX
- [ ] Hoạt động trên robot chẳng khác gì simulator

---

## 🎓 Tài Liệu Tham Khảo

1. **PPO Algorithm:** https://arxiv.org/abs/1707.06347
2. **Domain Randomization:** https://arxiv.org/abs/1703.06907
3. **Curriculum Learning:** https://arxiv.org/abs/1505.00686
4. **Locomotion Control:** https://arxiv.org/abs/1809.02627
5. **Quadruped Locomotion:** https://arxiv.org/abs/1804.00325 (Biped similar)

---

## ✅ Kết Luận

Chiến lược này sử dụng:
- **5 giai đoạn** huấn luyện từ đơn giản → phức tạp
- **Domain randomization** để generalize
- **Curriculum learning** để ổn định
- **Terrain-specific rewards** để tối ưu
- **Recovery policies** để cope với falls

**Kết quả:** Một policy có thể đi trên cát, sỏi, tuyết mà không bị ngã!

---

**Thời gian:** 14-18 ngày training (CPU), 7-9 ngày (GPU)  
**Yêu cầu:** 32GB RAM, GPU tối ưu (RTX3090 hoặc tương đương)  
**Kết quả:** Multi-terrain walking policy ready for robot!
