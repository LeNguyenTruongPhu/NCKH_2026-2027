#!/bin/bash

# Multi-Terrain Training Automation Script
# Huấn luyện chính sách để vịt có thể đi trên cát, sỏi, tuyết
#
# Usage: ./train_multiterrain_automated.sh [--gpu] [--skip-phase N] [--resume-from PATH]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODELS_DIR="$REPO_DIR/models"
LOG_DIR="$REPO_DIR/logs"
USE_GPU=false
SKIP_PHASE=""
RESUME_FROM=""
START_TIME=$(date +%s)

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --gpu)
            USE_GPU=true
            shift
            ;;
        --skip-phase)
            SKIP_PHASE="$2"
            shift 2
            ;;
        --resume-from)
            RESUME_FROM="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Setup environment
mkdir -p "$MODELS_DIR" "$LOG_DIR"
cd "$REPO_DIR"

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

if [ "$USE_GPU" = true ]; then
    export CUDA_VISIBLE_DEVICES=0
    echo -e "${GREEN}GPU Mode: Using CUDA${NC}"
else
    echo -e "${YELLOW}CPU Mode: Training will be slower${NC}"
fi

# Helper functions
log_phase() {
    echo -e "${BLUE}════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════${NC}"
    echo "$(date): $1" >> "$LOG_DIR/training.log"
}

log_step() {
    echo -e "${GREEN}→${NC} $1"
    echo "$(date): $1" >> "$LOG_DIR/training.log"
}

log_error() {
    echo -e "${RED}✗ ERROR: $1${NC}"
    echo "$(date): ERROR: $1" >> "$LOG_DIR/training.log"
}

log_success() {
    echo -e "${GREEN}✓ $1${NC}"
    echo "$(date): SUCCESS: $1" >> "$LOG_DIR/training.log"
}

elapsed_time() {
    local end=$SECONDS
    local hours=$((($end - $START_TIME) / 3600))
    local mins=$(((($end - $START_TIME) % 3600) / 60))
    echo "${hours}h ${mins}m"
}

# Verify environment
verify_environment() {
    log_phase "VERIFYING ENVIRONMENT"

    log_step "Checking Python..."
    python --version || { log_error "Python not found"; exit 1; }

    log_step "Checking for duck_rl module..."
    python -c "import duck_rl" || { log_error "duck_rl not installed"; exit 1; }

    log_step "Checking for MuJoCo..."
    python -c "import mujoco; print(f'MuJoCo version: {mujoco.__version__}')" || {
        log_error "MuJoCo not found. Install with: pip install mujoco"
        exit 1
    }

    if [ "$USE_GPU" = true ]; then
        log_step "Checking CUDA..."
        python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')" || {
            log_error "CUDA not available"
            exit 1
        }
    fi

    log_success "Environment verified"
}

# Phase 1: Baseline
phase_1_baseline() {
    if [ ! -z "$SKIP_PHASE" ] && [ "$SKIP_PHASE" -le 1 ]; then
        log_step "Skipping Phase 1"
        return
    fi

    log_phase "PHASE 1: BASELINE WALKING (Smooth Surface)"

    local model_dir="$MODELS_DIR/stage1_baseline"
    mkdir -p "$model_dir"

    log_step "Training on smooth surface with no randomization..."
    log_step "This phase teaches the duck basic walking gait"

    python -m duck_rl.train \
        --task walking \
        --model-dir "$model_dir" \
        --total-timesteps 10000000 \
        --learning-rate 3e-4 \
        --num-envs 8 \
        --seed 42 \
        --friction-range "(0.8, 0.8)" \
        --terrain-roughness 0 \
        --no-randomization \
        2>&1 | tee -a "$LOG_DIR/phase1.log"

    if [ -f "$model_dir/best_model.zip" ]; then
        cp "$model_dir/best_model.zip" "$MODELS_DIR/stage1_baseline_final.zip"
        log_success "Phase 1 completed - saved best model"
    else
        log_error "Phase 1 failed - no model file found"
        exit 1
    fi

    log_step "Phase 1 elapsed: $(elapsed_time)"
}

# Phase 2: Domain randomization
phase_2_randomized() {
    if [ ! -z "$SKIP_PHASE" ] && [ "$SKIP_PHASE" -le 2 ]; then
        log_step "Skipping Phase 2"
        return
    fi

    log_phase "PHASE 2: DOMAIN RANDOMIZATION"

    local model_dir="$MODELS_DIR/stage2_randomized"
    mkdir -p "$model_dir"

    local resume_model="${RESUME_FROM:-$MODELS_DIR/stage1_baseline_final.zip}"

    if [ ! -f "$resume_model" ]; then
        log_error "Resume model not found: $resume_model"
        exit 1
    fi

    log_step "Adding friction, terrain, and mass randomization..."
    log_step "Resume from: $resume_model"

    python -m duck_rl.train \
        --task walking \
        --model-dir "$model_dir" \
        --total-timesteps 5000000 \
        --learning-rate 2e-4 \
        --num-envs 16 \
        --seed 42 \
        --friction-range "(0.3, 1.2)" \
        --terrain-roughness 0.02 \
        --mass-range "(0.6, 1.5)" \
        --wind-force 0.5 \
        --resume-from "$resume_model" \
        2>&1 | tee -a "$LOG_DIR/phase2.log"

    if [ -f "$model_dir/best_model.zip" ]; then
        cp "$model_dir/best_model.zip" "$MODELS_DIR/stage2_randomized_final.zip"
        log_success "Phase 2 completed"
    else
        log_error "Phase 2 failed"
        exit 1
    fi

    log_step "Phase 2 elapsed: $(elapsed_time)"
}

# Phase 3: Terrain-specific
phase_3_terrain_specific() {
    if [ ! -z "$SKIP_PHASE" ] && [ "$SKIP_PHASE" -le 3 ]; then
        log_step "Skipping Phase 3"
        return
    fi

    log_phase "PHASE 3: TERRAIN-SPECIFIC POLICIES"

    local resume_model="${RESUME_FROM:-$MODELS_DIR/stage2_randomized_final.zip}"

    if [ ! -f "$resume_model" ]; then
        log_error "Resume model not found: $resume_model"
        exit 1
    fi

    # Sand training
    log_step "Training for SAND terrain (high friction, soft surface)..."
    python -m duck_rl.train \
        --task walking \
        --model-dir "$MODELS_DIR/stage3_sand" \
        --total-timesteps 3000000 \
        --learning-rate 1.5e-4 \
        --num-envs 8 \
        --seed 43 \
        --friction-range "(0.9, 1.3)" \
        --terrain-roughness 0.04 \
        --soft-ground \
        --resume-from "$resume_model" \
        2>&1 | tee -a "$LOG_DIR/phase3_sand.log"

    # Gravel training
    log_step "Training for GRAVEL terrain (uneven, unstable)..."
    python -m duck_rl.train \
        --task walking \
        --model-dir "$MODELS_DIR/stage3_gravel" \
        --total-timesteps 3000000 \
        --learning-rate 1.5e-4 \
        --num-envs 8 \
        --seed 44 \
        --friction-range "(0.4, 1.0)" \
        --terrain-roughness 0.08 \
        --terrain-type rocky \
        --resume-from "$resume_model" \
        2>&1 | tee -a "$LOG_DIR/phase3_gravel.log"

    # Snow training
    log_step "Training for SNOW terrain (low friction, slippery)..."
    python -m duck_rl.train \
        --task walking \
        --model-dir "$MODELS_DIR/stage3_snow" \
        --total-timesteps 3000000 \
        --learning-rate 1.5e-4 \
        --num-envs 8 \
        --seed 45 \
        --friction-range "(0.1, 0.4)" \
        --terrain-roughness 0.03 \
        --deformable-surface \
        --resume-from "$resume_model" \
        2>&1 | tee -a "$LOG_DIR/phase3.log"

    log_success "Phase 3 completed - all terrains trained"
    log_step "Phase 3 elapsed: $(elapsed_time)"
}

# Phase 4: Multi-terrain unified
phase_4_multiterrain() {
    if [ ! -z "$SKIP_PHASE" ] && [ "$SKIP_PHASE" -le 4 ]; then
        log_step "Skipping Phase 4"
        return
    fi

    log_phase "PHASE 4: UNIFIED MULTI-TERRAIN POLICY"

    local model_dir="$MODELS_DIR/stage4_multiterrain"
    mkdir -p "$model_dir"

    local resume_model="${RESUME_FROM:-$MODELS_DIR/stage2_randomized_final.zip}"

    if [ ! -f "$resume_model" ]; then
        log_error "Resume model not found: $resume_model"
        exit 1
    fi

    log_step "Training single policy that handles ALL terrains..."
    log_step "Using curriculum learning: easy → medium → hard"

    python -m duck_rl.train \
        --task walking \
        --model-dir "$model_dir" \
        --total-timesteps 10000000 \
        --learning-rate 1e-4 \
        --num-envs 32 \
        --seed 42 \
        --friction-range "(0.1, 1.3)" \
        --terrain-roughness "random(0.0, 0.08)" \
        --terrain-type random \
        --mass-range "(0.5, 2.0)" \
        --wind-force 1.0 \
        --use-curriculum \
        --resume-from "$resume_model" \
        2>&1 | tee -a "$LOG_DIR/phase4.log"

    if [ -f "$model_dir/best_model.zip" ]; then
        cp "$model_dir/best_model.zip" "$MODELS_DIR/stage4_multiterrain_final.zip"
        log_success "Phase 4 completed - unified policy trained"
    else
        log_error "Phase 4 failed"
        exit 1
    fi

    log_step "Phase 4 elapsed: $(elapsed_time)"
}

# Phase 5: Recovery policy
phase_5_recovery() {
    if [ ! -z "$SKIP_PHASE" ] && [ "$SKIP_PHASE" -le 5 ]; then
        log_step "Skipping Phase 5"
        return
    fi

    log_phase "PHASE 5: RECOVERY POLICY (Get Up)"

    local model_dir="$MODELS_DIR/stage5_getup"
    mkdir -p "$model_dir"

    log_step "Training recovery policy for when duck falls..."

    python -m duck_rl.train \
        --task getup \
        --model-dir "$model_dir" \
        --total-timesteps 2000000 \
        --learning-rate 2e-4 \
        --num-envs 8 \
        --seed 50 \
        2>&1 | tee -a "$LOG_DIR/phase5.log"

    if [ -f "$model_dir/best_model.zip" ]; then
        cp "$model_dir/best_model.zip" "$MODELS_DIR/stage5_getup_final.zip"
        log_success "Phase 5 completed - recovery policy trained"
    else
        log_error "Phase 5 failed"
        exit 1
    fi

    log_step "Phase 5 elapsed: $(elapsed_time)"
}

# Export policies
export_policies() {
    log_phase "EXPORTING POLICIES TO ONNX"

    local walking_model="$MODELS_DIR/stage4_multiterrain_final.zip"
    local getup_model="$MODELS_DIR/stage5_getup_final.zip"

    if [ ! -f "$walking_model" ]; then
        log_error "Walking model not found: $walking_model"
        return 1
    fi

    log_step "Exporting multi-terrain walking policy..."
    python -m duck_rl.export \
        --model-path "$walking_model" \
        --output "$MODELS_DIR/multiterrain_walking.onnx" \
        2>&1 | tee -a "$LOG_DIR/export.log"

    if [ -f "$MODELS_DIR/multiterrain_walking.onnx" ]; then
        log_success "Walking policy exported"
        ls -lh "$MODELS_DIR/multiterrain_walking.onnx"
    else
        log_error "Export failed"
        return 1
    fi

    if [ -f "$getup_model" ]; then
        log_step "Exporting recovery policy..."
        python -m duck_rl.export \
            --model-path "$getup_model" \
            --output "$MODELS_DIR/multiterrain_getup.onnx" \
            2>&1 | tee -a "$LOG_DIR/export.log"

        if [ -f "$MODELS_DIR/multiterrain_getup.onnx" ]; then
            log_success "Recovery policy exported"
        fi
    fi
}

# Main execution
main() {
    log_phase "MULTI-TERRAIN TRAINING STRATEGY"
    log_step "Repository: $REPO_DIR"
    log_step "Models directory: $MODELS_DIR"
    log_step "Logs directory: $LOG_DIR"

    verify_environment

    phase_1_baseline
    phase_2_randomized
    phase_3_terrain_specific
    phase_4_multiterrain
    phase_5_recovery

    export_policies

    log_phase "✓ TRAINING COMPLETED SUCCESSFULLY!"
    log_step "Total time: $(elapsed_time)"
    echo ""
    echo -e "${GREEN}Next steps:${NC}"
    echo "  1. Test in simulator:"
    echo "     export DUCK_POLICIES_DIR=$MODELS_DIR"
    echo "     cd ../microduck && scripts/duck-sim up"
    echo ""
    echo "  2. Evaluate performance:"
    echo "     python evaluate_multiterrain.py"
    echo ""
    echo "  3. Deploy to robot:"
    echo "     scripts/dev-push.sh robot@192.168.1.100"
    echo ""
}

main
