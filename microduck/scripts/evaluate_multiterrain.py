#!/usr/bin/env python3
"""
Multi-terrain policy evaluation script.

Evaluate how well the trained policy performs on different terrains:
- Sand (high friction, soft)
- Gravel (uneven, unstable)
- Snow (low friction, slippery)

Usage:
    python evaluate_multiterrain.py --model-path models/stage4_multiterrain_final.zip
    python evaluate_multiterrain.py --model-path models/stage4_multiterrain_final.zip --render
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_model(model_path: str):
    """Load trained policy model."""
    try:
        # Import here to avoid dependency if not needed
        from duck_rl.policy import load_policy
        logger.info(f"Loading model from {model_path}")
        return load_policy(model_path)
    except ImportError as e:
        logger.error(f"Failed to import duck_rl: {e}")
        logger.error("Make sure duck_rl is installed and microduck_rl/venv is activated")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        sys.exit(1)


def make_env(terrain: str, num_envs: int = 1, render: bool = False):
    """Create MuJoCo environment with specified terrain."""
    try:
        from duck_rl.env import make_env as make_env_impl
        logger.debug(f"Creating environment with terrain={terrain}, num_envs={num_envs}")
        return make_env_impl(terrain=terrain, num_envs=num_envs, render=render)
    except ImportError as e:
        logger.error(f"Failed to import duck_rl.env: {e}")
        sys.exit(1)


def run_evaluation_episode(env, policy, max_steps: int = 1000) -> Dict:
    """Run a single evaluation episode and return metrics."""
    obs = env.reset()
    done = False
    step_count = 0
    episode_reward = 0.0
    fell = False
    total_distance = 0.0
    max_height = 0.0

    while not done and step_count < max_steps:
        # Policy prediction
        action = policy.predict(obs)

        # Environment step
        obs, reward, done, info = env.step(action)

        # Track metrics
        episode_reward += reward
        step_count += 1

        if info.get('fell'):
            fell = True

        if 'distance' in info:
            total_distance += info['distance']

        if 'com_height' in info:
            max_height = max(max_height, info['com_height'])

    return {
        'episode_reward': episode_reward,
        'episode_length': step_count,
        'fell': fell,
        'total_distance': total_distance,
        'max_height': max_height,
    }


def evaluate_terrain(
    policy,
    terrain: str,
    num_episodes: int = 10,
    render: bool = False
) -> Dict:
    """Evaluate policy on a specific terrain."""
    logger.info(f"\nEvaluating on {terrain.upper()} terrain ({num_episodes} episodes)...")

    # Create environment
    env = make_env(terrain=terrain, num_envs=1, render=render)

    # Run episodes
    results = []
    for episode in range(num_episodes):
        logger.debug(f"  Episode {episode + 1}/{num_episodes}...", end=' ')
        episode_data = run_evaluation_episode(env, policy)
        results.append(episode_data)
        logger.debug(f"Return: {episode_data['episode_reward']:.1f}, "
                    f"Length: {episode_data['episode_length']}s, "
                    f"Fell: {episode_data['fell']}")

    # Aggregate statistics
    rewards = [r['episode_reward'] for r in results]
    lengths = [r['episode_length'] for r in results]
    falls = sum(1 for r in results if r['fell'])
    distances = [r['total_distance'] for r in results]

    terrain_stats = {
        'terrain': terrain,
        'num_episodes': num_episodes,
        'avg_return': float(np.mean(rewards)),
        'std_return': float(np.std(rewards)),
        'min_return': float(np.min(rewards)),
        'max_return': float(np.max(rewards)),
        'avg_episode_length': float(np.mean(lengths)),
        'std_episode_length': float(np.std(lengths)),
        'fall_rate': falls / num_episodes,
        'success_rate': 1.0 - (falls / num_episodes),
        'avg_distance': float(np.mean(distances)),
        'all_episodes': results,
    }

    return terrain_stats


def print_results(results: Dict[str, Dict]):
    """Print evaluation results in a nice format."""
    print("\n" + "=" * 80)
    print("MULTI-TERRAIN POLICY EVALUATION RESULTS")
    print("=" * 80)

    for terrain, stats in results.items():
        print(f"\n{terrain.upper()} TERRAIN")
        print("-" * 80)
        print(f"  Episodes:            {stats['num_episodes']}")
        print(f"  Avg Return:          {stats['avg_return']:.1f} ± {stats['std_return']:.1f}")
        print(f"    (min: {stats['min_return']:.1f}, max: {stats['max_return']:.1f})")
        print(f"  Avg Episode Length:  {stats['avg_episode_length']:.1f} ± {stats['std_episode_length']:.1f} steps")
        print(f"  Success Rate:        {stats['success_rate']*100:.1f}%")
        print(f"  Fall Rate:           {stats['fall_rate']*100:.1f}%")
        print(f"  Avg Distance:        {stats['avg_distance']:.2f} m")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("-" * 80)

    all_fall_rates = {t: s['fall_rate'] for t, s in results.items()}
    all_returns = {t: s['avg_return'] for t, s in results.items()}

    print(f"\nFall Rates:")
    for terrain, fall_rate in all_fall_rates.items():
        status = "✓ PASS" if fall_rate < 0.05 else "✗ FAIL" if fall_rate > 0.10 else "⚠ WARNING"
        print(f"  {terrain:10} {fall_rate*100:5.1f}%  {status}")

    print(f"\nAverage Returns:")
    for terrain, avg_return in all_returns.items():
        status = "✓ EXCELLENT" if avg_return > 250 else "✓ GOOD" if avg_return > 200 else "⚠ OK"
        print(f"  {terrain:10} {avg_return:6.1f}  {status}")

    # Overall assessment
    print(f"\nOverall Assessment:")
    overall_pass = all(fr < 0.05 for fr in all_fall_rates.values())
    overall_good = all(ret > 200 for ret in all_returns.values())

    if overall_pass and overall_good:
        print("  ✓✓✓ POLICY IS READY FOR DEPLOYMENT ✓✓✓")
    elif overall_pass:
        print("  ✓ Policy passes safety criteria but could be more efficient")
    else:
        print("  ✗ Policy needs more training - fall rate too high")

    print("=" * 80 + "\n")


def save_results(results: Dict[str, Dict], output_file: str):
    """Save evaluation results to JSON file."""
    # Remove 'all_episodes' for JSON serialization
    clean_results = {}
    for terrain, stats in results.items():
        clean_stats = {k: v for k, v in stats.items() if k != 'all_episodes'}
        clean_results[terrain] = clean_stats

    with open(output_file, 'w') as f:
        json.dump(clean_results, f, indent=2)

    logger.info(f"Results saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate multi-terrain walking policy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic evaluation
  python evaluate_multiterrain.py \\
    --model-path models/stage4_multiterrain_final.zip

  # With visualization
  python evaluate_multiterrain.py \\
    --model-path models/stage4_multiterrain_final.zip \\
    --render

  # More episodes, more thorough
  python evaluate_multiterrain.py \\
    --model-path models/stage4_multiterrain_final.zip \\
    --episodes 20
        """
    )

    parser.add_argument(
        '--model-path',
        type=str,
        required=True,
        help='Path to trained policy model (.zip file)'
    )
    parser.add_argument(
        '--episodes',
        type=int,
        default=10,
        help='Number of episodes per terrain (default: 10)'
    )
    parser.add_argument(
        '--render',
        action='store_true',
        help='Render MuJoCo visualization during evaluation'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='evaluation_results.json',
        help='Output file for results (default: evaluation_results.json)'
    )
    parser.add_argument(
        '--terrains',
        type=str,
        default='sand,gravel,snow,default',
        help='Comma-separated list of terrains to evaluate (default: sand,gravel,snow,default)'
    )

    args = parser.parse_args()

    # Check model exists
    model_path = Path(args.model_path)
    if not model_path.exists():
        logger.error(f"Model not found: {args.model_path}")
        sys.exit(1)

    # Load policy
    logger.info(f"Loading policy from {args.model_path}")
    policy = load_model(str(model_path))

    # Parse terrains
    terrains = [t.strip() for t in args.terrains.split(',')]

    # Evaluate on each terrain
    logger.info(f"\nStarting evaluation on {len(terrains)} terrains")
    logger.info(f"Episodes per terrain: {args.episodes}")
    logger.info(f"Rendering: {args.render}")

    results = {}
    for terrain in terrains:
        try:
            stats = evaluate_terrain(
                policy,
                terrain=terrain,
                num_episodes=args.episodes,
                render=args.render
            )
            results[terrain] = stats
        except Exception as e:
            logger.error(f"Failed to evaluate on {terrain}: {e}")
            continue

    # Print and save results
    if results:
        print_results(results)
        save_results(results, args.output)
        logger.info(f"Full results saved to {args.output}")
    else:
        logger.error("No evaluation results to report")
        sys.exit(1)


if __name__ == '__main__':
    main()
