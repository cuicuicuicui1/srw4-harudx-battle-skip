from pathlib import Path
import json
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apply_x_skip import machine_code, patch_bytes, CODE_START, OWNED_END, PAIRS
from native_lz import decode, NativeLZError
from tools.bps import encode, apply, _number
from tools.inspect_original import text_span, resolve

class NativeLZTests(unittest.TestCase):
    def test_literal_and_long_terminator(self):
        result = decode(bytes.fromhex('A0 41 00 00 00'), 0)
        self.assertEqual(result['output'], b'A')
        self.assertEqual(result['end'], 5)

    def test_short_backreference(self):
        result = decode(bytes.fromhex('82 41 FF 00 00 00'), 0)
        self.assertEqual(result['output'], b'AAA')

    def test_preexisting_history_is_explicit(self):
        stream = bytes.fromhex('04 FF 00 00 00')
        with self.assertRaises(NativeLZError):
            decode(stream, 0)
        self.assertEqual(decode(stream, 0, history=b'Z')['output'], b'ZZ')

    def test_source_and_output_limits(self):
        for data, options in [(b'', {}), (bytes.fromhex('A0 41 00'), {}),
                              (bytes.fromhex('A0 41 00 00 00'), {'max_output': 0}),
                              (bytes.fromhex('A0 41 00 00 00'), {'max_source': 2})]:
            with self.subTest(data=data, options=options), self.assertRaises(NativeLZError):
                decode(data, 0, **options)

class BpsTests(unittest.TestCase):
    def test_mixed_runs_and_metadata(self):
        source, target = b'abcd' * 50, b'abcd' * 40 + b'X' * 40
        patch = encode(source, target, b'public test')
        self.assertEqual(apply(patch, source), target)
        self.assertEqual(patch, encode(source, target, b'public test'))

    def test_empty_and_all_equal(self):
        for data in [b'', b'hello']:
            self.assertEqual(apply(encode(data, data), data), data)

    def test_reject_bad_source_crc_patch_and_truncation(self):
        patch = encode(b'abcd', b'aXYZ')
        for bad, source in [(patch, b'abce'), (patch[:-1], b'abcd'),
                            (patch[:6] + bytes([patch[6] ^ 1]) + patch[7:], b'abcd')]:
            with self.subTest(source=source, size=len(bad)), self.assertRaises(ValueError):
                apply(bad, source)

    def test_output_limit(self):
        with self.assertRaises(ValueError):
            apply(encode(b'AB', b'CD'), b'AB', max_output=1)

    def test_source_and_overlapping_target_copy_actions(self):
        source, target = b'abc', b'abcabcabc'
        # SourceCopy(3, offset+0), then overlapping TargetCopy(6, offset+0).
        patch = bytearray(b'BPS1' + _number(3) + _number(9) + _number(0))
        patch += _number((2 << 2) | 2) + _number(0)
        patch += _number((5 << 2) | 3) + _number(0)
        patch += struct.pack('<II', zlib.crc32(source), zlib.crc32(target))
        patch += struct.pack('<I', zlib.crc32(patch))
        self.assertEqual(apply(patch, source), target)

    def test_valid_crc_does_not_bypass_bounds(self):
        patch = bytearray(b'BPS1' + _number(0) + _number(1) + _number(0))
        patch += _number(3) + _number(0)  # TargetCopy before any output exists.
        patch += struct.pack('<II', zlib.crc32(b''), zlib.crc32(b'X'))
        patch += struct.pack('<I', zlib.crc32(patch))
        with self.assertRaises(ValueError):
            apply(patch, b'')

class InputGuardTests(unittest.TestCase):
    def test_unapproved_or_wrong_size_rom(self):
        for data in [b'', bytes(0x400000), bytes(0x400200)]:
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                patch_bytes(data)

    def test_cli_never_overwrites_input_or_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source, out = Path(directory) / 'source.smc', Path(directory) / 'out.smc'
            source.write_bytes(b'invalid, but must survive')
            out.write_bytes(b'preserve me')
            for dest in [source, out]:
                run = subprocess.run([sys.executable, str(ROOT / 'apply_x_skip.py'), str(source),
                                      '--output', str(dest)], capture_output=True)
                self.assertNotEqual(run.returncode, 0)
            self.assertEqual(source.read_bytes(), b'invalid, but must survive')
            self.assertEqual(out.read_bytes(), b'preserve me')

class CodeContractTests(unittest.TestCase):
    def test_frozen_instruction_bytes_and_branch_targets(self):
        code = machine_code()
        self.assertEqual(len(code), OWNED_END - CODE_START)
        self.assertEqual(code.hex(), 'c230a592c9a73dd02ba593c93dcbd024adec030df003894000d011a5ab29ff00c91e00b00fe220e6abdcfbf5a9c03d8592dcf8f5a5ac5c089283')
        for opcode_at, target in [(7, 52), (14, 52), (25, 44), (35, 52)]:
            distance = int.from_bytes(code[opcode_at + 1:opcode_at + 2], 'little', signed=True)
            self.assertEqual(opcode_at + 2 + distance, target)

    def test_checked_in_patch_source_target_contracts(self):
        manifest = json.loads((ROOT / 'patches/manifest.json').read_text('utf8'))
        self.assertEqual(len(manifest['patches']), 2)
        import hashlib
        for row in manifest['patches']:
            blob = (ROOT / 'patches' / row['file']).read_bytes()
            self.assertEqual(hashlib.sha256(blob).hexdigest(), row['patch_sha256'])
            self.assertEqual(PAIRS[row['source_sha256']]['target_sha256'], row['target_sha256'])

    def test_full_localization_patch_fingerprints(self):
        import hashlib
        manifest = json.loads((ROOT / 'patches/manifest.json').read_text('utf8'))
        self.assertEqual(len(manifest['full_localization_patches']), 2)
        for row in manifest['full_localization_patches']:
            blob = (ROOT / 'patches' / row['file']).read_bytes()
            self.assertEqual(hashlib.sha256(blob).hexdigest(), row['patch_sha256'])
            self.assertEqual(zlib.crc32(blob[:-4]), int.from_bytes(blob[-4:], 'little'))
            self.assertEqual(row['source_sha256'], '5cea22b5995e91e7e19c9ff73a2036f1929e5f162ea56d0819628728ec3d50d0')

class OriginalIndexTests(unittest.TestCase):
    def test_fe_fb_operands_are_not_ff_terminators(self):
        rom = bytes.fromhex('FE FF FF FB FF FF F6 FF')
        raw, controls = text_span(rom, 0xc00000)
        self.assertEqual(raw, rom)
        self.assertEqual(controls, {'FE': 1, 'FB': 1, 'F6': 1, 'FF': 1})

    def test_native_selector_following(self):
        rom = bytearray(96)
        rom[0:3] = bytes.fromhex('10 00 C0')
        rom[16:18] = bytes.fromhex('20 00')
        rom[32:38] = bytes.fromhex('FA 02 30 00 40 00')
        self.assertEqual(resolve(rom, 0, 0, [1]), 0xc00040)
        with self.assertRaises(ValueError):
            resolve(rom, 0, 0, [2])

class SourceHealthTests(unittest.TestCase):
    def test_all_public_python_sources_parse(self):
        import ast
        for directory in [ROOT, ROOT / 'tools', ROOT / 'tests']:
            for path in directory.glob('*.py'):
                with self.subTest(file=path.name):
                    ast.parse(path.read_text('utf8'), filename=path.name)

if __name__ == '__main__':
    unittest.main()
