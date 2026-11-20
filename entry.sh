#!/bin/bash
set -euo pipefail
mode=${1:?}
arm=${2:?}
logs=/home/jovyan/quiet-mulberry-logs
mkdir -p "$logs"
exec > >(tee "$logs/$arm.log") 2>&1
trap 'rc=$?; printf "APPLICATION_EXIT=%s\n" "$rc"; exit 0' EXIT
output="/tmp/retrain-$arm"
mkdir -p "$output"
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false
export HF_HOME="$output/hf" TRITON_CACHE_DIR="$output/triton"
export HF_HUB_DISABLE_IMPLICIT_TOKEN=1
python -m venv --system-site-packages "$output/venv"
export PATH="$output/venv/bin:$PATH"
python -m pip install --disable-pip-version-check -q 'huggingface_hub>=0.34,<1' pybind11
python - <<'PY'
import os
import torch
from huggingface_hub import HfApi
assert torch.cuda.is_available()
name = torch.cuda.get_device_name(0)
assert torch.cuda.get_device_capability(0)[0] == 9, name
HfApi(token=os.environ["TRAIN_HF_TOKEN"]).repo_info(os.environ["TRAIN_HF_REPO"])
print("RUNTIME", name, torch.__version__, flush=True)
PY

if [[ "$mode" == dense ]]; then
  python -m pip install --disable-pip-version-check -q     wandb==0.25.1 tiktoken==0.12.0 loguru==0.7.3 schedulefree==1.4.1     pyarrow==20.0.0 transformers==4.51.3 datasets==3.6.0 bitsandbytes==0.45.5 opt_einsum
  (
    cd dense
    export PYTHONPATH=src:.
    python -m torch.distributed.run --standalone --nproc_per_node=1 retrain.py "$arm" "$output"
  )
else
  export MONARCH_CKPT_ROOT="$output/checkpoints" MONARCH_LOG_ROOT="$logs"
  export MONARCH_DATA_CACHE_PATH="$output/data-cache"
  export MONARCH_MICRO_BATCH=16 MONARCH_EVAL_INTERVAL=4000 MONARCH_ALLOW_NO_WANDB=1
  export MONARCH_SAVE_INTERVAL=17242
  optimizer=${arm%-n?}
  blocks=${arm: -1}
  (
    cd moe
    "$PWD/scripts/cloud_monarch_pretrain.sh" hmoe "$optimizer" "$blocks" ddp full
  )
fi
python publish.py "$mode" "$arm" "$output"
