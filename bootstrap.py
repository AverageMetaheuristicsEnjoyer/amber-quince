import json, os, subprocess, sys, tempfile, traceback, zlib
from pathlib import Path
from cryptography.fernet import Fernet

def run():
    if int(os.environ.get("OMPI_COMM_WORLD_RANK","0")) != 0: return
    key = os.environ.pop("BUNDLE_KEY").encode()
    files = json.loads(zlib.decompress(Fernet(key).decrypt(Path(__file__).with_name("payload.bin").read_bytes())))
    with tempfile.TemporaryDirectory(dir="/tmp") as name:
        dest=Path(name)
        for rel, data in files.items():
            path=dest/rel
            if not path.resolve().is_relative_to(dest): raise ValueError("bad path")
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(data)
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TORCHINDUCTOR_CACHE_DIR=name+"/inductor", TRITON_CACHE_DIR=name+"/triton", XDG_CACHE_HOME=name+"/cache", TMPDIR=name)
        deps=dest/"deps"
        for mod, pkg in [("tiktoken","tiktoken==0.8.0"),("transformers","transformers==4.53.3")]:
            if subprocess.run([sys.executable,"-c","import "+mod],env=env,cwd=dest).returncode:
                subprocess.run([sys.executable,"-m","pip","install","--no-cache-dir","--target",str(deps),pkg],env=env,cwd=dest,check=True)
                env["PYTHONPATH"]=str(deps)+os.pathsep+env.get("PYTHONPATH","")
        subprocess.run([sys.executable,"-u","bench.py"],cwd=dest,env=env,check=True)
try: run()
except Exception:
    traceback.print_exc()
    print("BENCHMARK_FAILED",flush=True)
