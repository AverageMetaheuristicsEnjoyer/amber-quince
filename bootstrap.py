"""Authenticated single-use envelope. No downloads or persistent writes."""
import hashlib, hmac, json, os, re, subprocess, sys, tempfile, zlib
from pathlib import Path


def crypt(raw, key, decrypt=False):
    # Random per-envelope encryption and MAC keys; never reuse for another message.
    return subprocess.run(['openssl','enc','-aes-256-cbc','-nosalt','-pbkdf2','-iter','100000','-md','sha256','-pass','env:E']+(['-d'] if decrypt else []),env={'PATH':os.environ['PATH'],'E':key[:32].hex()},input=raw,capture_output=True,check=True).stdout


def main():
    os.umask(0o077)
    if sys.argv[1:] not in ([], ['test']): raise SystemExit('invalid mode')
    key=bytes.fromhex(os.environ.pop('BUNDLE_KEY'))
    blob=Path(__file__).with_name('payload.bin').read_bytes()
    if len(key)!=64 or not hmac.compare_digest(blob[:32],hmac.digest(key[32:],blob[32:],'sha256')): raise SystemExit('authentication failed')
    pkg=json.loads(zlib.decompress(crypt(blob[32:],key,True))); del key
    with tempfile.TemporaryDirectory(dir='/tmp') as d:
        for name, data in pkg['files'].items():
            if not re.fullmatch(r'[a-z0-9_]+\.py',name): raise SystemExit('invalid member')
            (Path(d)/name).write_text(data,encoding='utf-8')
        env=dict(os.environ, TMPDIR=d)
        return subprocess.call([sys.executable,'-E','-B',pkg['entries'][bool(sys.argv[1:])]],cwd=d,env=env)

if __name__=='__main__': raise SystemExit(main())
