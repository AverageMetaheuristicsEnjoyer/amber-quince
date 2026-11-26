"""Read and verify a sealed, immutable experiment-D job payload."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile
import time
import traceback

MODES = ("validate", "storage", "bench")
BUDGET = {"validate": 180, "storage": 180, "bench": 5400}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    started = time.monotonic()
    assert len(sys.argv) >= 2 and sys.argv[1] in MODES
    mode = sys.argv[1]
    offline = os.environ.pop("LBA_LOCAL_VALIDATE", "") == "1"
    assert not offline or mode == "validate"
    os.umask(0o077)
    key = os.environ.pop("BUNDLE_KEY")
    if os.environ.get("OMPI_COMM_WORLD_RANK", "0") != "0":
        print("LBA_MPI_NONZERO_IDLE", flush=True)
        return
    for name in ("PYTHONPATH", "PYTHONUSERBASE", "PYTHONOPTIMIZE"):
        os.environ.pop(name, None)
    os.environ.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1")
    root = Path(__file__).resolve().parent
    public = json.loads((root / "manifest.json").read_text())
    payload = (root / "payload.fernet").read_bytes()
    assert sha(payload) == public["payload_sha256"]
    tmp = os.statvfs("/tmp")
    assert offline or (tmp.f_bavail * tmp.f_frsize >= 20 * (1 << 30) and tmp.f_favail >= 100000)
    with tempfile.TemporaryDirectory(prefix="sealed-lba-", dir="/tmp") as work:
        directory = Path(work)
        if not offline:
            from importlib.util import find_spec
            if find_spec("cryptography") is None:
                deps = directory / "deps"
                subprocess.run([sys.executable, "-m", "pip", "install", "--no-cache-dir",
                                "--only-binary=:all:", "--disable-pip-version-check",
                                "--target", str(deps), "cryptography==46.0.5"], check=True,
                               timeout=65, env=dict(os.environ, TMPDIR=work, XDG_CACHE_HOME=work))
                sys.path.insert(0, str(deps))
        from cryptography.fernet import Fernet
        raw = Fernet(key.encode()).decrypt(payload)
        del key
        assert sha(raw) == public["plaintext_sha256"]
        target = directory / "app"
        target.mkdir()
        members = {}
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
            for member in archive:
                relative = PurePosixPath(member.name)
                assert member.isfile() and not relative.is_absolute() and ".." not in relative.parts
                assert member.name == str(relative) and member.name not in members
                assert member.size <= 64 << 20
                contents = archive.extractfile(member).read()
                members[member.name] = sha(contents)
                path = target.joinpath(*relative.parts)
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as stream:
                    stream.write(contents)
        manifest = json.loads((target / "bundle_manifest.json").read_text())
        assert public["bundle_id"] == sha((target / "bundle_manifest.json").read_bytes())[:20]
        del members["bundle_manifest.json"]
        assert members == manifest["files"] and manifest["entry"] == "entry.py"
        env = dict(os.environ, LBA_BUNDLE_ID=public["bundle_id"],
                   LBA_BOOT_MONOTONIC=str(started),
                   LBA_IMPLEMENTATION_COMMIT=manifest["pin"])
        print("LBA_BUNDLE_AUTHENTICATED " + public["bundle_id"], flush=True)
        subprocess.run([sys.executable, "-B", manifest["entry"], *sys.argv[1:]], cwd=target,
                       env=env, check=True, timeout=max(1, BUDGET[mode] - (time.monotonic() - started)))


if __name__ == "__main__":
    if not sys.flags.optimize:
        try:
            main()
        except Exception:
            traceback.print_exc()
            print("LBA_JOB_FAIL mode=" + str(sys.argv[1:2]), flush=True)
            if os.getenv("LBA_LOCAL_VERIFY_STRICT") == "1":
                sys.exit(1)
    else:
        raise SystemExit("experiment D requires Python assertions")
