# Troubleshooting Guide

## 🚀 Getting Started

### Simulator Won't Start

**Error:** `scripts/duck-sim: command not found`

```bash
# Make script executable
chmod +x scripts/duck-sim

# Or run directly
python scripts/duck-sim
```

**Error:** `MuJoCo window doesn't open` or `duck-body not found`

```bash
# Check microduck_rl is installed
ls ~/Pollen/microduck_rl
# If not found, clone it:
cd ~/Pollen && git clone https://github.com/pollen-robotics/microduck_rl.git

# Verify duck-body exists
ls ~/Pollen/microduck_rl/target/debug/duck-body
# If not, build it:
cd ~/Pollen/microduck_rl
cargo build

# Point environment variable
export DUCK_SIM_RL=~/Pollen/microduck_rl
```

**Error:** `ONNX Runtime library not found`

```bash
# Check if libonnxruntime exists
find ~/Pollen/microduck_rl -name "libonnxruntime*"

# If not, install it
cd ~/Pollen/microduck_rl
pip install onnxruntime  # For CPU
# or
pip install onnxruntime-gpu  # For CUDA

# Set library path
export LD_LIBRARY_PATH=$HOME/.local/lib:$LD_LIBRARY_PATH
```

## 🦆 Simulator Issues

### Duck Doesn't Stand Up

**Symptoms:** Robot lies on side or flails randomly

```bash
# Check policy is loaded
scripts/duck-sim ctl health
# Look for "standing" policy loaded

# If not loaded, check policy file exists
ls policies/standing.onnx
# Copy from RL repo if missing
cp ~/Pollen/microduck_rl/models/standing.onnx policies/
```

**Solution:** 
- Make sure `DUCK_POLICIES_DIR` is set correctly
- Rebuild simulator: `scripts/duck-sim build`
- Check robotd logs: `scripts/duck-sim log`

### Duck Stands But Won't Walk

**Symptoms:** Duck is upright but doesn't move when given walk command

```bash
# Check if walk policy is loaded
scripts/duck-sim ctl health | grep walk

# Manually test policy
scripts/duck-sim drive 0.15 0

# Watch motor commands
scripts/duck-sim ctl monitor
# You should see joint angles changing
```

**Solutions:**
1. **Policy not exported correctly**
   ```bash
   # Re-export policy
   cd ~/Pollen/microduck_rl
   python -m duck_rl.export --model-path models/walking/best.zip --output models/walking.onnx
   ```

2. **Policy file corrupted**
   ```bash
   # Verify ONNX model
   python -c "import onnx; onnx.checker.check_model('policies/walking.onnx')"
   ```

3. **Joint limits issue**
   ```bash
   # Check servo limits in duck-control/src/model.rs
   cargo test -p duck-control  # All tests should pass
   ```

### Duck Falls Constantly

**Symptoms:** Even standing still causes falls

```bash
# Get detailed logs
scripts/duck-sim log | tail -100
# Look for "fall detected" messages

# Check IMU is working
scripts/duck-sim ctl monitor
# Verify gyro and accel readings change
```

**Possible causes:**

1. **Standing policy not trained enough**
   ```bash
   cd ~/Pollen/microduck_rl
   python -m duck_rl.train \
       --task standing \
       --total-timesteps 5000000 \
       --learning-rate 1e-4  # Slower = more stable
   ```

2. **Simulator physics not matching training**
   ```bash
   # Check if domain randomization is enabled
   grep -r "friction" ~/Pollen/microduck_rl/
   # Make sure wind/mass randomization is on
   ```

3. **Safety thresholds too aggressive**
   ```bash
   # Edit fall detection threshold
   # File: duck-control/src/safety.rs
   # Look for FALL_THRESHOLD_GYRO
   # Increase value to be less sensitive
   ```

### Simulator Running Slow

**Symptoms:** Simulation lags, response time > 1 sec

```bash
# Check framerate
scripts/duck-sim realtime
# Should show close to 1.0 (real-time)

# If < 0.5, system is overloaded
```

**Solutions:**

```bash
# Reduce MuJoCo physics quality
# Edit ~/.cache/duck-sim/scene.xml
# Change <timestep> from 0.002 to 0.004 (halves simulation cost)

# Disable graphics rendering
# Run headless mode
HEADLESS=1 scripts/duck-sim

# Close other applications
# Stop Chrome, VS Code, etc.
```

## 🧠 Training Issues

### Training Diverges (Reward Explodes/Crashes)

**Symptoms:** 
- Reward suddenly jumps to 1000 or -1000
- Training crashes with NaN values
- Policy becomes erratic in simulator

```bash
# Check logs
tail -20 ./models/walking/logs/training.log

# Likely causes:
# 1. Learning rate too high
# 2. Large batch size with small num_envs
# 3. Reward function mismatch between sim and eval
```

**Solutions:**

```bash
# Reduce learning rate
python -m duck_rl.train \
    --task walking \
    --learning-rate 1e-4  # Default is 3e-4

# Increase number of environments
python -m duck_rl.train \
    --task walking \
    --num-envs 16  # More stability

# Restart training from saved checkpoint
python -m duck_rl.train \
    --task walking \
    --resume-from ./models/walking/checkpoint_1000000.zip
```

### Training Takes Too Long

**Symptoms:** Standing takes 30+ minutes, walking takes > 2 hours

```bash
# Check if GPU is being used
python -c "import torch; print(torch.cuda.is_available())"  # Should be True
python -c "import torch; print(torch.cuda.get_device_name())"  # Should show GPU
```

**Solutions:**

1. **Use GPU if available**
   ```bash
   export CUDA_VISIBLE_DEVICES=0
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
   ```

2. **Increase parallel environments**
   ```bash
   python -m duck_rl.train \
       --task walking \
       --num-envs 32  # More parallel sim = faster data collection
   ```

3. **Use simpler network**
   ```bash
   python -m duck_rl.train \
       --task walking \
       --network-size 64 64  # Smaller = faster, but may learn slower
   ```

4. **Train for fewer steps** (not recommended)
   ```bash
   python -m duck_rl.train \
       --task walking \
       --total-timesteps 2000000  # Still enough for basic gait
   ```

### Policy Exports But Doesn't Work

**Symptoms:** 
- Export succeeds
- Simulator shows policy loaded
- But behavior is random or frozen

```bash
# Verify ONNX export
python -c "
import onnx
model = onnx.load('policies/walking.onnx')
print('Model valid:', onnx.checker.check_model(model))
print('Inputs:', [i.name for i in model.graph.input])
print('Outputs:', [o.name for o in model.graph.output])
"
```

**Common issues:**

1. **Wrong input shape**
   ```bash
   # Check observation size matches policy input
   grep "OBS_LEN" duck-control/src/obs.rs
   # Should match ONNX input dimensions (1, obs_len)
   ```

2. **Dtype mismatch**
   ```bash
   # Policy expects float32, not float64
   python -m duck_rl.export --dtype float32
   ```

3. **Output normalization**
   ```bash
   # Check if policy outputs normalized actions (-1 to 1)
   # or if servo commands need scaling
   # Look in duck-control/src/policy.rs
   ```

## 🤖 Robot Hardware Issues

### Robot Won't Boot After Update

**Symptoms:** Robot turns on but no LEDs, no response to commands

```bash
# SSH into robot if possible
ssh root@192.168.1.100

# Check journal
journalctl -n 100  # Last 100 lines
journalctl -u robotd -n 50  # robotd logs

# Check update status
systemctl status updater

# View update logs
journalctl -u updater -n 100
```

**Recovery:**
```bash
# Force rollback to previous version
systemctl stop updater
mount -o remount,rw /
# Edit /etc/robot-update/active to point to previous version
mount -o remount,ro /
systemctl reboot
```

### Servos Overheat

**Symptoms:** Servo doesn't respond, warns of high temperature

```bash
# Check servo temperature
scripts/duck-sim ctl health | grep temp
# or on robot
robotctl health | grep temp
```

**Prevention:**
- Never run > 30 min continuous
- 15 min activity, 5 min rest cycle
- Reduce walking speed if training (0.15 m/s instead of 0.25)

**Fix if overheated:**
```bash
# Stop immediately
scripts/duck-sim down

# Let cool for 10 minutes
sleep 600

# Restart with lower power
scripts/duck-sim up  # Reduced servo torque
```

### Can't SSH Into Robot

**Symptoms:** `ssh robot@192.168.1.100` times out

```bash
# Check if robot is on network
ping 192.168.1.100

# Try via Bluetooth instead
duckctl --robot duck.local shell
# or
robotctl --sock ~/.cache/duck-sim/duck.sock system info
```

**If still can't reach:**
```bash
# Connect via USB serial
sudo minicom -D /dev/ttyUSB0 -b 115200

# Or use recovery mode
# Hold reset button 10s during boot
```

## 🛠️ Build Issues

### Cargo Build Fails

**Error:** `cannot find -lonnxruntime`

```bash
# ONNX Runtime not installed
# Option 1: Use pre-compiled version
cargo build --release --features pre-built-onnx

# Option 2: Install from package manager
sudo apt-get install libonnxruntime-dev

# Option 3: Download prebuilt
mkdir -p vendor/onnxruntime/lib
cd vendor/onnxruntime/lib
wget https://github.com/microsoft/onnxruntime/releases/download/v1.28.0/...
```

**Error:** `linker 'cc' not found`

```bash
# Install C compiler
sudo apt-get install build-essential
# or on macOS
xcode-select --install
```

**Error:** `error[E0514]: type mismatch`

```bash
# Usually means you're mixing different Rust versions
rustup update
cargo clean
cargo build
```

### Tests Fail

**Error:** `thread panicked at 'called Option::unwrap()`

```bash
# Run test with backtrace
RUST_BACKTRACE=1 cargo test

# Run specific test
cargo test test_forward_kinematics -- --nocapture
```

**Flaky tests (fail randomly):**
```bash
# Run tests multiple times
for i in {1..10}; do cargo test || exit 1; done

# Check for race conditions
RUST_TEST_THREADS=1 cargo test  # Sequential
```

## 📞 Getting Help

### Check These First

1. **Error message online**
   ```bash
   google "error: no default members in workspace"
   ```

2. **Project issues**
   ```bash
   # Check GitHub issues
   https://github.com/pollen-robotics/microduck/issues
   https://github.com/pollen-robotics/microduck_rl/issues
   ```

3. **Documentation**
   - `docs/README.md` - all docs index
   - `docs/robot/cheatsheet.md` - commands reference
   - `CONTRIBUTING.md` - dev guidelines

### Collect Info for Support

When asking for help:

```bash
# System info
uname -a
rustc --version
cargo --version

# Build error
cargo build 2>&1 | head -50

# Runtime error
scripts/duck-sim log | tail -100

# Policy training issue
tail -100 models/walking/logs/training.log

# Verify everything is installed
which python python3 cargo rustc
ls ~/Pollen/microduck_rl
echo $DUCK_SIM_RL $DUCK_POLICIES_DIR
```

Then post to issues or ask Pollen team.

## 🔄 Reset Everything

**Nuclear option: start fresh**

```bash
# Stop all processes
scripts/duck-sim down 2>/dev/null || true
pkill -f robotd
pkill -f duck-body

# Clear cache
rm -rf ~/.cache/duck-sim
rm -rf target/

# Rebuild
cargo build --release

# Start fresh
scripts/duck-sim build
scripts/duck-sim up
```

---

**Still stuck?** 
- Email: hello@pollen-robotics.com
- GitHub: https://github.com/pollen-robotics/microduck/issues
- Documentation: https://pollen-robotics.com/docs/microduck/
