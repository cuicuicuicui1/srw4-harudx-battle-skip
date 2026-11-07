"""Small BPS1 writer and complete bounded reader, using only the standard library."""
import struct
import zlib

def _number(value):
    if value < 0:
        raise ValueError('negative BPS integer')
    out = bytearray()
    while True:
        part = value & 0x7f
        value >>= 7
        if not value:
            out.append(part | 0x80)
            return bytes(out)
        out.append(part)
        value -= 1

def encode(source, target, metadata=b''):
    """Use SourceRead and TargetRead only; deterministic, no matching heuristic."""
    if len(source) != len(target):
        raise ValueError('this writer expects equal-size source and target')
    patch = bytearray(b'BPS1' + _number(len(source)) + _number(len(target)) + _number(len(metadata)) + metadata)
    start = 0
    while start < len(target):
        equal = source[start] == target[start]
        end = start + 1
        while end < len(target) and (source[end] == target[end]) == equal:
            end += 1
        patch.extend(_number(((end - start - 1) << 2) | (0 if equal else 1)))
        if not equal:
            patch.extend(target[start:end])
        start = end
    patch.extend(struct.pack('<II', zlib.crc32(source), zlib.crc32(target)))
    patch.extend(struct.pack('<I', zlib.crc32(patch)))
    return bytes(patch)

def apply(patch, source, max_output=16 * 1024 * 1024):
    if len(patch) < 19 or patch[:4] != b'BPS1':
        raise ValueError('invalid BPS header')
    if zlib.crc32(patch[:-4]) != int.from_bytes(patch[-4:], 'little'):
        raise ValueError('patch CRC mismatch')
    limit = len(patch) - 12
    pos = 4
    def number():
        nonlocal pos
        value, shift = 0, 1
        for _ in range(10):
            if pos >= limit:
                raise ValueError('truncated BPS integer')
            byte = patch[pos]
            pos += 1
            value += (byte & 127) * shift
            if byte & 128:
                return value
            shift <<= 7
            value += shift
        raise ValueError('oversized BPS integer')
    source_size, target_size, meta_size = number(), number(), number()
    if source_size != len(source) or target_size > max_output:
        raise ValueError('source/output size mismatch')
    if zlib.crc32(source) != int.from_bytes(patch[-12:-8], 'little'):
        raise ValueError('source CRC mismatch')
    if pos + meta_size > limit:
        raise ValueError('truncated metadata')
    pos += meta_size
    out = bytearray()
    source_relative = target_relative = 0
    while len(out) < target_size:
        command = number()
        action, length = command & 3, (command >> 2) + 1
        if len(out) + length > target_size:
            raise ValueError('action exceeds output size')
        if action == 0:
            start = len(out)
            if start + length > len(source):
                raise ValueError('source read out of bounds')
            out.extend(source[start:start + length])
        elif action == 1:
            if pos + length > limit:
                raise ValueError('truncated target literal')
            out.extend(patch[pos:pos + length])
            pos += length
        else:
            encoded_offset = number()
            delta = -(encoded_offset >> 1) if encoded_offset & 1 else encoded_offset >> 1
            if action == 2:
                source_relative += delta
                if source_relative < 0 or source_relative + length > len(source):
                    raise ValueError('source copy out of bounds')
                out.extend(source[source_relative:source_relative + length])
                source_relative += length
            else:
                target_relative += delta
                for _ in range(length):
                    if not 0 <= target_relative < len(out):
                        raise ValueError('target copy before initialized output')
                    out.append(out[target_relative])
                    target_relative += 1
    if pos != limit:
        raise ValueError('unexpected action bytes')
    if zlib.crc32(out) != int.from_bytes(patch[-8:-4], 'little'):
        raise ValueError('target CRC mismatch')
    return bytes(out)
