# 🎮 Hướng Dẫn Visual: Chạy Mô Phỏng Vịt

**In page này ra hoặc mở trong browser để tham khảo nhanh!**

---

## 📍 Vị Trí & Chuẩn Bị

```
YOUR COMPUTER
│
├─ ~/Pollen/
│  ├─ microduck/              ← FIRMWARE & SIMULATOR
│  │  ├─ scripts/
│  │  │  ├─ duck-sim          ← CHẠY SIMULATOR
│  │  │  └─ evaluate_multiterrain.py
│  │  ├─ SIMULATOR_COMMANDS_GUIDE.md
│  │  └─ configs/
│  │
│  └─ microduck_rl/           ← TRAINING & POLICIES
│     ├─ models/
│     │  ├─ walking.onnx      ← Policy file
│     │  ├─ standing.onnx
│     │  └─ ...
│     └─ venv/                ← Python environment
│
└─ [Make sure both folders exist!]
```

---

## 🚀 QUICK START (3 Bước)

### BƯỚC 1: Mở Terminal & Vào Thư Mục

```
┌─────────────────────────────────────┐
│ $ cd ~/Pollen/microduck             │
│ $ pwd                               │
│ /home/user/Pollen/microduck         │
│ $                                   │
└─────────────────────────────────────┘
```

### BƯỚC 2: Chạy Simulator

```
┌─────────────────────────────────────┐
│ $ scripts/duck-sim up               │
│                                     │
│ [Loading MuJoCo...]                 │
│ [Starting robotd...]                │
│ [Loading policy...]                 │
│ ✓ Duck simulator ready!             │
│                                     │
│ [MuJoCo Window Opens] ← WATCH HERE  │
│  ┌──────────────────┐               │
│  │  🦆   (standing) │               │
│  │                  │               │
│  │ MuJoCo Simulator │               │
│  └──────────────────┘               │
│ $                                   │
└─────────────────────────────────────┘
```

### BƯỚC 3: Điều Khiển (Terminal Khác)

```
┌─────────────────────────────────────┐
│ $ cd ~/Pollen/microduck             │
│ $ scripts/duck-sim drive 0.15 0     │
│                                     │
│ [Duck starts walking forward]        │
│  ┌──────────────────┐               │
│  │  🦆➡️  (walking)  │               │
│  │ →→→→→→→→→→→     │  Moving!      │
│  └──────────────────┘               │
│                                     │
│ $ scripts/duck-sim drive 0 0        │
│ [Duck stops]                        │
│ $                                   │
└─────────────────────────────────────┘
```

---

## 🎮 LỆNH ĐIỀU KHIỂN CHÍNH

```
┌──────────────────────────────────────────────────────────┐
│                   ĐIỀU KHIỂN CHUYỂN ĐỘNG                 │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Forward:                                               │
│  $ scripts/duck-sim drive 0.15 0                        │
│    🦆                    →→→→→→→→→→                      │
│                                                          │
│  Backward:                                              │
│  $ scripts/duck-sim drive -0.15 0                       │
│    🦆                    ←←←←←←←←←←                      │
│                                                          │
│  Turn Left:                                             │
│  $ scripts/duck-sim drive 0 0.5                         │
│    🦆  ↻ ↻ ↻                                            │
│                                                          │
│  Turn Right:                                            │
│  $ scripts/duck-sim drive 0 -0.5                        │
│    🦆  ↼ ↼ ↼                                            │
│                                                          │
│  Diagonal (Forward-Right):                              │
│  $ scripts/duck-sim drive 0.1 -0.3                      │
│    🦆  ↘ ↘ ↘                                            │
│                                                          │
│  STOP:                                                  │
│  $ scripts/duck-sim drive 0 0                           │
│    🦆  (standing still)                                 │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## 📋 LỆNH QUẢN LÝ

```
┌──────────────────────────────────────────────────────────┐
│              QUẢN LÝ SIMULATOR                           │
├──────────────────────────────────────────────────────────┤
│                                                          │
│ BẬT:                                                    │
│ $ scripts/duck-sim up                                   │
│   → MuJoCo window opens                                 │
│   → Duck is ready to control                            │
│                                                          │
│ TẮT:                                                    │
│ $ scripts/duck-sim down                                 │
│   → Simulator stops                                     │
│   → MuJoCo window closes                                │
│                                                          │
│ TRẠNG THÁI:                                             │
│ $ scripts/duck-sim status                               │
│   → health: OK                                          │
│   → position: standing                                  │
│   → policy: walking.onnx                                │
│                                                          │
│ XEM LOGS (Live):                                        │
│ $ scripts/duck-sim log -f                               │
│   → [timestamp] message                                 │
│   → [timestamp] message                                 │
│   → Ctrl+C to stop                                      │
│                                                          │
│ XEM LOGS (Một lần):                                     │
│ $ scripts/duck-sim log                                  │
│   → Show last 50 lines                                  │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## 🔍 GIÁM SÁT & DEBUG

```
┌──────────────────────────────────────────────────────────┐
│         XEMÔNG HIỂU TÌNH TRẠNG VỊT                       │
├──────────────────────────────────────────────────────────┤
│                                                          │
│ HEALTH CHECK:                                           │
│ $ scripts/duck-sim ctl health                           │
│   Status:        healthy ✓                              │
│   Policy:        walking.onnx loaded                    │
│   Battery:       100%                                   │
│   Temperature:   35°C (normal)                          │
│   Falls:         0                                      │
│                                                          │
│ MONITOR (Real-time):                                    │
│ $ scripts/duck-sim monitor                              │
│   Joint positions:      [0.1, -0.5, 0.2, ...]          │
│   IMU Gyro:             [0.01, 0.02, 0.00]             │
│   IMU Accel:            [0.0, 0.0, -9.8]               │
│   Foot contacts:        [L:yes, R:no]                   │
│   (Updates every 50ms)                                  │
│                                                          │
│ SIMULATION SPEED:                                       │
│ $ scripts/duck-sim realtime                             │
│   0.97 → 97% of real-time (excellent)                   │
│   0.50 → 50% of real-time (slow)                        │
│   1.05 → 105% of real-time (fast)                       │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## ⚙️ CẤU HÌNH & TÙYẾN

```
┌──────────────────────────────────────────────────────────┐
│         THAY ĐỔI POLICY/TERRAIN                         │
├──────────────────────────────────────────────────────────┤
│                                                          │
│ THAY POLICY:                                            │
│ $ export DUCK_POLICY=models/custom_walking.onnx         │
│ $ scripts/duck-sim up                                   │
│                                                          │
│ THAY THƯ MỤC POLICY:                                    │
│ $ export DUCK_POLICIES_DIR=~/custom_policies            │
│ $ scripts/duck-sim up                                   │
│                                                          │
│ THAY ĐỘ NHẸ NHÀN VỊT:                                   │
│ $ scripts/duck-sim ctl setMass 1.5    # Heavy (1.5x)    │
│ $ scripts/duck-sim ctl setMass 0.8    # Light (0.8x)    │
│                                                          │
│ THAY TỐC ĐỘ MÔ PHỎNG:                                  │
│ $ scripts/duck-sim ctl setTimescale 2.0   # 2x faster   │
│ $ scripts/duck-sim ctl setTimescale 0.5   # 0.5x slower │
│ $ scripts/duck-sim ctl setTimescale 1.0   # Normal      │
│                                                          │
│ THAY TỶ LỆ FRICTION:                                    │
│ $ scripts/duck-sim ctl setFriction 1.5    # More grip   │
│ $ scripts/duck-sim ctl setFriction 0.3    # Slippery    │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## 🎯 FLOW ĐIỂN HÌNH (Day-to-Day)

```
MORNING: SET UP
─────────────────────────────────────────────────
$ cd ~/Pollen/microduck
$ scripts/duck-sim up
  [MuJoCo window opens]
  [Duck is ready]


DAYTIME: TESTING & TWEAKING
─────────────────────────────────────────────────
Terminal 1:  [scripts/duck-sim up]  (running)
Terminal 2:  $ scripts/duck-sim monitor
             (watching metrics)
Terminal 3:  $ scripts/duck-sim drive 0.15 0
             $ # wait 5 seconds
             $ scripts/duck-sim drive 0 0
             $ scripts/duck-sim ctl health


AFTERNOON: EVALUATION
─────────────────────────────────────────────────
$ scripts/duck-sim drive 0.15 0   # Test 1: Forward
$ sleep 10
$ scripts/duck-sim drive 0 0

$ scripts/duck-sim drive 0 0.5    # Test 2: Turn
$ sleep 4
$ scripts/duck-sim drive 0 0

$ scripts/duck-sim ctl health     # Final check
  ✓ All metrics good?


EVENING: CLEANUP
─────────────────────────────────────────────────
$ scripts/duck-sim down
$ # Save logs
$ scripts/duck-sim log > run_$(date +%Y%m%d).log
```

---

## 📊 DASHBOARD VIEW (Tưởng Tượng)

```
┌─────────────────────────────────────────────────────────────┐
│                   SIMULATION DASHBOARD                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  MuJoCo Window:              Terminal Logs:                 │
│  ┌─────────────────┐        ┌──────────────────────────┐   │
│  │                 │        │ [14:30:15] duck started  │   │
│  │      🦆          │        │ [14:30:16] policy loaded │   │
│  │   ➡️ ➡️ ➡️      │        │ [14:30:20] drive: 0.15 0 │   │
│  │                 │        │ [14:30:25] speed: 0.14   │   │
│  │ [Walking]       │        │ [14:30:30] stop cmd      │   │
│  └─────────────────┘        └──────────────────────────┘   │
│                                                             │
│  Monitor Panel:              Health Status:                │
│  ┌─────────────────┐        ┌──────────────────────────┐   │
│  │ Joint[0]: 0.15  │        │ Status:      Healthy ✓  │   │
│  │ Joint[1]: -0.45 │        │ Falls:       0          │   │
│  │ Gyro[X]: 0.02   │        │ Battery:     100%       │   │
│  │ Gyro[Y]: 0.01   │        │ Temp:        35°C       │   │
│  │ Foot_L: Yes     │        │ FPS:         50         │   │
│  │ Foot_R: No      │        │ Speed:       0.97x      │   │
│  └─────────────────┘        └──────────────────────────┘   │
│                                                             │
│ Commands Ready:  $ scripts/duck-sim [drive|ctl|log|...]   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔗 COMMAND FLOW DIAGRAM

```
START
  │
  ├─→ scripts/duck-sim up
  │   │
  │   ├─ Load firmware (robotd)
  │   ├─ Load MuJoCo (duck-body)
  │   ├─ Load policy (walking.onnx)
  │   └─→ READY STATE
  │
  └─→ (In another terminal)
      │
      ├─→ scripts/duck-sim drive 0.15 0
      │   └─ Duck walks forward →→→
      │
      ├─→ scripts/duck-sim drive 0 0
      │   └─ Duck stops
      │
      ├─→ scripts/duck-sim monitor
      │   └─ Show sensors & joints
      │
      ├─→ scripts/duck-sim ctl health
      │   └─ Show health status
      │
      └─→ scripts/duck-sim log
          └─ Show recent logs

STOP
  │
  └─→ scripts/duck-sim down
      │
      ├─ Stop policy (robotd)
      ├─ Stop simulator (duck-body)
      └─→ SHUTDOWN
```

---

## 💻 TERMINAL SETUP (Recommended)

```
┌─────────────────────────────────────────────┐
│        YOUR DESKTOP/TERMINAL SETUP           │
├─────────────────────────────────────────────┤
│                                             │
│ [Terminal 1]      [Terminal 2]   [Terminal3]
│ ─────────────────────────────────────────
│ duck-sim          Logs            Commands
│ (simulator)       (monitoring)    (control)
│                                             │
│ $ scripts/        $ tail -f        $ drive │
│   duck-sim up       logs/...         0.15 0│
│                                             │
│ [MuJoCo]          [Auto-updating]  [Ready] │
│ [Window]          Log output       to send │
│                                             │
│ Running...        Running...       Waiting  │
│                   Watching         command  │
│                                             │
│ Ctrl+C to stop    Ctrl+C to stop   (type & │
│                                    enter) │
│                                             │
└─────────────────────────────────────────────┘
```

---

## ⚡ KEYBOARD SHORTCUTS (MuJoCo)

```
┌────────────────────────────────────────────┐
│      IN MUJOCO WINDOW (If Allowed)         │
├────────────────────────────────────────────┤
│                                            │
│ Spacebar    →  Pause/Resume simulation    │
│ R           →  Reset to initial state     │
│ C           →  Center camera on robot     │
│ Mouse Drag  →  Rotate camera              │
│ Scroll      →  Zoom camera                │
│ V           →  Toggle velocity display    │
│ D           →  Toggle joint display       │
│ S           →  Toggle sensor display      │
│ Esc         →  Close window                │
│                                            │
│ (May depend on configuration)              │
│                                            │
└────────────────────────────────────────────┘
```

---

## 🚨 TROUBLESHOOTING QUICK REFERENCE

```
PROBLEM 1: Window doesn't open
───────────────────────────────
$ export DISPLAY=:0
$ scripts/duck-sim up

PROBLEM 2: "Command not found"
────────────────────────────────
$ cd ~/Pollen/microduck
$ ls scripts/duck-sim
$ chmod +x scripts/duck-sim
$ ./scripts/duck-sim up

PROBLEM 3: "Port already in use"
─────────────────────────────────
$ pkill -f duck-sim
$ sleep 2
$ scripts/duck-sim up

PROBLEM 4: Policy not loading
──────────────────────────────
$ export DUCK_POLICIES_DIR=~/Pollen/microduck_rl/models
$ scripts/duck-sim up
$ scripts/duck-sim ctl health  # Should show policy loaded

PROBLEM 5: Simulation very slow
────────────────────────────────
$ scripts/duck-sim realtime  # Check if < 0.5
$ pkill -f duck-sim
$ scripts/duck-sim up        # Try again
```

---

## 📍 EXPECTED OUTPUT

```bash
$ scripts/duck-sim up

[00:00:00] Initializing simulator...
[00:00:01] Loading robot model...
[00:00:02] Starting daemons...
  ├─ robotd: OK
  ├─ duck-control: OK
  ├─ policy system: OK
[00:00:03] Loading MuJoCo...
[00:00:04] Loading policy: walking.onnx
[00:00:05] Simulator ready!

[MuJoCo Window Opens with Duck Standing]
✓ Ready for commands

$ scripts/duck-sim drive 0.15 0
[Duck starts walking in MuJoCo]
✓ Command sent

$ scripts/duck-sim monitor
Joint positions:  [0.12, -0.34, 0.18, ...]
IMU Gyro:         [0.01, 0.02, 0.00]
IMU Accel:        [0.0, 0.0, -9.8]
Foot contacts:    [Left: YES, Right: NO]
(Updates continuously...)

$ scripts/duck-sim ctl health
Status:           HEALTHY ✓
Policy loaded:    walking.onnx
Battery:          100%
Temperature:      35°C
Falls:            0
✓ All systems nominal
```

---

## 📌 BOOKMARK THIS!

Print this page or bookmark it for quick reference while simulating!

**Key Commands to Remember:**

```bash
# Start
scripts/duck-sim up

# Drive forward
scripts/duck-sim drive 0.15 0

# Stop
scripts/duck-sim drive 0 0

# Check health
scripts/duck-sim ctl health

# Watch logs
scripts/duck-sim log -f

# Stop simulator
scripts/duck-sim down
```

---

**Ready to Simulate!** 🚀 🦆

Let's go!
