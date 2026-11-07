"""Local ROM verification; prints hashes/results only, never writes ROMs."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apply_x_skip import patch_bytes
from tools.bps import apply
from tools.make_patch import build

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--expected-target', type=Path)
    args = parser.parse_args()
    source = args.source.read_bytes()
    target, report = patch_bytes(source)
    manifest = json.loads((ROOT / 'patches/manifest.json').read_text('utf8'))
    row = next(x for x in manifest['patches'] if x['source_sha256'] == report['source_sha256'])
    patch = (ROOT / 'patches' / row['file']).read_bytes()
    if hashlib.sha256(patch).hexdigest() != row['patch_sha256']:
        raise ValueError('patch fingerprint mismatch')
    rebuilt, _ = build(source)
    if patch != rebuilt or apply(patch, source) != target:
        raise ValueError('patch rebuild/replay mismatch')
    if args.expected_target is not None and args.expected_target.read_bytes() != target:
        raise ValueError('target differs byte-for-byte')
    report.update(patch_rebuild=True, patch_replay=True,
                  expected_target_compared=args.expected_target is not None)
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
