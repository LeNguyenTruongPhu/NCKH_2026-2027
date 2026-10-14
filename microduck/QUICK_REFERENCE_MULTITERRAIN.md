# 🦆 Quick Reference Card - Multi-Terrain Training

**Print this page or keep in browser for quick lookup!**

---

## ⚡ One-Liner Start

```bash
cd ~/Pollen/microduck_rl && source venv/bin/activate && \
../microduck/scripts/train_multiterrain_automated.sh --gpu
```

---

## 📊 Training Metrics at a Glance

```
Phase | Expected Return | Fall % | Ep Len | Days(GPU/CPU)
------|-----------------|--------|--------|---------------
  1   |      280+       |   <3   | 50s+   | 1-2 / 3-4
  2   |      250+       |   <5   | 48s+   | 1 / 2-3
  3   |  180-220/ea     |  <5-8  | 40-50s | 1.5 / 3-4
  4   |      200+       |   <4   | 50s+   | 2-3 / 5-8
  5   |   60% recovery  |   --   |  --    | 0.5 / 1-2
------|-----------------|--------|--------|---------------
Total |    Multi-terrain|  <5%   | 50s+   | 7-10 / 14-21
```

---

## 📂 Key Files Location

```
~/Pollen/microduck_rl/
  models/
    stage1_baseline_final.zip       ← After Phase 1
    stage2_randomized_final.zip     ← After Phase 2
    stage3_{sand,gravel,snow}/      ← After Phase 3
    stage4_multiterrain_final.zip   ← After Phase 4
    stage5_getup_final.zip          ← After Phase 5
    multiterrain_walking.onnx       ← Exported policy
    multiterrain_getup.onnx         ← Recovery policy
  logs/
    training.log                    ← Main log file
    phase{1-5}.log                  ← Per-phase logs

~/Pollen/microduck/
  scripts/
    train_multiterrain_automated.sh ← Main training script
    evaluate_multiterrain.py        ← Evaluation script
  configs/
    multiterrain_training.yaml      ← All parameters
  policies/                          ← Copy ONNX here for robot
```

---

## 🔍 Monitoring Commands

```bash
# Terminal 1: Run training
./train_multiterrain_automated.sh --gpu

# Terminal 2: Watch logs (live)
tail -f logs/training.log

# Terminal 3: TensorBoard
tensorboard --logdir=./models --port=6006
# → http://localhost:6006

# Terminal 4: System monitor
watch nvidia-smi              # GPU stats
# or
top                           # CPU stats
```

---

## ⚠️ Red Flags & Quick Fixes

| Problem | Symptom | Fix |
|---------|---------|-----|
| Divergence | Loss → -1000 | Reduce LR: `--learning-rate 5e-5` |
| Stuck | Loss flat for hours | Increase num_envs: `--num-envs 16` |
| Memory Error | Out of memory | Reduce batch: `--batch-size 128` |
| NaN Loss | Loss = NaN | Restart + reduce LR 10x |
| Falls on one terrain | High fall% on sand/gravel/snow | Train longer: `+2M steps` |
| Slow progress | Return stuck at 150 | Resume from phase 1: `--resume-from stage1_final.zip` |

---

## ✅ Success Checklist

Phase 1 Done?
- [ ] Return > 280
- [ ] Fall% < 3%
- [ ] Episode > 45s
- [ ] Save `stage1_baseline_final.zip`

Phase 2 Done?
- [ ] Return > 250
- [ ] Fall% < 5%
- [ ] Episode > 40s
- [ ] Save `stage2_randomized_final.zip`

Phase 3 Done?
- [ ] Sand: Return > 200
- [ ] Gravel: Return > 180
- [ ] Snow: Return > 160
- [ ] All saved

Phase 4 Done?
- [ ] Return > 200
- [ ] Fall% < 5% ALL terrains
- [ ] Episode > 50s
- [ ] Save `stage4_multiterrain_final.zip`

Phase 5 Done?
- [ ] Recovery rate > 60%
- [ ] Save `stage5_getup_final.zip`

Export Done?
- [ ] `multiterrain_walking.onnx` exists (500KB)
- [ ] `multiterrain_getup.onnx` exists (500KB)

Evaluation Done?
- [ ] Run evaluate_multiterrain.py
- [ ] All terrains: fall% < 5%
- [ ] All terrains: return > 180

Testing Done?
- [ ] Simulator works: `scripts/duck-sim drive 0.15 0`
- [ ] Robot walks on real surfaces
- [ ] Recovery works if pushed

---

## 🧪 Testing Commands

```bash
# Evaluate policy
python evaluate_multiterrain.py \
    --model-path models/stage4_multiterrain_final.zip \
    --episodes 20

# Test in simulator
cd ../microduck
export DUCK_POLICIES_DIR=../microduck_rl/models
scripts/duck-sim up
scripts/duck-sim drive 0.15 0       # Forward
scripts/duck-sim drive -0.15 0      # Backward
scripts/duck-sim drive 0 0.5        # Spin
scripts/duck-sim ctl health         # Check status
scripts/duck-sim monitor            # Watch sensors
scripts/duck-sim down               # Stop

# Deploy to robot
scripts/dev-push.sh robot@192.168.1.100
duckctl --robot duck.local drive 0.15 0
duckctl --robot duck.local monitor
```

---

## 🔧 Key Parameters to Adjust

If **too many falls:**
```bash
# Option 1: Longer training
--total-timesteps 15000000  # More iterations

# Option 2: Conservative updates
--clip-ratio 0.15           # Smaller policy changes
--learning-rate 5e-5        # Slower learning

# Option 3: Curriculum learning
--use-curriculum            # Progressively harder
```

If **slow progress:**
```bash
# Option 1: Faster learning
--learning-rate 3e-4        # Faster convergence

# Option 2: More parallel envs
--num-envs 32               # More data/step (if GPU)

# Option 3: Larger batch
--batch-size 512            # More stable updates
```

If **one terrain fails:**
```bash
# Fine-tune that terrain
python -m duck_rl.train \
    --task walking \
    --model-dir ./models/finetune_sand \
    --total-timesteps 3000000 \
    --friction-range "(0.9, 1.3)" \
    --resume-from stage4_multiterrain_final.zip
```

---

## 💾 Backup Important Files

After each phase:
```bash
# Backup best models
cp models/stageN_X/best_model.zip models/stageN_X_backup.zip

# Backup logs
cp logs/phaseN.log logs/phaseN_backup.log

# Track results
echo "Phase N: Return=$(grep 'Return' logs/phaseN.log | tail -1)" >> results.txt
```

---

## 🚀 GPU vs CPU Timeline

### GPU (NVIDIA RTX 3090)
- Phase 1: 1-2 days ▓▓░░░░░░░░
- Phase 2: 1 day   ▓░░░░░░░░░
- Phase 3: 1.5 day ▓▓░░░░░░░░
- Phase 4: 2-3 day ▓▓▓░░░░░░░
- Phase 5: 0.5 day ▓░░░░░░░░░
- **Total: 7-10 days**

### CPU (8-core)
- Phase 1: 3-4 days ▓▓▓▓░░░░░░
- Phase 2: 2-3 day ▓▓▓░░░░░░░
- Phase 3: 3-4 day ▓▓▓▓░░░░░░
- Phase 4: 5-8 day ▓▓▓▓▓▓▓░░░
- Phase 5: 1-2 day ▓░░░░░░░░░
- **Total: 14-21 days**

---

## 📧 Log What You See

**After each phase, note:**
```
Phase X Complete:
  Date: [DATE]
  GPU/CPU: [GPU/CPU]
  Final Return: [VALUE]
  Fall Rate: [PERCENT]
  Episode Length: [SECONDS]
  Issues: [IF ANY]
  
Training Curves Look Good? [YES/NO]
```

---

## 🎯 Training Day Example

```
8:00 AM   - Start training: ./train_multiterrain_automated.sh --gpu
8:05 AM   - Open TensorBoard: tensorboard --logdir ./models
8:10 AM   - Start monitoring: tail -f logs/training.log
          
12:00 PM  - Check progress: look at TensorBoard curves
           - If good: continue
           - If bad: note issues, may need adjustment

6:00 PM   - Daily update: echo "Day 1 done, Return=$(tail logs/training.log)" >> daily.log
           
9:00 AM Next Day - Check overnight progress
                 - If Phase complete: save + move to next
                 - If still training: continue monitoring
```

---

## 🆘 Emergency Restart

If training crashes:

```bash
# Check last checkpoint
ls -lt models/stage4_multiterrain/checkpoint_*.zip | head -1

# Resume from checkpoint
cd ~/Pollen/microduck_rl
source venv/bin/activate
python -m duck_rl.train \
    --task walking \
    --model-dir ./models/stage4_multiterrain \
    --total-timesteps 10000000 \
    --resume-from ./models/stage4_multiterrain/checkpoint_5000000.zip
```

---

## 📱 Status: Where You Are

```
STARTING:  ☐ Setup env ☐ Run training
TRAINING:  ☑ Phase N running...
           └─ Check: Return=200+, Fall%<5%, logs look good
DONE:      ☑ Phases 1-5 complete
           ├─ Export to ONNX ☐
           ├─ Evaluate ☐
           ├─ Test simulator ☐
           └─ Deploy to robot ☐
DEPLOYED:  ✓ Multi-terrain duck ready!
```

---

## 🔗 Quick Links

| Resource | Link |
|----------|------|
| Repo | https://github.com/pollen-robotics/microduck |
| Training Repo | https://github.com/pollen-robotics/microduck_rl |
| Strategy Doc | MULTI_TERRAIN_TRAINING_STRATEGY.md |
| Implementation | IMPLEMENT_MULTITERRAIN_PLAN.md |
| Config File | configs/multiterrain_training.yaml |
| This File | QUICK_REFERENCE_MULTITERRAIN.md |

---

## ✍️ Notes Space

```
Training Notes:
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

Observations:
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

Issues Encountered:
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
```

---

**Last Updated:** 2026-09-11  
**Status:** Ready to Train! 🚀  
**Good Luck!** 🦆
