"""Read and verify a sealed, immutable job payload."""
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


def sha(b): return hashlib.sha256(b).hexdigest()


def main():
    started=time.monotonic()
    assert len(sys.argv)>=2 and sys.argv[1] in ('validate','storage','smoke','bench')
    mode=sys.argv[1]
    offline=os.environ.pop('EP2_LOCAL_VALIDATE','')=='1'
    assert not offline or mode=='validate'
    os.umask(0o077)
    key=os.environ.pop('BUNDLE_KEY')
    if os.environ.get('OMPI_COMM_WORLD_RANK','0')!='0':
        print('EP2_MPI_NONZERO_IDLE',flush=True)
        return
    for p in ('PYTHONPATH','PYTHONUSERBASE','PYTHONOPTIMIZE'):
        os.environ.pop(p,None)
    os.environ.update(PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1')
    p=Path(__file__).resolve().parent
    public=json.loads((p/'manifest.json').read_text())
    enc=(p/'payload.fernet').read_bytes()
    assert sha(enc)==public['payload_sha256']
    tmp=os.statvfs('/tmp')
    assert offline or (tmp.f_bavail*tmp.f_frsize>=20*(1<<30) and tmp.f_favail>=100000)
    with tempfile.TemporaryDirectory(prefix='sealed-ep2-',dir='/tmp') as work:
        d=Path(work)
        if not offline:
            from importlib.util import find_spec
            if find_spec('cryptography') is None:
                deps=d/'deps'
                subprocess.run([sys.executable,'-m','pip','install','--no-cache-dir','--only-binary=:all:',
                    '--disable-pip-version-check','--target',str(deps),'cryptography==46.0.5'],check=True,timeout=65,
                    env=dict(os.environ,TMPDIR=work,XDG_CACHE_HOME=work))
                sys.path.insert(0,str(deps))
        from cryptography.fernet import Fernet
        raw=Fernet(key.encode()).decrypt(enc)
        del key
        assert sha(raw)==public['plaintext_sha256']
        target=d/'app';target.mkdir()
        members={}
        with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as tf:
            for m in tf:
                rel=PurePosixPath(m.name)
                assert m.isfile() and not rel.is_absolute() and '..' not in rel.parts and m.name==str(rel) and m.name not in members
                assert m.size <= 64<<20
                contents=tf.extractfile(m).read()
                members[m.name]=sha(contents)
                path=target.joinpath(*rel.parts);path.parent.mkdir(parents=True,exist_ok=True)
                with path.open('xb') as out: out.write(contents)
        manifest=json.loads((target/'bundle_manifest.json').read_text())
        assert public['bundle_id']==sha((target/'bundle_manifest.json').read_bytes())[:20]
        del members['bundle_manifest.json']
        assert members==manifest['files'] and manifest['entry']=='entry.py'
        env=dict(os.environ,EP2_BUNDLE_ID=public['bundle_id'],EP2_BOOT_MONOTONIC=str(started))
        print('EP2_BUNDLE_AUTHENTICATED '+public['bundle_id'],flush=True)
        budget={'validate':120,'storage':120,'smoke':900,'bench':3600}[mode]
        subprocess.run([sys.executable,'-B',manifest['entry'],*sys.argv[1:]],cwd=target,env=env,check=True,
                       timeout=max(1,budget-(time.monotonic()-started)))


if __name__=='__main__':
    if not sys.flags.optimize:
        try:
            main()
        except Exception:
            traceback.print_exc()
            print('EP2_JOB_FAIL mode='+str(sys.argv[1:2]),flush=True)
            # The platform hides logs for failed containers: immutable success evidence is mandatory.
            if os.getenv('EP2_LOCAL_VERIFY_STRICT')=='1': sys.exit(1)
    else:
        raise SystemExit('EP2 requires Python assertions')
