"""Exact-source, no-overwrite HaruDX opening-X battle skip patcher.

Python 3 standard library only. Does not bundle ROMs or player saves.
Supported pairs: frozen R29 -> original R30, frozen R45 standard -> R45 X.
"""
from pathlib import Path
import argparse
import hashlib
import json
from native_lz import decode

HOOK = 0x039204
CODE_START = 0x3B78AA
OWNED_END = 0x3B78E4
GRAPHICS_POINTER_BASE = 0x160000
GFX329_SOURCE = 0x3B6DC0
GFX329_OUTPUT_SHA256 = '31fcca8fb858bc902bd08fb2cc0944c1129e4656284748b827650a69e50a1940'
PAIRS = {
    '897c76f1dc45573ea1313a8098c2b6dc4b3e27300bc2b622657905e48d3ef6db': {
        'name': 'R29 -> R30 X',
        'target_sha256': '25c358d334156f600ffda2bb2b190c6512ab444e847c86e4dfcb7795a4cd2938',
    },
    '8105ce9fced0519d733de4499e7ccacb72c5c951b02fae6c0bf78001f1b738bb': {
        'name': 'R45 standard -> R45 X',
        'target_sha256': '82f2825c3ca462ac898a705bfbd9059d3c4f68340296fc4be127bb4a90374611',
    },
}

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def machine_code():
    """Small label-aware emitter; no external assembler dependency."""
    data = bytearray()
    labels = {}
    refs = []
    def emit(value):
        data.extend(bytes.fromhex(value))
    def branch(op, label):
        data.extend((op, 0))
        refs.append((len(data) - 1, label))
    emit('C2 30')                     # REP #$30: replay original width setup
    emit('A5 92 C9 A7 3D')            # LDA $92 / CMP #$3DA7
    branch(0xD0, 'original')
    emit('A5 93 C9 3D CB')            # LDA $93 / CMP #$CB3D
    branch(0xD0, 'original')
    emit('AD EC 03 0D F0 03 89 40 00') # LDA $03EC / ORA $03F0 / BIT #$0040
    branch(0xD0, 'skip')
    emit('A5 AB 29 FF 00 C9 1E 00')   # LDA $AB / AND #$00FF / CMP #30
    branch(0xB0, 'original')
    emit('E2 20 E6 AB DC FB F5')       # SEP #$20 / INC $AB / JML [$F5FB]
    labels['skip'] = len(data)
    emit('A9 C0 3D 85 92 DC F8 F5')    # LDA #$3DC0 / STA $92 / JML [$F5F8]
    labels['original'] = len(data)
    emit('A5 AC 5C 08 92 83')          # LDA $AC / JML $839208
    for at, label in refs:
        distance = labels[label] - at - 1
        if not -128 <= distance <= 127:
            raise ValueError('branch outside signed-byte range')
        data[at] = distance & 255
    if len(data) != 58 or CODE_START + len(data) != OWNED_END:
        raise ValueError('code reservation changed')
    return bytes(data)

def patch_bytes(source):
    """Build in memory; return only after exact target identity is proven."""
    if len(source) != 0x400000:
        raise ValueError('requires an exact 4 MiB unheadered ROM')
    source_sha = sha256(source)
    if source_sha not in PAIRS:
        raise ValueError('unsupported source SHA-256 (or already patched): ' + source_sha)
    checks = {
        HOOK: bytes.fromhex('C2 30 A5 AC'),
        0x0B3DA4: bytes.fromhex('57 01 80 F5 3D'),
        0x0B3DC0: bytes.fromhex('68 1D 60 FB FF 68 16 68 13 03'),
        0x00F5F8: bytes.fromhex('43 F6 80'),
        0x00F5FB: bytes.fromhex('4E F6 80'),
        CODE_START: bytes(OWNED_END - CODE_START),
    }
    for start, expected in checks.items():
        if source[start:start + len(expected)] != expected:
            raise ValueError(f'consumer/ownership bytes differ at {start:06X}')
    # This slot is a documented R22 reservation tail after relocated R23 gfx329.
    # Zero bytes are checked only after ownership and resource identity are fixed.
    resource = decode(source, GFX329_SOURCE, max_output=0x10000, history=bytes(8192))
    if resource['end'] != CODE_START or sha256(resource['output']) != GFX329_OUTPUT_SHA256:
        raise ValueError('gfx329 no longer ends before the owned code slot')
    code = machine_code()
    result = bytearray(source)
    result[HOOK:HOOK + 4] = bytes.fromhex('5C AA 78 FB')
    result[CODE_START:OWNED_END] = code
    result[0xFFDC:0xFFE0] = bytes.fromhex('FF FF 00 00')
    checksum = sum(result) & 65535
    result[0xFFDC:0xFFE0] = (checksum ^ 65535).to_bytes(2, 'little') + checksum.to_bytes(2, 'little')
    if sum(result) & 65535 != checksum:
        raise ValueError('checksum failed')
    streams = 0
    for gfx in range(330):
        ptr = GRAPHICS_POINTER_BASE + gfx * 3
        start = int.from_bytes(source[ptr:ptr + 3], 'little') & 0x3FFFFF
        if not start:
            continue
        before = decode(source, start, max_output=0x10000, history=bytes(8192))
        after = decode(result, start, max_output=0x10000, history=bytes(8192))
        if before['end'] != after['end'] or before['output'] != after['output']:
            raise ValueError(f'graphics stream {gfx} changed')
        streams += 1
    target_sha = sha256(result)
    if target_sha != PAIRS[source_sha]['target_sha256']:
        raise ValueError('result differs from the accepted release')
    differences = [i for i, (a, b) in enumerate(zip(source, result)) if a != b]
    for i in differences:
        if not (0xFFDC <= i < 0xFFE0 or HOOK <= i < HOOK + 4 or CODE_START <= i < OWNED_END):
            raise ValueError('unexpected changed byte')
    return bytes(result), {
        'pair': PAIRS[source_sha]['name'],
        'source_sha256': source_sha,
        'target_sha256': target_sha,
        'size': len(result),
        'code_bytes': len(code),
        'changed_bytes': len(differences),
        'graphics_streams_checked': streams,
        'status': 'exact_release_match',
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true', help='build and validate in memory; do not write a ROM')
    mode.add_argument('--output', type=Path, help='new output file; existing files are never overwritten')
    args = parser.parse_args()
    source_path = args.source.resolve(strict=True)
    if args.output is not None:
        output = args.output.resolve()
        if output == source_path or output.exists():
            parser.error('output must be a new, distinct file')
        if not output.parent.is_dir():
            parser.error('output parent must already exist')
    try:
        target, report = patch_bytes(source_path.read_bytes())
    except ValueError as error:
        parser.error(str(error))
    if args.output is not None:
        with output.open('xb') as stream:
            stream.write(target)
        report['output'] = str(output)
    else:
        report['output'] = None
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
