"""Generic authenticated job carrier."""
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


def main():
    os.umask(0o077)
    boot = time.monotonic()
    key = os.environ.pop('BUNDLE_KEY')
    if os.environ.get('OMPI_COMM_WORLD_RANK','0') != '0':
        print('CARRIER_NONZERO_IDLE', flush=True)
        return
    os.environ.pop('PYTHONUSERBASE',None)
    os.environ.pop('PYTHONPATH',None)
    os.environ.update(PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1')
    root = Path(__file__).resolve().parent
    m = json.loads((root/'manifest.json').read_text())
    enc = (root/'payload.fernet').read_bytes()
    if hashlib.sha256(enc).hexdigest() != m['payload_sha256']:
        raise RuntimeError('payload hash mismatch')
    tmp = os.statvfs('/tmp')
    if tmp.f_bavail*tmp.f_frsize < 20<<30 or tmp.f_favail < 100000:
        raise RuntimeError('node scratch not admitted')
    with tempfile.TemporaryDirectory(prefix='sealed-task-',dir='/tmp') as td:
        scratch=Path(td)
        deps=scratch/'deps'
        if os.environ.pop('CARRIER_LOCAL_VERIFY','') != '1':
            pip_env = dict(os.environ, TMPDIR=td, XDG_CACHE_HOME=td, PIP_NO_CACHE_DIR='1')
            subprocess.run([sys.executable,'-m','pip','install','--no-cache-dir','--only-binary=:all:','--disable-pip-version-check','--target',str(deps),'cryptography==46.0.5'],env=pip_env,check=True,timeout=120)
            sys.path.insert(0,str(deps))
        from cryptography.fernet import Fernet
        data=Fernet(key.encode()).decrypt(enc)
        del key
        if hashlib.sha256(data).hexdigest()!=m['source_sha256']:
            raise RuntimeError('plaintext hash mismatch')
        target=scratch/'app'
        target.mkdir()
        seen=set()
        with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as tar:
            for item in tar:
                rel=PurePosixPath(item.name)
                if not item.isfile() or rel.is_absolute() or '..' in rel.parts or item.name in seen:
                    raise RuntimeError('unsafe payload member')
                seen.add(item.name)
                p=target.joinpath(*rel.parts)
                p.parent.mkdir(parents=True,exist_ok=True)
                with p.open('xb') as f:
                    f.write(tar.extractfile(item).read())
        inner=json.loads((target/'bundle_manifest.json').read_text())
        if inner['bundle_id'] != m['bundle_id'] or inner['entry'] != ['src/entry.py']:
            raise RuntimeError('authenticated entry mismatch')
        print('BUNDLE_AUTHENTICATED='+m['bundle_id'],flush=True)
        env=dict(os.environ,BUNDLE_ID=m['bundle_id'],CROSS_BOOT_MONOTONIC=str(boot))
        return subprocess.call([sys.executable,*inner['entry'],*sys.argv[1:]],cwd=target,env=env,timeout=6600)


if __name__=='__main__':
    raise SystemExit(main())
