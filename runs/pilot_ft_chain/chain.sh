#!/bin/bash
LOG=/workspace/pilot_chain.log
echo "CHAIN_START $(date -u +%FT%TZ)" >> $LOG
for step in "eval p2 0" "train p2 1" "eval p2 1" "train ident 0" "eval ident 0" "train ident 1" "eval ident 1" "train p2d 0" "eval p2d 0"; do
  bash /workspace/run_step.sh $step 3600
  if [ $? -ne 0 ]; then echo "CHAIN_ABORT at: $step $(date -u +%FT%TZ)" >> $LOG; exit 1; fi
done
echo "CHAIN_DONE $(date -u +%FT%TZ)" >> $LOG
