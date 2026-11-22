"""Reader for Bedrock Edition worlds (.mcworld zip or world folder with a LevelDB 'db')."""
import datetime, struct
from collections import Counter
import numpy as np

import nbt
from leveldb import BedrockDB
from blocks import bedrock_variant

GAME_MODES = {0: 'Survival', 1: 'Creative', 2: 'Adventure', 3: 'Spectator'}
TAG_DATA2D, TAG_SUBCHUNK, TAG_BLOCKENT, TAG_ENTITY = 45, 47, 49, 50


def parse_chunk_key(k):
    """Return (cx, cz, dim, tag, subchunk_y) or None."""
    n = len(k)
    if n in (9, 10):
        cx, cz = struct.unpack_from('<ii', k, 0)
        return cx, cz, 0, k[8], (struct.unpack_from('b', k, 9)[0] if n == 10 else None)
    if n in (13, 14):
        cx, cz, dim = struct.unpack_from('<iii', k, 0)
        if dim not in (1, 2):
            return None
        return cx, cz, dim, k[12], (struct.unpack_from('b', k, 13)[0] if n == 14 else None)
    return None


class SubChunkDecoder:
    def __init__(self, palette):
        self.palette = palette
        self.cache = {}
        self.unsupported = Counter()

    def _global(self, entry):
        name = entry.get('name', 'unknown')
        states = entry.get('states') or {}
        key = (name, tuple(sorted((k, str(v)) for k, v in states.items())))
        g = self.cache.get(key)
        if g is None:
            n, v = bedrock_variant(name, states)
            g = self.palette.add(n, v)
            self.cache[key] = g
        return g

    def decode(self, data):
        """Return uint16 array shaped (16, 16, 16) indexed [x, z, y] of global palette ids, or None."""
        ver = data[0]
        if ver in (8, 9):
            nstor = data[1]
            p = 3 if ver == 9 else 2
        elif ver == 1:
            nstor, p = 1, 1
        else:
            self.unsupported[ver] += 1
            return None
        if nstor == 0:
            return None
        hdr = data[p]; p += 1
        bpb = hdr >> 1
        if bpb == 0:
            psize = struct.unpack_from('<i', data, p)[0]
            p += 4
            idx = np.zeros(4096, dtype=np.int64)
        else:
            bpw = 32 // bpb
            nwords = -(-4096 // bpw)
            words = np.frombuffer(data, dtype='<u4', count=nwords, offset=p)
            p += nwords * 4
            shifts = (np.arange(bpw, dtype=np.uint32) * bpb)
            idx = ((words[:, None] >> shifts[None, :]) & ((1 << bpb) - 1)).ravel()[:4096].astype(np.int64)
            psize = struct.unpack_from('<i', data, p)[0]
            p += 4
        r = nbt.NBTReader(data, little=True)
        r.p = p
        gl = np.empty(psize, dtype=np.uint16)
        for i in range(psize):
            gl[i] = self._global(r.root())
        idx = np.minimum(idx, psize - 1)
        return gl[idx].reshape(16, 16, 16)


def _text(v):
    return v if isinstance(v, str) else ''


class BedrockWorld:
    edition = 'Bedrock'

    def __init__(self, path, palette, player_names=None):
        self.path = path
        self.palette = palette
        self.db = BedrockDB(path)
        self.decoder = SubChunkDecoder(palette)
        self.player_names = player_names or {}
        raw = self.db.read(self.db.prefix + 'level.dat') if self.db.zip else open(self.db.prefix + 'level.dat', 'rb').read()
        self.level = nbt.NBTReader(raw[8:], little=True).root()
        try:
            self.level_name_txt = (self.db.zip.read(self.db.prefix + 'levelname.txt').decode('utf-8', 'replace')
                                   if self.db.zip else None)
        except KeyError:
            self.level_name_txt = None
        self._latest = None

    # ------------------------------------------------------------------ helpers
    def _winners(self):
        """key -> highest sequence number, for keys we care about."""
        if self._latest is None:
            best = {}
            for k, seq, t, v in self.db.iter_raw():
                cur = best.get(k)
                if cur is None or seq > cur[0]:
                    best[k] = (seq, t)
            self._latest = {k: s for k, (s, t) in best.items() if t == 1}
        return self._latest

    def iter_latest(self, want=None):
        latest = self._winners()
        for k, seq, t, v in self.db.iter_raw(want):
            if t == 1 and latest.get(k) == seq:
                yield k, v

    # ------------------------------------------------------------------ metadata
    def metadata(self):
        L = self.level
        players = []
        for k, v in self.iter_latest(lambda k: k.startswith(b'player_') or k == b'~local_player'):
            try:
                p = nbt.NBTReader(v, little=True).root()
            except Exception:
                continue
            uid = k.decode('latin1')
            inv = Counter()
            for it in p.get('Inventory', []):
                n = str(it.get('Name', '')).replace('minecraft:', '')
                if n:
                    inv[n] += it.get('Count', 1)
            players.append({
                'uuid': uid,
                'name': self.player_names.get(uid),
                'pos': [round(x) for x in p.get('Pos', [0, 0, 0])],
                'dimension': p.get('DimensionId', 0),
                'xp_level': p.get('PlayerLevel', 0),
                'game_mode': GAME_MODES.get(p.get('PlayerGameMode', 0), '?'),
                'inventory': inv.most_common(12),
            })
        ver = L.get('lastOpenedWithVersion') or []
        return {
            'edition': 'Bedrock',
            'level_name': L.get('LevelName') or self.level_name_txt,
            'version': '.'.join(str(x) for x in ver[:3]) if ver else '?',
            'game_mode': GAME_MODES.get(L.get('GameType', 0), '?'),
            'hardcore': False,
            'cheats': bool(L.get('commandsEnabled', 0)),
            'generator': {0: 'Old (limited)', 1: 'Infinite', 2: 'Flat'}.get(L.get('Generator'), '?'),
            'seed': L.get('RandomSeed'),
            'spawn': [L.get('SpawnX'), L.get('SpawnY'), L.get('SpawnZ')],
            'last_played': datetime.datetime.utcfromtimestamp(L.get('LastPlayed', 0)).isoformat() + 'Z',
            'world_ticks': L.get('currentTick', L.get('Time', 0)),
            'multiplayer': bool(L.get('MultiplayerGame', 0)),
            'players': players,
            'dimensions': [],
        }

    # ------------------------------------------------------------------ scanning
    def scan(self, progress=None):
        pal = self.palette
        chunk_top = {}
        chunk_built = Counter()
        chunk_parts = {}
        chunk_be = Counter()
        dims = Counter()
        counts = np.zeros(4096, dtype=np.int64)
        signs, containers, books, entities, named = [], [], [], Counter(), []

        def want(k):
            ck = parse_chunk_key(k)
            return ck is not None and ck[3] in (TAG_SUBCHUNK, TAG_BLOCKENT, TAG_ENTITY)

        n = 0
        built_arr = None
        kind_arr = None
        for k, v in self.iter_latest(want):
            cx, cz, dim, tag, sy = parse_chunk_key(k)
            if dim != 0:
                if tag == TAG_SUBCHUNK and sy == 0:
                    dims[dim] += 1
                continue
            n += 1
            if progress and n % 50000 == 0:
                progress(n)
            if tag == TAG_SUBCHUNK:
                try:
                    blk = self.decoder.decode(v)
                except Exception:
                    continue
                if blk is None:
                    continue
                if built_arr is None or len(built_arr) < len(pal.keys):
                    A = pal.arrays()
                    built_arr, kind_arr = A['built'], A['kind']
                bc = np.bincount(blk.ravel(), minlength=len(pal.keys))
                if len(bc) > len(counts):
                    counts = np.pad(counts, (0, len(bc) - len(counts) + 1024))
                counts[:len(bc)] += bc
                chunk_built[(cx, cz)] += float((bc * built_arr[:len(bc)]).sum())
                nz = np.nonzero(bc)[0]
                chunk_parts.setdefault((cx, cz), []).append((nz.astype(np.uint16), bc[nz].astype(np.int32)))
                drawable = kind_arr[blk] != 0  # x, z, y
                if drawable.any():
                    any_ = drawable.any(axis=2)
                    ty = 15 - np.argmax(drawable[:, :, ::-1], axis=2)
                    xx, zz = np.meshgrid(np.arange(16), np.arange(16), indexing='ij')
                    tidx = blk[xx, zz, ty]
                    ent = chunk_top.get((cx, cz))
                    if ent is None:
                        ent = (np.full((16, 16), -999, dtype=np.int16), np.zeros((16, 16), dtype=np.uint16))
                        chunk_top[(cx, cz)] = ent
                    h, ti = ent
                    yy = (sy * 16 + ty).astype(np.int16)
                    # stored as [z, x] to match the Java layout
                    upd = any_.T & (yy.T > h)
                    h[upd] = yy.T[upd]
                    ti[upd] = tidx.T[upd]
                else:
                    chunk_top.setdefault((cx, cz), (np.full((16, 16), -999, dtype=np.int16),
                                                    np.zeros((16, 16), dtype=np.uint16)))
            elif tag == TAG_BLOCKENT:
                try:
                    tes = nbt.load_all(v, little=True)
                except Exception:
                    continue
                for te in tes:
                    if not te:
                        continue
                    tid = str(te.get('id', ''))
                    pos = [te.get('x'), te.get('y'), te.get('z')]
                    chunk_be[(cx, cz)] += 1
                    if tid == 'Sign':
                        txt = _text(te.get('Text', ''))
                        if txt.strip():
                            signs.append({'pos': pos, 'lines': txt.split('\n')})
                    items = te.get('Items')
                    if items:
                        inv = Counter()
                        for it in items:
                            nm = str(it.get('Name', '')).replace('minecraft:', '')
                            if not nm:
                                continue
                            tag_ = it.get('tag') or {}
                            disp = (tag_.get('display') or {}).get('Name')
                            inv[disp or nm] += it.get('Count', 1)
                            if nm in ('written_book', 'writable_book'):
                                pages = [pg.get('text', '') if isinstance(pg, dict) else str(pg)
                                         for pg in tag_.get('pages', [])]
                                books.append({'pos': pos, 'title': tag_.get('title'),
                                              'author': tag_.get('author'), 'pages': pages[:20]})
                        if inv:
                            containers.append({'pos': pos, 'type': tid, 'items': inv.most_common(8),
                                               'total': sum(inv.values())})
            elif tag == TAG_ENTITY:
                try:
                    ents = nbt.load_all(v, little=True)
                except Exception:
                    continue
                for e in ents:
                    if not e:
                        continue
                    eid = str(e.get('identifier', '?')).replace('minecraft:', '')
                    entities[eid] += 1
                    if e.get('CustomName'):
                        named.append({'type': eid, 'name': e.get('CustomName'),
                                      'pos': [round(x) for x in e.get('Pos', [0, 0, 0])]})
        keys = list(chunk_top.keys())
        cx = np.array([k[0] for k in keys]); cz = np.array([k[1] for k in keys])
        top = np.array([chunk_top[k][1] for k in keys]) if keys else np.zeros((0, 16, 16), np.uint16)
        hgt = np.array([chunk_top[k][0] for k in keys]) if keys else np.zeros((0, 16, 16), np.int16)
        built = np.array([chunk_built[k] for k in keys], dtype=np.float64)
        self._chunks = set(keys)
        cc_idx, cc_cnt = [], []
        for k in keys:
            parts = chunk_parts.get(k)
            if not parts:
                cc_idx.append(np.zeros(0, np.uint16)); cc_cnt.append(np.zeros(0, np.int32)); continue
            ii = np.concatenate([p[0] for p in parts]).astype(np.int64)
            cn = np.concatenate([p[1] for p in parts]).astype(np.int64)
            tot = np.bincount(ii, weights=cn)
            nz = np.nonzero(tot)[0]
            cc_idx.append(nz.astype(np.uint16)); cc_cnt.append(tot[nz].astype(np.int32))
        del chunk_parts
        return {
            'cx': cx, 'cz': cz, 'built': built, 'inhabited': np.zeros(len(keys), dtype=np.int64),
            'timestamp': np.zeros(len(keys), dtype=np.int64),
            'top': top, 'height': np.clip(hgt, 0, 255).astype(np.uint8), 'height_raw': hgt,
            'chunk_counts': (cc_idx, cc_cnt),
            'counts': counts, 'signs': signs, 'containers': containers, 'books': books,
            'entities': entities, 'named': named, 'other_dims': dict(dims),
        }

    # ------------------------------------------------------------------ volume extraction
    def volumes(self, rects, ymin=0, ymax=256):
        """For each (x0, z0, w, d) return a palette-index volume shaped (w, H, d) indexed [x, y, z]
        (y offset by ymin). All rects are filled in a single pass over the database."""
        H = ymax - ymin
        vols = [np.zeros((w, H, d), dtype=np.uint16) for (x0, z0, w, d) in rects]
        wanted = set()
        for (x0, z0, w, d) in rects:
            for cx in range(x0 >> 4, ((x0 + w - 1) >> 4) + 1):
                for cz in range(z0 >> 4, ((z0 + d - 1) >> 4) + 1):
                    wanted.add(struct.pack('<ii', cx, cz))

        def flt(k):
            return len(k) == 10 and k[8] == TAG_SUBCHUNK and k[:8] in wanted

        for k, v in self.iter_latest(flt):
            cx, cz = struct.unpack_from('<ii', k, 0)
            sy = struct.unpack_from('b', k, 9)[0]
            try:
                blk = self.decoder.decode(v)
            except Exception:
                continue
            if blk is None:
                continue
            blk = np.transpose(blk, (0, 2, 1))  # x, y, z
            bx, bz, by = cx * 16, cz * 16, sy * 16 - ymin
            if by < 0 or by + 16 > H:
                continue
            for vol, (x0, z0, w, d) in zip(vols, rects):
                ax0, az0 = max(bx, x0), max(bz, z0)
                ax1, az1 = min(bx + 16, x0 + w), min(bz + 16, z0 + d)
                if ax0 >= ax1 or az0 >= az1:
                    continue
                vol[ax0 - x0:ax1 - x0, by:by + 16, az0 - z0:az1 - z0] = \
                    blk[ax0 - bx:ax1 - bx, :, az0 - bz:az1 - bz]
        return vols
