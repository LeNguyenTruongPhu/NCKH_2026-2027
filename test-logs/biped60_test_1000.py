#!/usr/bin/env python3
"""Test a BIPED-C3 policy in N parallel simulated environments (GPU, mjlab), one 20 s episode
each, under the same conditions it was trained in, and log every environment's result.

    .venv/bin/python scripts/biped60_test_1000.py <task> <checkpoint.pt> <out_dir> [--num-envs 1000] [--seed 2026]

Conditions are the training env's (`play=False`): every terrain type and difficulty row, random
velocity commands, mass/CoM/friction/armature randomisation, pushes, actuator delay. Each env runs
until its first episode ends (fall, out of bounds, or the 20 s time-out); what happens after the
automatic reset is ignored.

Writes `<out_dir>/envs.csv` (one row per environment) and `<out_dir>/summary.json`.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import asdict
from pathlib import Path

import torch

import mjlab_microduck.tasks  # noqa: F401  (registers the tasks)
from mjlab.envs import ManagerBasedRlEnv
from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
from mjlab.tasks.registry import load_env_cfg, load_rl_cfg, load_runner_cls
from mjlab.utils.torch import configure_torch_backends

ap = argparse.ArgumentParser()
ap.add_argument("task")
ap.add_argument("checkpoint")
ap.add_argument("out_dir")
ap.add_argument("--num-envs", type=int, default=1000)
ap.add_argument("--seed", type=int, default=2026)
args = ap.parse_args()
out = Path(args.out_dir)
out.mkdir(parents=True, exist_ok=True)

configure_torch_backends()
device = "cuda:0"
env_cfg = load_env_cfg(args.task, play=False)
agent_cfg = load_rl_cfg(args.task)
env_cfg.scene.num_envs = args.num_envs
env_cfg.seed = args.seed
gen = env_cfg.scene.terrain.terrain_generator
type_names = list(gen.sub_terrains.keys())
num_rows = gen.num_rows

t0 = time.time()
env = ManagerBasedRlEnv(cfg=env_cfg, device=device)
venv = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)
runner_cls = load_runner_cls(args.task) or MjlabOnPolicyRunner
runner = runner_cls(venv, asdict(agent_cfg), device=device)
runner.load(args.checkpoint, load_cfg={"actor": True}, strict=True, map_location=device)
policy = runner.get_inference_policy(device=device)
print(f"[test] {args.task}: {args.num_envs} envs, checkpoint {args.checkpoint}, seed {env_cfg.seed}, "
      f"set up in {time.time() - t0:.1f} s", flush=True)

N = args.num_envs
dt = env.step_dt
max_steps = int(env.max_episode_length)
robot = env.scene["robot"]
terrain = env.scene.terrain
tm = env.termination_manager
cm = env.command_manager
level = terrain.terrain_levels.clone()
ttype = terrain.terrain_types.clone()

# Per-env accumulators, over the first episode only.
alive = torch.ones(N, dtype=torch.bool, device=device)
steps = torch.zeros(N, device=device)
end = torch.full((N,), -1, dtype=torch.long, device=device)  # index into term names
term_names = list(tm.active_terms)
start = robot.data.root_link_pos_w.clone()
last = start.clone()
err_vx = torch.zeros(N, device=device)
err_vy = torch.zeros(N, device=device)
err_wz = torch.zeros(N, device=device)
cmd_vx = torch.zeros(N, device=device)
best_fwd = torch.zeros(N, device=device)
backing = torch.zeros(N, dtype=torch.bool, device=device)
step_backs = torch.zeros(N, device=device)
z_max = start[:, 2].clone()
z_min = start[:, 2].clone()

obs = venv.get_observations()
t1 = time.time()
with torch.inference_mode():
    for k in range(max_steps + 2):
        cmd = cm.get_command("twist")
        v = robot.data.root_link_lin_vel_b
        w = robot.data.root_link_ang_vel_b
        a = alive.float()
        err_vx += a * (v[:, 0] - cmd[:, 0]).abs()
        err_vy += a * (v[:, 1] - cmd[:, 1]).abs()
        err_wz += a * (w[:, 2] - cmd[:, 2]).abs()
        cmd_vx += a * cmd[:, 0]
        pos = robot.data.root_link_pos_w
        last = torch.where(alive[:, None], pos, last)
        z_max = torch.where(alive, torch.maximum(z_max, pos[:, 2]), z_max)
        z_min = torch.where(alive, torch.minimum(z_min, pos[:, 2]), z_min)
        fwd = pos[:, 0] - start[:, 0]
        new_best = alive & (fwd > best_fwd)
        best_fwd = torch.where(new_best, fwd, best_fwd)
        backing = backing & ~new_best
        went_back = alive & ~backing & (fwd < best_fwd - 0.03)
        step_backs += went_back.float()
        backing = backing | went_back

        obs, _, dones, _ = venv.step(policy(obs))
        steps += alive.float()
        done = dones.bool() & alive
        if done.any():
            which = torch.full((N,), -1, dtype=torch.long, device=device)
            for i, name in enumerate(term_names):
                which = torch.where(done & tm.get_term(name).bool() & (which < 0), torch.full_like(which, i), which)
            end = torch.where(done, which, end)
            alive = alive & ~done
        if k % 100 == 0:
            print(f"[test] step {k:4d}/{max_steps}: {int(alive.sum())} still in their first episode, "
                  f"{int((end >= 0).sum())} ended", flush=True)
        if not alive.any():
            break
print(f"[test] ran {k + 1} steps ({(k + 1) * dt:.1f} s simulated) in {time.time() - t1:.1f} s", flush=True)

lo, hi = None, None
for name, sub in gen.sub_terrains.items():
    if hasattr(sub, "step_height_range"):
        lo, hi = sub.step_height_range
        break

rows = []
n_alive = steps.clamp(min=1)
for i in range(N):
    t = int(ttype[i])
    r = int(level[i])
    name = type_names[t]
    stairs = "stairs" in name
    res = term_names[int(end[i])] if int(end[i]) >= 0 else "time_out"
    rows.append({
        "env": i,
        "terrain": name,
        "row": r,
        "riser_cm": f"{100 * (lo + (hi - lo) * r / num_rows):.1f}-{100 * (lo + (hi - lo) * (r + 1) / num_rows):.1f}" if stairs and lo is not None else "",
        "result": res,
        "fell": int(res in ("fell_over", "nan_state")),
        "survived_s": round(float(steps[i]) * dt, 2),
        "cmd_vx_mean": round(float(cmd_vx[i] / n_alive[i]), 3),
        "err_vx": round(float(err_vx[i] / n_alive[i]), 3),
        "err_vy": round(float(err_vy[i] / n_alive[i]), 3),
        "err_wz": round(float(err_wz[i] / n_alive[i]), 3),
        "dist_xy_m": round(float(torch.linalg.norm(last[i, :2] - start[i, :2])), 3),
        "forward_x_m": round(float(last[i, 0] - start[i, 0]), 3),
        "max_rise_m": round(float(z_max[i] - start[i, 2]), 3),
        "max_drop_m": round(float(start[i, 2] - z_min[i]), 3),
        "step_backs": int(step_backs[i]),
    })

import csv
with open(out / "envs.csv", "w", newline="") as f:
    w = csv.DictWriter(f, list(rows[0]))
    w.writeheader()
    w.writerows(rows)


def stats(sel):
    n = len(sel)
    if not n:
        return None
    fell = sum(r["fell"] for r in sel)
    return {
        "envs": n,
        "fell": fell,
        "fall_rate_pct": round(100 * fell / n, 1),
        "time_out": sum(r["result"] == "time_out" for r in sel),
        "out_of_bounds": sum(r["result"] == "out_of_terrain_bounds" for r in sel),
        "survived_s_mean": round(sum(r["survived_s"] for r in sel) / n, 2),
        "err_vx_mean": round(sum(r["err_vx"] for r in sel) / n, 3),
        "err_wz_mean": round(sum(r["err_wz"] for r in sel) / n, 3),
        "dist_xy_mean": round(sum(r["dist_xy_m"] for r in sel) / n, 2),
        "max_rise_mean": round(sum(r["max_rise_m"] for r in sel) / n, 3),
        "max_drop_mean": round(sum(r["max_drop_m"] for r in sel) / n, 3),
        "step_backs_mean": round(sum(r["step_backs"] for r in sel) / n, 2),
    }


summary = {
    "task": args.task, "checkpoint": args.checkpoint, "num_envs": N, "seed": env_cfg.seed,
    "episode_s": round(max_steps * dt, 1), "riser_range_cm": [100 * lo, 100 * hi] if lo is not None else None,
    "all": stats(rows),
    "by_terrain": {n: stats([r for r in rows if r["terrain"] == n]) for n in type_names},
    "by_row": {f"{r}": stats([x for x in rows if x["row"] == r and "stairs" in x["terrain"]]) for r in range(num_rows)},
}
(out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
a = summary["all"]
print(f"[test] RESULT: {a['envs']} envs, fell {a['fell']} ({a['fall_rate_pct']}%), time-out {a['time_out']}, "
      f"out of bounds {a['out_of_bounds']}, survived {a['survived_s_mean']} s on average", flush=True)
for n, s in summary["by_terrain"].items():
    if s:
        print(f"[test]   {n:24s} {s['envs']:4d} envs  fell {s['fell']:3d} ({s['fall_rate_pct']:5.1f}%)  "
              f"vx err {s['err_vx_mean']:.3f} m/s  yaw err {s['err_wz_mean']:.3f} rad/s  rise {s['max_rise_mean']:.3f} m  drop {s['max_drop_mean']:.3f} m  dist {s['dist_xy_mean']:.1f} m", flush=True)
