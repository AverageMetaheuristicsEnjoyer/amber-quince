from pathlib import Path
import re

root = Path("/home/jovyan/quiet-mulberry-logs")
for log in sorted(root.glob("*.log")):
    data = log.read_text(errors="replace").splitlines()
    signals = [
        line for line in data
        if re.search(r"RUNTIME|TRAIN_RECIPE|MONARCH_TRAIN_CONFIG|MONARCH_MODEL_CHECK|TRAIN_EXIT|APPLICATION_EXIT|validation loss|^>Eval|^Train:|elapsed time per iteration|Error|Exception|Killed|NotImplemented|FAILED|CHECKPOINT_PUBLISHED", line, re.I)
    ]
    errors = [line for line in data if re.search(r"Error|Exception|Killed|NotImplemented|FAILED",line,re.I)]
    print("FILE", log.name, "LINES", len(data), flush=True)
    for line in (signals[:3] + signals[-6:] + errors[-3:]):
        print(line[:350], flush=True)
print("PROGRESS_EXIT=0",flush=True)
