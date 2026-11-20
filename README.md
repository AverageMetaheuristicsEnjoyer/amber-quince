# Source snapshot

The archive requires a Fernet key shared separately. With Python 3.12+ and the `cryptography` package installed, extract it into a new directory.

```bash
python unpack.py /path/to/key ./source
```

The source commit is recorded in `manifest.json`.
