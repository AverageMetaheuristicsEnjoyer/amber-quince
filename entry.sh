#!/bin/bash
set -euo pipefail
world=${OMPI_COMM_WORLD_SIZE:?}
rank=${OMPI_COMM_WORLD_LOCAL_RANK:?}
logs=/home/jovyan/quiet-mulberry-logs
output=$(mktemp -d /tmp/monarch-ddp-bench.XXXXXXXX)
mkdir -p "$logs"
exec > >(tee "$logs/ddp-bench-${world}gpu-rank${rank}.log") 2>&1
trap 'rc=$?; printf "BENCH_EXIT=%s\n" "$rc"; rm -rf -- "$output"; exit "$rc"' EXIT
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false
export TRITON_CACHE_DIR="$output/triton"
python -m venv --system-site-packages "$output/venv"
export PATH="$output/venv/bin:$PATH"
python -m pip install --disable-pip-version-check -q pybind11
python - "$rank" <<'PY'
import sys
import torch
rank = int(sys.argv[1])
device = torch.cuda.get_device_properties(rank)
assert device.major == 9, device.name
print("BENCH_GPU", rank, device.name, device.uuid, flush=True)
PY
export MONARCH_LOG_ROOT=$logs MONARCH_GLOBAL_BATCH=208 MONARCH_MICRO_BATCH=$((16 / world))
export MONARCH_BENCH_ITERS=15 WANDB_MODE=offline
export MONARCH_DATA_CACHE_PATH="/tmp/monarch-ddp-bench-cache-${world}gpu"
export MONARCH_RUN_SUFFIX=ddp-timing-20261120
cd moe
bash scripts/cloud_monarch_pretrain.sh hmoe muon 2 ddp bench
