import datetime
import json
import os
import socket

import torch
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel

rank = int(os.environ["OMPI_COMM_WORLD_RANK"])
world = int(os.environ["OMPI_COMM_WORLD_SIZE"])
local_rank = int(os.environ["OMPI_COMM_WORLD_LOCAL_RANK"])
visible = torch.cuda.device_count()
assert world == 2, f"Expected 2 MPI ranks, got {world}"
assert visible >= 1, f"No GPUs visible on rank {rank}"
device = torch.device("cuda", local_rank if visible > 1 else 0)
torch.cuda.set_device(device)
os.environ.setdefault("MASTER_ADDR", socket.gethostname())
os.environ.setdefault("MASTER_PORT", "29543")
os.environ.setdefault("NCCL_DEBUG", "WARN")
dist.init_process_group("nccl", rank=rank, world_size=world, timeout=datetime.timedelta(seconds=45), device_id=device)

properties = torch.cuda.get_device_properties(device)
record = {"rank":rank,"local_rank":local_rank,"visible":visible,"gpu":properties.name,"uuid":str(properties.uuid)}
devices = [None, None]
dist.all_gather_object(devices, record)
assert len({d["uuid"] for d in devices}) == 2, devices
value = torch.tensor(float(rank + 1), device=device)
dist.all_reduce(value)
assert value.item() == 3.0, value.item()
module = DistributedDataParallel(torch.nn.Linear(4, 1, bias=False, device=device), device_ids=[device.index])
module(torch.full((1, 4), float(rank + 1), device=device)).sum().backward()
torch.testing.assert_close(module.module.weight.grad, torch.full((1, 4), 1.5, device=device))
if rank == 0:
    print("DDP_PROBE_PASS " + json.dumps({"gpus":devices,"all_reduce":3.0,"ddp_gradient":1.5}), flush=True)
dist.destroy_process_group()
