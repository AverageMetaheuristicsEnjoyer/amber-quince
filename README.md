# Experiment D carrier v4 - large-batch AdamW (2026-11-26)

Sealed, immutable mlsub carrier for one corrected 2xH100 experiment-D run.
Entry: bootstrap.py bench <control> (or storage <control> on a CPU node).
The payload is authenticated before any job code runs.

| field | value |
|---|---|
| bundle | 288d4d61bf8e496308a3 |
| implementation pin | 1dc81fc7781dccdbe0ecb13889500a46a385b54b |
| dion pin | 7692479288f928a3d61d1cc58137b4dbe4f71000 |
| payload sha256 | 0a52a4c60e2ab6ff7627c2e687bf0e83e7836de27d607cb0bf7816fdbff4cc44 |
| budget | 4800 s in-job guard (2.67 H100*h), under the 2.84 H100*h all-in remainder |
| output | /home/jovyan/rebuttal-20261123/distributed/large-batch-adamw/<bundle>-<control> |

v4 differs from v3 bundle 184caeb35917894408ad ONLY in the aggregate guard
(BENCH_BUDGET 5400 -> 4800); every other payload member is byte-identical.
v3 fixed the v2 verifier bug (full chunked point assembly, order check,
F+B+O+other identity) and the orderless-point emit.

Protocol unchanged: ordinary dense AdamW vs dense Muon-Dion vs optimized
two-block Monarch-Muon combined, BF16 FSDP2 reshard-after-forward, seq 4096,
mb2 x acc256 x 2 ranks = 4,194,304 tokens/update, identical synthetic data and
seeds, same physical GPU pair for AB then BA, 2 warmup + 5 measured updates per
arm and order, separate CUDA-event F/B/O diagnostic pass afterwards.

No NFS3 writes, no checkpoints, no W&B, no shared pip installs; scratch /tmp.
CPU storage sample required within 15 min; home >=13 GiB after the 64 MiB
reserve.
