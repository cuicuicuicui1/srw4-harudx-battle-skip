"""Apply one of the four checked-in BPS files with SHA-256 and no-overwrite guards."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.bps import apply

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('patch', type=Path)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    output = args.output.resolve()
    patch = args.patch.resolve(strict=True)
    if output == source or output.exists() or not output.parent.is_dir():
        parser.error('output must be a new distinct file in an existing directory')
    manifest = json.loads((ROOT / 'patches/manifest.json').read_text('utf8'))
    blob = patch.read_bytes()
    sha = lambda data: hashlib.sha256(data).hexdigest()
    row = next((x for x in manifest['patches'] + manifest['full_localization_patches']
                if x['patch_sha256'] == sha(blob)), None)
    if row is None:
        parser.error('patch is not one of the documented release artifacts')
    raw = source.read_bytes()
    if sha(raw) != row['source_sha256']:
        parser.error('source SHA-256 differs from the documented patch base')
    target = apply(blob, raw)
    if sha(target) != row['target_sha256']:
        parser.error('result SHA-256 differs from the expected target')
    with output.open('xb') as stream:
        stream.write(target)
    print(json.dumps(dict(status='exact_release_match', source_sha256=sha(raw),
                          target_sha256=sha(target), output=str(output)), indent=2))

if __name__ == '__main__':
    main()
