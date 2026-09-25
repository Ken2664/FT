#!/bin/bash
# usage: run_step.sh <train|eval> <cond> <seed> <timeout_sec>
export HF_HOME=/workspace/.cache/huggingface
cd /workspace/translesion
source /workspace/venv/bin/activate
KIND=$1; COND=$2; SEED=$3; TMO=$4
if [ "$KIND" = train ]; then
  CFG=configs/exp_pilot_ft_train_${COND}.yaml; RUN=runs/pilot_ft_train_${COND}_s${SEED}; MOD=code.train.run; EXTRA="--seed $SEED"
else
  CFG=configs/exp_pilot_ft_eval_${COND}_s${SEED}.yaml; RUN=runs/pilot_ft_eval_${COND}_s${SEED}; MOD=code.eval.run; EXTRA=""
fi
TAG=${KIND}_${COND}_s${SEED}
LOG=/workspace/pilot_chain.log
mkdir -p $RUN
echo "$TAG START $(date -u +%FT%TZ)" >> $LOG
python infra/preflight.py --config $CFG --run-dir $RUN > /workspace/pre_${TAG}.out 2>&1
RC_PRE=$?
echo "$TAG PREFLIGHT_RC=$RC_PRE $(date -u +%FT%TZ)" >> $LOG
if [ $RC_PRE -ne 0 ]; then echo "$TAG ABORT_PREFLIGHT" >> $LOG; exit 1; fi
nvidia-smi --query-gpu=timestamp,memory.used,memory.total --format=csv,noheader -l 3 > $RUN/vram_${KIND}.csv &
SAMP=$!
timeout $TMO python -m $MOD --config $CFG $EXTRA --run-dir $RUN > /workspace/${TAG}.out 2>&1
RC=$?
kill $SAMP
echo "$TAG RUN_RC=$RC $(date -u +%FT%TZ)" >> $LOG
exit $RC
