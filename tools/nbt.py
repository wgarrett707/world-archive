"""Minimal NBT reader (Java = big-endian, Bedrock = little-endian)."""
import gzip, struct, zlib, io

class NBTReader:
    def __init__(self, data, little=False):
        self.b = data
        self.p = 0
        self.e = '<' if little else '>'

    def _u(self, fmt, n):
        v = struct.unpack_from(self.e + fmt, self.b, self.p)[0]
        self.p += n
        return v

    def string(self):
        n = self._u('H', 2)
        s = self.b[self.p:self.p + n].decode('utf-8', 'replace')
        self.p += n
        return s

    def payload(self, t):
        if t == 1: return self._u('b', 1)
        if t == 2: return self._u('h', 2)
        if t == 3: return self._u('i', 4)
        if t == 4: return self._u('q', 8)
        if t == 5: return self._u('f', 4)
        if t == 6: return self._u('d', 8)
        if t == 7:
            n = self._u('i', 4); v = self.b[self.p:self.p + n]; self.p += n; return v
        if t == 8: return self.string()
        if t == 9:
            et = self._u('b', 1); n = self._u('i', 4)
            return [self.payload(et) for _ in range(n)]
        if t == 10:
            d = {}
            while True:
                tt = self._u('b', 1)
                if tt == 0: return d
                name = self.string()
                d[name] = self.payload(tt)
        if t == 11:
            n = self._u('i', 4)
            v = struct.unpack_from(self.e + f'{n}i', self.b, self.p); self.p += 4 * n; return list(v)
        if t == 12:
            n = self._u('i', 4)
            v = struct.unpack_from(self.e + f'{n}q', self.b, self.p); self.p += 8 * n; return list(v)
        raise ValueError(f'bad tag {t} at {self.p}')

    def root(self):
        t = self._u('b', 1)
        if t == 0:
            return None
        self.string()
        return self.payload(t)


def load(data, little=False):
    if data[:2] == b'\x1f\x8b':
        data = gzip.decompress(data)
    elif data[:1] == b'\x78':
        data = zlib.decompress(data)
    return NBTReader(data, little).root()


def load_all(data, little=True):
    """Read consecutive root compounds (Bedrock block entities)."""
    r = NBTReader(data, little)
    out = []
    while r.p < len(r.b):
        out.append(r.root())
    return out


def load_file(path, little=False):
    with open(path, 'rb') as f:
        return load(f.read(), little)
