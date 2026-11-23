"""CPU MuJoCo (BAM, delay, stale vel): walking policy over scene_ramp.xml (box ramp 6.7 %, up 8 cm, down)."""
import importlib.util, math, sys
from pathlib import Path
import mujoco, numpy as np
spec = importlib.util.spec_from_file_location("sr", Path.home() / "Pollen/microduck_rl/scripts/biped60_stairs_rate.py")
sr = importlib.util.module_from_spec(spec); spec.loader.exec_module(sr); ev = sr.ev
policy = ev.Policy(Path(sys.argv[1]))
model, data, bam = ev.load(ev.ROOT / "scene_ramp.xml")
key = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "STAND")
trunk = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "trunk_base")
for speed in (0.3, 0.45, 0.6):
    for x0 in (-0.3, 0.0, 0.2):
        mujoco.mj_resetDataKeyframe(model, data, key); data.qpos[0] = x0; mujoco.mj_forward(model, data)
        default = model.key_ctrl[key].copy(); bam.reset(data.qpos)
        action, stale, applied, pending, step = np.zeros(model.nu), np.zeros(model.nu), default.copy(), [], 0
        zmax, fell = data.qpos[2], False
        for k in range(int(20 / ev.CONTROL_DT)):
            rot = data.xmat[trunk].reshape(3, 3); yaw = math.atan2(rot[1, 0], rot[0, 0])
            err = (math.atan2(-data.qpos[1], 0.6) - yaw + math.pi) % (2 * math.pi) - math.pi
            cmd = np.array([speed, 0.0, float(np.clip(2 * err, -1, 1))])
            obs = np.concatenate([data.qvel[3:6], rot.T @ np.array([0, 0, -1.0]), data.qpos[7:7 + model.nu] - default, stale, action, cmd, policy.pose_commands(model, data, trunk)])
            stale = data.qvel[6:6 + model.nu].copy(); action = policy(obs)
            pending.append((step + ev.DELAY_STEPS, default + action))
            for _ in range(ev.DECIMATION):
                while pending and pending[0][0] <= step: applied = pending.pop(0)[1]
                bam.q_target[:] = applied; bam.update(); mujoco.mj_step(model, data); step += 1
            zmax = max(zmax, data.qpos[2])
            if rot[2, 2] < math.cos(math.radians(70)): fell = True; break
            if data.qpos[0] > 4.6: break
        print(f"speed {speed} x0 {x0:+.1f}: {'FELL' if fell else 'ok  '} at t {data.time:5.1f} s, x {data.qpos[0]:.2f} (ramp 0.8-4.0), trunk rose {zmax - 0.37:+.3f}", flush=True)
