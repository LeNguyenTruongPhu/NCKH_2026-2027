# Quick Start: Train Your Duck to Walk Without Falling 🦆

**Goal:** Get a walking policy trained and running in 30 minutes (or use pre-trained policies)

## 🎯 Option 1: Use Pre-Trained Policies (5 min)

If you just want to test the simulator with existing policies:

```bash
# Clone the training repo (includes pre-trained policies)
cd ~/Pollen
git clone https://github.com/pollen-robotics/microduck_rl.git

# Setup Python environment
cd microduck_rl
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Go back to microduck
cd ../microduck

# Point to the pre-trained policies
export DUCK_POLICIES_DIR=~/Pollen/microduck_rl/models

# Run simulator
scripts/duck-sim up

# In another terminal, test walking
scripts/duck-sim drive 0.15 0  # Move forward
scripts/duck-sim drive 0 0     # Stop
scripts/duck-sim down          # Shutdown
```

**That's it!** The duck should walk forward in the simulator.

## 🧠 Option 2: Train Your Own Policy (20-30 min)

### Step 1: Setup Environment

```bash
cd ~/Pollen/microduck_rl
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Optional: Use GPU (much faster)
# pip install torch --index-url https://download.pytorch.org/whl/cu118
```

### Step 2: Train Standing Policy (5-10 min)

```bash
# Train model to stand still (harder than you think!)
python -m duck_rl.train \
    --task standing \
    --model-dir ./models/standing \
    --seed 42 \
    --total-timesteps 1000000

# This will:
# 1. Spawn MuJoCo simulator window
# 2. Show training progress
# 3. Save checkpoints every 50k steps
# 4. Achieve ~95% success rate standing
```

**What's happening:**
- Policy learns to balance via IMU feedback
- Reward: penalizes tipping over, rewards staying upright
- Domain randomization: random friction, mass, wind
- Takes ~1M steps (10-15 min on GPU, 20-30 min on CPU)

### Step 3: Train Walking Policy (20-30 min)

```bash
# Train walking (more complex task)
python -m duck_rl.train \
    --task walking \
    --model-dir ./models/walking \
    --seed 42 \
    --total-timesteps 5000000 \
    --num-envs 8  # Parallel environments for faster training

# This will:
# 1. Spawn 8 parallel MuJoCo environments
# 2. Show training curves (reward, episode length)
# 3. Learn forward motion and obstacle avoidance
# 4. Achieve smooth gait with ~90% stability
```

**Progress indicators:**
- Episode length: increases from 10s → 60s+ as it learns
- Reward: rises as policy learns better balance
- You'll see the duck in simulator walking forward, sometimes falling

### Step 4: (Optional) Train Recovery Policy

```bash
# Teach it to get up if it falls
python -m duck_rl.train \
    --task getup \
    --model-dir ./models/getup \
    --total-timesteps 2000000
```

### Step 5: Export to ONNX

```bash
# Convert PyTorch → ONNX format for robot
python -m duck_rl.export \
    --model-path ./models/walking/best_model.zip \
    --output ./models/walking.onnx \
    --policy-name walking

# Verify it exported
ls -lh models/walking.onnx  # Should be ~500 KB
```

### Step 6: Test in Simulator

```bash
# Back in microduck
cd ../microduck

# Tell simulator to use your new policies
export DUCK_POLICIES_DIR=~/Pollen/microduck_rl/models

# Start simulator
scripts/duck-sim up

# Test walking (in another terminal)
scripts/duck-sim drive 0.15 0    # Forward
scripts/duck-sim drive -0.15 0   # Backward
scripts/duck-sim drive 0 0.5     # Spin left
scripts/duck-sim drive 0.1 0.2   # Forward + turn

# Monitor performance
scripts/duck-sim monitor
scripts/duck-sim log

# Stop
scripts/duck-sim down
```

## 🔧 Debugging: "Duck Keeps Falling"

### 1. Check Policy Quality

```bash
# Replay trained policy in isolation
python -m duck_rl.evaluate \
    --model-path ./models/walking/best_model.zip \
    --episodes 10 \
    --render
```

If duck falls in eval, policy needs more training. **Solution:** Train longer.

### 2. Increase Training Time

```python
# Edit training config or use CLI:
python -m duck_rl.train \
    --task walking \
    --total-timesteps 10000000  # 2x longer
    --learning-rate 3e-4        # Slower learning = more stable
```

### 3. Increase Domain Randomization

```python
# In duck_rl/config.py, increase randomness:
# friction_range = (0.1, 2.0)  # wider range
# mass_range = (0.5, 2.0)
# wind_force = 2.0  # stronger wind
```

Higher randomization = more robust to real-world variations.

### 4. Reduce Policy Complexity

```python
# Use smaller network = simpler, more stable policy
python -m duck_rl.train \
    --network-size 64 64  # Default: 256 256
```

### 5. Different Algorithm

```python
# Try SAC (Soft Actor-Critic) instead of PPO
python -m duck_rl.train \
    --algorithm SAC \
    --task walking \
    --total-timesteps 5000000
```

## 📊 What to Monitor During Training

```
Iteration 1000 | Return: 42.3 | Ep Len: 15s | Fall Rate: 12% | Entropy: 0.8
Iteration 2000 | Return: 156.7 | Ep Len: 32s | Fall Rate: 5% | Entropy: 0.7
Iteration 5000 | Return: 287.4 | Ep Len: 58s | Fall Rate: 2% | Entropy: 0.6
```

**Good signs:**
- Return increasing over time
- Episode length going up (duck stays alive longer)
- Fall rate going down
- Entropy gradually decreasing (policy becoming more confident)

**Bad signs:**
- Return stuck or decreasing
- Episode length plateaus early (< 30s for walking)
- Fall rate high (> 10%)
- Training diverges (return suddenly jumps to -1000)

## 🚀 Deploy to Real Robot

Once you're happy with the policy:

```bash
# 1. Copy to microduck
cp ~/Pollen/microduck_rl/models/walking.onnx \
   ~/Pollen/microduck/policies/

# 2. Push to robot
scripts/dev-push.sh robot@192.168.1.100

# 3. Enable the policy
duckctl --robot duck.local setSkill walking

# 4. Test with gamepad or command
duckctl --robot duck.local drive 0.15 0
```

## 💡 Pro Tips

### Training Faster

```bash
# Use GPU if available
export CUDA_VISIBLE_DEVICES=0
python -m duck_rl.train --task walking --total-timesteps 5000000

# Use multiple parallel environments
python -m duck_rl.train --num-envs 16 --task walking

# Watch training in real-time
tensorboard --logdir=./models/walking/logs
```

### Better Gaits

Teach different skills:

```bash
# Standing still (100% uptime goal)
python -m duck_rl.train --task standing

# Walking forward (smooth gait)
python -m duck_rl.train --task walking

# Strafing (sideways movement)
python -m duck_rl.train --task strafe

# Turning (spinning in place)
python -m duck_rl.train --task spin

# Recovery (get up from falls)
python -m duck_rl.train --task getup
```

### Policy Composition

Combine policies:

```python
# In robotd config:
standing_policy = "models/standing.onnx"
walking_policy = "models/walking.onnx"
getup_policy = "models/getup.onnx"

# At runtime, switch based on state:
if is_fallen():
    load_policy(getup_policy)
elif has_walking_command():
    load_policy(walking_policy)
else:
    load_policy(standing_policy)
```

## ❌ Common Mistakes

| Mistake | Fix |
|---------|-----|
| Train with too few steps | Use at least 1M for standing, 5M for walking |
| No domain randomization | Enable randomization in config (friction, mass, wind) |
| Train only on flat ground | Randomize terrain height/roughness |
| Impatient evaluation | Run 10+ episodes before judging |
| Deploy without simulator test | Always test in `scripts/duck-sim` first |
| Use old ONNX runtime | Update with `scripts/setup-board.sh` |

## 📚 Hyperparameters Cheat Sheet

```python
# For a **stable** policy (safety first):
learning_rate = 2e-4          # Slow learning
entropy_coeff = 0.01          # Low entropy = confident
value_loss_coeff = 0.5        # Trust value function
clip_ratio = 0.2              # Conservative PPO

# For a **aggressive** policy (speed first):
learning_rate = 3e-4          # Faster learning
entropy_coeff = 0.1           # Explore more
value_loss_coeff = 0.1        # Trust policy over value
clip_ratio = 0.3              # Allow bigger updates
```

## ✅ Verification Checklist

Before deploying to the robot:

- [ ] Policy trains without diverging (loss doesn't explode)
- [ ] Duck stands for > 1 minute in eval (simulator)
- [ ] Duck walks smoothly for > 30 seconds
- [ ] Duck recovers from small pushes (10% of the time)
- [ ] Fall rate < 5% across 10 evaluation episodes
- [ ] ONNX export succeeds without warnings
- [ ] Simulator runs smoothly: `scripts/duck-sim drive 0.15 0`
- [ ] `robotctl health` shows policy loaded on robot
- [ ] Real duck walks without slipping

## 🎯 Success Criteria

| Milestone | Expected Time | How to Verify |
|-----------|---|---|
| Duck stands still | 5-10 min | `scripts/duck-sim drive 0 0` (30s+) |
| Duck walks forward | 20-30 min | `scripts/duck-sim drive 0.15 0` (smooth) |
| Duck doesn't fall | 30+ min | 10 episodes, fall rate < 5% |
| Deploys to robot | 40+ min | `duckctl drive 0.15 0` on real hardware |

---

**Next Step:** Pick Option 1 or 2 above and get started! 

Questions? Check `microduck_rl` README or reach out to the Pollen team.
