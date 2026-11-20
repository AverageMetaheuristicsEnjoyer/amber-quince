import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile

from cryptography.fernet import Fernet

parser = argparse.ArgumentParser()
parser.add_argument("key", type=Path, help="Path to the separately shared Fernet key")
parser.add_argument("output", type=Path, help="New folder for the source tree")
args = parser.parse_args()
here = Path(__file__).resolve().parent
manifest = json.loads((here / "manifest.json").read_text())
encrypted = (here / "payload.fernet").read_bytes()
if hashlib.sha256(encrypted).hexdigest() != manifest["sha256"]:
    raise ValueError("Encrypted archive checksum mismatch")
archive = Fernet(args.key.read_bytes().strip()).decrypt(encrypted)
args.output.mkdir(parents=True, exist_ok=False)
with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
    bundle.extractall(args.output, filter="data")
print(manifest["source_commit"])
