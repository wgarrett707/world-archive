"""Pure-Python read-only LevelDB reader for Minecraft Bedrock worlds (inside a .mcworld zip
or a world folder). Supports Mojang's zlib (2) and raw-deflate (4) block compression."""
import os, struct, zlib, zipfile


def _varint(b, p):
    r = s = 0
    while True:
        c = b[p]; p += 1
        r |= (c & 0x7f) << s
        if c < 0x80:
            return r, p
        s += 7


def _decompress(raw, ctype):
    if ctype == 0:
        return raw
    if ctype == 2:
        return zlib.decompress(raw)
    if ctype == 4:
        return zlib.decompress(raw, -15)
    raise ValueError(f'unsupported compression {ctype}')


def _block_entries(data):
    nrest = struct.unpack_from('<I', data, len(data) - 4)[0]
    end = len(data) - 4 - 4 * nrest
    p = 0
    key = b''
    while p < end:
        shared, p = _varint(data, p)
        nonshared, p = _varint(data, p)
        vlen, p = _varint(data, p)
        key = key[:shared] + data[p:p + nonshared]
        p += nonshared
        yield key, data[p:p + vlen]
        p += vlen


def _read_block(buf, off, size):
    raw = buf[off:off + size]
    ctype = buf[off + size]
    return _decompress(raw, ctype)


def iter_table(buf):
    """Yield (user_key, seq, type, value) from an .ldb/.sst file's bytes."""
    footer = buf[-48:]
    p = 0
    _, p = _varint(footer, p); _, p = _varint(footer, p)  # metaindex handle
    ioff, p = _varint(footer, p); isize, p = _varint(footer, p)
    index = _read_block(buf, ioff, isize)
    for _, handle in _block_entries(index):
        off, q = _varint(handle, 0)
        size, q = _varint(handle, q)
        for ikey, val in _block_entries(_read_block(buf, off, size)):
            tag = struct.unpack_from('<Q', ikey, len(ikey) - 8)[0]
            yield ikey[:-8], tag >> 8, tag & 0xff, val


def iter_log(buf):
    """Yield (user_key, seq, type, value) from a .log write-ahead file."""
    records = []
    pending = b''
    p = 0
    BS = 32768
    while p + 7 <= len(buf):
        left = BS - (p % BS)
        if left < 7:
            p += left
            continue
        length = struct.unpack_from('<H', buf, p + 4)[0]
        rtype = buf[p + 6]
        payload = buf[p + 7:p + 7 + length]
        p += 7 + length
        if rtype == 0 and length == 0:
            continue
        if rtype == 1:
            records.append(payload)
        elif rtype == 2:
            pending = payload
        elif rtype == 3:
            pending += payload
        elif rtype == 4:
            records.append(pending + payload); pending = b''
    for rec in records:
        seq, count = struct.unpack_from('<QI', rec, 0)
        q = 12
        for i in range(count):
            t = rec[q]; q += 1
            kl, q = _varint(rec, q); key = rec[q:q + kl]; q += kl
            if t == 1:
                vl, q = _varint(rec, q); val = rec[q:q + vl]; q += vl
            else:
                val = None
            yield key, seq + i, t, val


class BedrockDB:
    """Opens the 'db' directory either from a .mcworld (zip) or a world folder."""

    def __init__(self, path):
        self.path = path
        if zipfile.is_zipfile(path):
            self.zip = zipfile.ZipFile(path)
            names = self.zip.namelist()
            prefix = ''
            for n in names:
                if n.endswith('level.dat'):
                    prefix = n[:-len('level.dat')]
                    break
            self.prefix = prefix
            self.files = [n for n in names if n.startswith(prefix + 'db/')]
        else:
            self.zip = None
            self.prefix = os.path.normpath(path) + os.sep
            d = os.path.join(path, 'db')
            self.files = [os.path.join(d, f) for f in os.listdir(d)]

    def read(self, name):
        if self.zip:
            return self.zip.read(self.prefix + name if not name.startswith(self.prefix) else name)
        return open(name if os.path.isabs(name) else self.prefix + name, 'rb').read()

    def iter_raw(self, key_filter=None):
        """Yield (key, seq, type, value) for every record in every table and log."""
        for f in sorted(self.files):
            low = f.lower()
            if low.endswith('.ldb') or low.endswith('.sst'):
                it = iter_table(self.read(f))
            elif low.endswith('.log'):
                it = iter_log(self.read(f))
            else:
                continue
            for rec in it:
                if key_filter is None or key_filter(rec[0]):
                    yield rec

    def latest(self, key_filter=None):
        """Dict of key -> value using the highest sequence number (deletions removed)."""
        best = {}
        for k, seq, t, v in self.iter_raw(key_filter):
            cur = best.get(k)
            if cur is None or seq > cur[0]:
                best[k] = (seq, t, v)
        return {k: v for k, (s, t, v) in best.items() if t == 1}
