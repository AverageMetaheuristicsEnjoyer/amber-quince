"""Authenticated C-JM1 carrier entry; does not alter the shared run.sh."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

os.umask(0o077)
key = os.environ.pop("BUNDLE_KEY")
root = Path(__file__).resolve().parent
payload = (root / "payload.fernet").read_bytes()
public_manifest = json.loads((root / "manifest.json").read_text())
if hashlib.sha256(payload).hexdigest() != public_manifest["payload_sha256"]:
    raise RuntimeError("Encrypted payload checksum mismatch")

with tempfile.TemporaryDirectory(prefix="cjm1-job-", dir="/tmp") as directory:
    destination = Path(directory)
    deps = destination / "dependencies"
    subprocess.run([
        sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
        "--no-cache-dir", "--only-binary=:all:", "--target", str(deps),
        "cryptography==46.0.5",
    ], check=True)
    sys.path.insert(0, str(deps))
    from cryptography.fernet import Fernet

    plaintext = Fernet(key.encode()).decrypt(payload)
    del key
    source = destination / "source"
    source.mkdir()
    with tarfile.open(fileobj=io.BytesIO(plaintext), mode="r:gz") as archive:
        if sys.version_info >= (3, 12):
            archive.extractall(source, filter="data")
        else:
            # Local preflight uses Python 3.9.  The payload is already
            # authenticated; accept only regular relative files when the
            # interpreter lacks tarfile's extraction filter.
            members = archive.getmembers()
            if any(not m.isfile() or Path(m.name).is_absolute() or ".." in Path(m.name).parts
                   for m in members):
                raise RuntimeError("Unsafe bundle archive member")
            archive.extractall(source)
    del plaintext
    manifest = json.loads((source / "bundle_manifest.json").read_text())
    if manifest["bundle_id"] != public_manifest["bundle_id"]:
        raise RuntimeError("Bundle id mismatch")
    print("BUNDLE_AUTHENTICATED=" + manifest["bundle_id"], flush=True)
    if sys.argv[1:] == ["--verify-only"]:
        raise SystemExit(0)
    if not sys.argv[1:]:
        raise SystemExit("usage: cjm1_bootstrap.py ARM [--smoke]")

    rank = os.environ.get("OMPI_COMM_WORLD_RANK", "0")
    if rank != "0":
        print(f"CJM1_TRAINING_NONZERO_RANK_IDLE rank={rank}", flush=True)
        raise SystemExit(0)

    bundle_id = manifest["bundle_id"]
    log_root = Path("/home/jovyan/rebuttal-eval-20261123/logs")
    log_root.mkdir(parents=True, exist_ok=True)
    log_path = log_root / f"{bundle_id}-cjm1-training-{sys.argv[1]}.log"
    env = dict(os.environ)
    env.update(
        BUNDLE_ID=bundle_id,
        PYTHONUNBUFFERED="1",
        PYTHONNOUSERSITE="1",
        PIP_NO_CACHE_DIR="1",
        TOKENIZERS_PARALLELISM="false",
        OMP_NUM_THREADS="8",
        HF_HOME="/tmp/hf",
        WANDB_MODE="disabled",
        PYTHONPATH="src:.",
    )

    def run_logged(command):
        with log_path.open("a") as log:
            process = subprocess.Popen(
                command, cwd=source, env=env, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, bufsize=1,
            )
            for line in process.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                log.write(line)
            return process.wait()

    runtime = (
        "import json,shutil,torch; "
        "print('CJM1_RUNTIME_INFO='+json.dumps({'torch':torch.__version__,"
        "'cuda':torch.version.cuda,'gpu':torch.cuda.get_device_name() "
        "if torch.cuda.is_available() else None,"
        "'free_gib':{p:round(shutil.disk_usage(p).free/1024**3,1) "
        "for p in ('/tmp','/home/jovyan','/workspace-SR006.nfs2',"
        "'/workspace-SR006.nfs3')}}),flush=True)"
    )
    run_logged([sys.executable, "-c", runtime])

    venv = Path("/tmp/eval-venv-cjm1")
    if run_logged([sys.executable, "-m", "venv", "--system-site-packages", str(venv)]) != 0:
        print("CJM1_VENV_SETUP_FAILED", flush=True)
        raise SystemExit(0)
    python = str(venv / "bin/python")
    pins = [
        "ai2-olmo-eval==0.8.5", "tiktoken==0.12.0", "wandb==0.25.1",
        "loguru==0.7.3", "schedulefree==1.4.1", "opt_einsum==3.4.0",
    ]
    if run_logged([
        python, "-m", "pip", "install", "--disable-pip-version-check",
        "--no-cache-dir", "--only-binary=:all:", *pins,
    ]) != 0:
        print("CJM1_DEPS_INSTALL_FAILED", flush=True)
        raise SystemExit(0)
    check = run_logged([
        python, "-c", "import olmo_eval,tiktoken,wandb,loguru,schedulefree,opt_einsum",
    ])
    if check != 0:
        print("CJM1_DEPS_INSTALL_FAILED", flush=True)
        raise SystemExit(0)
    print("CJM1_DEPS_OK", flush=True)

    code = run_logged([python, "tools/train_cjm1.py", *sys.argv[1:]])
    marker = f"CJM1_TRAINING_EXIT={code}"
    print(marker, flush=True)
    with log_path.open("a") as log:
        log.write(marker + "\n")
    # Match run.sh: preserve a completed platform job plus explicit exit marker.
    raise SystemExit(0)
