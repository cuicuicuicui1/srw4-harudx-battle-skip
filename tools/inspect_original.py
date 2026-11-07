"""Index original HaruDX graphics and known text pointers; optionally extract locally."""
from pathlib import Path
from collections import Counter
import argparse
import csv
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_lz import decode, NativeLZError

JP_SHA = '5cea22b5995e91e7e19c9ff73a2036f1929e5f162ea56d0819628728ec3d50d0'
H = lambda data: hashlib.sha256(data).hexdigest()

def read(rom, cpu, count=1):
    start = cpu & 0x3fffff
    if start + count > len(rom):
        raise ValueError('ROM read exceeds end')
    return int.from_bytes(rom[start:start + count], 'little')

def normalize(rom, cpu):
    seen = set()
    while read(rom, cpu, 2) == 0x07fc:
        if cpu in seen:
            raise ValueError('FC07 pointer cycle')
        seen.add(cpu)
        cpu = (cpu & 0xff0000) | read(rom, cpu + 2, 2)
    return cpu

def resolve(rom, site, index, branches):
    table = read(rom, site, 3)
    cpu = (table & 0xff0000) | read(rom, table + 2 * index, 2)
    for branch in branches:
        cpu = normalize(rom, cpu)
        head = cpu + 2 if read(rom, cpu, 2) in (0x01fc, 0x0efc) else cpu
        if read(rom, head) == 0xfa:
            count = read(rom, head + 1)
        elif read(rom, head, 2) in (0x08fc, 0x09fc):
            count = 8
        else:
            raise ValueError('catalog path is not a native selector')
        if not 0 <= branch < count <= 8:
            raise ValueError('selector branch out of range')
        cpu = (head & 0xff0000) | read(rom, head + 2 + 2 * branch, 2)
    return normalize(rom, cpu)

def text_span(rom, cpu):
    start = cpu & 0x3fffff
    pos = start
    controls = Counter()
    for _ in range(4096):
        if pos >= len(rom) or pos >> 16 != start >> 16:
            raise ValueError('native text crosses bank without supported control')
        value = rom[pos]
        n = 3 if value in (0xfe, 0xfb) else 2 if value in (0xf8, 0xf9, 0xfa, 0xfc, 0xfd) or 0xf0 <= value <= 0xf5 else 1
        if pos + n > len(rom):
            raise ValueError('truncated native text token')
        if value >= 0xf6:
            controls[f'{value:02X}'] += 1
        pos += n
        if value == 0xff:
            return rom[start:pos], dict(controls)
    raise ValueError('native text has no bounded FF terminator')

def inspect(rom, out, extract=False):
    if len(rom) != 0x400000 or H(rom) != JP_SHA:
        raise ValueError('requires the exact unheadered HaruDX v05_09 Japanese ROM')
    out = Path(out)
    out.mkdir(exist_ok=False, parents=True)
    if extract:
        (out / 'graphics').mkdir()
        (out / 'encoded-text').mkdir()
    graphics = []
    for gfx in range(330):
        site = 0x160000 + gfx * 3
        pointer = read(rom, site, 3)
        start = pointer & 0x3fffff
        if not start:
            graphics.append(dict(gfx_id=gfx, pointer_site_file=f'{site:06X}', status='null_pointer'))
            continue
        data = decode(rom, start, max_output=0x10000, history=bytes(8192))
        depends_on_history = False
        try:
            decode(rom, start, max_output=0x10000, history=None)
        except NativeLZError as error:
            if 'reference before decoded image' not in str(error):
                raise
            depends_on_history = True
        compressed = rom[start:data['end']]
        graphics.append(dict(gfx_id=gfx, pointer_site_file=f'{site:06X}', source_cpu=f'{pointer:06X}',
                             source_file=f'{start:06X}', end_file_exclusive=f'{data["end"]:06X}',
                             source_bytes=len(compressed), output_bytes=len(data['output']),
                             compressed_sha256=H(compressed), output_zero_history_sha256=H(data['output']),
                             requires_preexisting_history=depends_on_history, status='decoded'))
        if extract:
            (out / 'graphics' / f'{gfx:03d}.compressed.bin').write_bytes(compressed)
            (out / 'graphics' / f'{gfx:03d}.zero-history.bin').write_bytes(data['output'])
    text = []
    with (ROOT / 'original/indexed-text-seeds.tsv').open(encoding='utf8', newline='') as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            item = dict(row)
            try:
                branches = [int(x) for x in row['branch'].split('.') if x]
                cpu = resolve(rom, int(row['site_file'], 16), int(row['index']), branches)
                raw, controls = text_span(rom, cpu)
                item.update(cpu=f'{cpu:06X}', start_file=f'{cpu & 0x3fffff:06X}',
                            end_file_exclusive=f'{(cpu & 0x3fffff) + len(raw):06X}',
                            source_bytes=len(raw), encoded_sha256=H(raw), controls=controls, status='indexed')
                if extract:
                    safe_id = row['id'].replace(':', '_')
                    (out / 'encoded-text' / (safe_id + '.bin')).write_bytes(raw)
            except ValueError as error:
                item.update(status='unresolved', reason=str(error))
            text.append(item)
    summary = dict(source_sha256=JP_SHA, source_size=len(rom), graphics_table_slots=330,
                   graphics_nonnull=sum(x['status'] == 'decoded' for x in graphics),
                   text_catalog_rows=len(text), text_indexed=sum(x['status'] == 'indexed' for x in text),
                   text_unresolved=sum(x['status'] != 'indexed' for x in text), raw_extraction_requested=extract,
                   scope='Known native graphics table and inherited indexed text catalog; not whole-ROM unpacking or all live script references.',
                   history_note='Decompressed hashes/files assume zero-filled previous8192 bytes; history-dependent streams are labeled, not proven context-independent.',
                   text_note='FF-token span metadata, not proof of reachability, displayed dialogue, glyph identity or complete branch grammar.')
    for name, data in [('graphics-index.json', graphics), ('text-index.json', text), ('summary.json', summary)]:
        (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', 'utf8')
    return summary

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--extract', action='store_true', help='also write encoded text and graphics .bin locally; never upload them')
    args = parser.parse_args()
    print(json.dumps(inspect(args.source.read_bytes(), args.output, args.extract), indent=2))

if __name__ == '__main__':
    main()
