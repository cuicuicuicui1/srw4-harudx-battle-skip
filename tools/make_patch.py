"""Rebuild the public X-only BPS from an exact, user-supplied base ROM."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apply_x_skip import patch_bytes
from tools.bps import encode, apply

METADATA = b'HaruDX opening SNES X battle skip; source-only project v1.0.0'

def build(source):
    target, report = patch_bytes(source)
    blob = encode(source, target, METADATA)
    if apply(blob, source) != target:
        raise ValueError('BPS replay differs from expected target')
    return blob, dict(report, patch_sha256=hashlib.sha256(blob).hexdigest(), patch_bytes=len(blob))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    src = args.source.resolve(strict=True)
    out = args.output.resolve()
    if src == out or out.exists() or not out.parent.is_dir():
        parser.error('output must be a new file in an existing directory')
    blob, report = build(src.read_bytes())
    with out.open('xb') as stream:
        stream.write(blob)
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
