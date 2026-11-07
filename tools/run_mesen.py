"""Run the declared historical ordinary-SRAM battle route in an isolated directory."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apply_x_skip import PAIRS

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emulator', type=Path, required=True)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--sram', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--x', action='store_true', help='use held-X input route')
    args = parser.parse_args()
    raw, save = args.rom.read_bytes(), args.sram.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    known = set(PAIRS) | {row['target_sha256'] for row in PAIRS.values()}
    if len(raw) != 0x400000 or sha not in known:
        parser.error('only the documented exact ROM identities are supported')
    if len(save) != 8192 or hashlib.sha256(save).hexdigest() != '5949394e7e70097649207f5d539a77a15506d294b1aa44ef64d26c1a6c570e09':
        parser.error('this historical route requires the documented SRAM identity; adapt a new route for a different save')
    emulator = args.emulator.resolve(strict=True)
    directory = args.output.resolve()
    if directory.exists():
        parser.error('output must be a new isolated directory')
    directory.mkdir(parents=True)
    (directory / 'isolated.smc').write_bytes(raw)
    (directory / 'seed.srm').write_bytes(save)
    route_name = 'route-x-held.json' if args.x else 'route-no-x.json'
    route = json.loads((ROOT / 'testing/mesen' / route_name).read_text('utf8'))
    fixture = json.loads((ROOT / 'testing/mesen/declared-battle-fixture.json').read_text('utf8'))
    events = re.findall(r'(\d+)-(\d+):(\w+)', route['input'])
    lua_events = ','.join('{' + f'{a},{b},"{key}"' + '}' for a, b, key in events)
    writes = ','.join('{address=' + str(w['address']) + ',bytes={' +
                      ','.join(map(str, bytes.fromhex(w['bytes']))) + '}}' for w in fixture['writes'])
    settings = '{frames=' + str(route['frames']) + ',events={' + lua_events + '},shots={' + \
        ','.join('[' + str(frame) + ']=true' for frame in route['shots']) + '},writes={' + writes + '}}'
    (directory / 'route.lua').write_text(settings, 'utf8')
    env = {k: v for k, v in os.environ.items() if not k.startswith(('PROBE_', 'TRACE_', 'CAPTURE_'))}
    env.update(PROBE_OUT=str(directory), PROBE_ROUTE=str(directory / 'route.lua'),
               PROBE_SRAM=str(directory / 'seed.srm'), PROBE_RESET=str(int.from_bytes(raw[0xfffc:0xfffe], 'little')))
    cmd = [str(emulator), '--testRunner', str(ROOT / 'testing/mesen/trace_battle.lua'),
           str(directory / 'isolated.smc'), '--doNotSaveSettings', '--timeout=600', '--enableStdout']
    start = time.time()
    with (directory / 'stdout.log').open('w', encoding='utf8') as output:
        result = subprocess.run(cmd, cwd=directory, env=env, stdout=output, stderr=subprocess.STDOUT,
                                timeout=660, creationflags=0x08000000 if os.name == 'nt' else 0)
    trace = (directory / 'trace.log').read_text('utf8') if (directory / 'trace.log').exists() else ''
    expect_skip = args.x and sha in {row['target_sha256'] for row in PAIRS.values()}
    passed = result.returncode == 0 and 'RETURNED_TO_MAP' in trace and 'DONE' in trace and \
        ('X_NATIVE_SKIP' in trace) == expect_skip
    report = dict(status='listed_route_passed' if passed else 'failed_or_entry_not_reached',
                  returncode=result.returncode, rom_sha256=sha, input_x=args.x, expected_skip=expect_skip,
                  source_save_sha256=hashlib.sha256(save).hexdigest(),
                  emulator_sha256=hashlib.sha256(emulator.read_bytes()).hexdigest(),
                  seconds=time.time() - start, route=route, declared_fixture=fixture,
                  scope='Cold ordinary save; declared unit/position/HP fixture; native UI; map-return and skip marker only. Compare persistent RAM and save lifecycle separately.')
    (directory / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not passed:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
