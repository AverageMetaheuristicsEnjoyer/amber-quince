# Experiment D carrier v3 - large-batch AdamW (2026-11-26)

Sealed, immutable mlsub carrier for one 2xH100 experiment-D allocation.
Entry: bootstrap.py bench <control> (or storage <control> on a CPU node).
The payload is authenticated before any job code runs: the manifest pins the
encrypted and plaintext SHA-256, every tar member and the exact entry point.

| field | value |
|---|---|
| bundle | 184caeb35917894408ad |
| implementation pin | 1dc81fc7781dccdbe0ecb13889500a46a385b54b |
| dion pin | 7692479288f928a3d61d1cc58137b4dbe4f71000 |
| payload sha256 | a498265165290fc87be46bc90726f0dfc848faadfc9e308c7f17a9e90b2e37e8 |
| budget | 5400 s application wall (3 H100*h on 2 GPUs) |
| output | /home/jovyan/rebuttal-20261123/distributed/large-batch-adamw/<bundle>-<control> |

v3 fixes the v2 verifier bug: the entry now reassembles the full chunked point
and diagnostic instead of reading the short summary marker, and the driver
writes the run order into the point before emitting it. Pre-submit regression
covers missing chunks, missing pass marker and wrong order.

Protocol: ordinary dense AdamW vs dense Muon-Dion vs optimized two-block
Monarch-Muon combined, BF16 FSDP2 (reshard-after-forward), seq 4096,
mb2 x acc256 x 2 ranks = 4,194,304 tokens/update, identical synthetic data and
seeds, same physical GPU pair for both forward and reverse arm orders,
2 warmup + 5 measured complete updates per arm and order. A separate
CUDA-event forward/backward/optimizer pass runs after the primary window.

No NFS3 writes, no checkpoints, no W&B, no pip installs into shared volumes;
job scratch is under /tmp. A CPU storage sample is required within 15 minutes
of submission and must keep >=13 GiB free on home after the 64 MiB reserve.
