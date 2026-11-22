"""Reader for Java Edition (Anvil, pre-1.13 numeric block IDs) worlds."""
import json, os, re, struct, zlib, datetime
from collections import Counter
import numpy as np

import nbt
from blocks import java_lut

GAME_MODES = {0: 'Survival', 1: 'Creative', 2: 'Adventure', 3: 'Spectator'}


def text_component(s):
    """Flatten a 1.12 JSON text component (sign lines / book pages) to plain text."""
    if not s:
        return ''
    try:
        j = json.loads(s)
    except Exception:
        return s.strip('"')

    def flat(c):
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            return ''.join(flat(x) for x in c)
        if isinstance(c, dict):
            return c.get('text', '') + ''.join(flat(x) for x in c.get('extra', []))
        return str(c)
    return flat(j)


class Region:
    def __init__(self, path):
        with open(path, 'rb') as f:
            self.buf = f.read()
        m = re.search(r'r\.(-?\d+)\.(-?\d+)\.mca$', path)
        self.rx, self.rz = int(m.group(1)), int(m.group(2))

    def chunks(self):
        b = self.buf
        if len(b) < 8192:
            return
        for i in range(1024):
            loc = struct.unpack_from('>I', b, i * 4)[0]
            off, cnt = loc >> 8, loc & 0xff
            if off == 0 or cnt == 0:
                continue
            ts = struct.unpack_from('>I', b, 4096 + i * 4)[0]
            p = off * 4096
            if p + 5 > len(b):
                continue
            length, comp = struct.unpack_from('>IB', b, p)
            raw = b[p + 5:p + 4 + length]
            try:
                data = zlib.decompress(raw) if comp == 2 else __import__('gzip').decompress(raw)
                root = nbt.NBTReader(data).root()
            except Exception:
                continue
            yield self.rx * 32 + (i & 31), self.rz * 32 + (i >> 5), ts, root


def chunk_blocks(level):
    """Return (ids, data) arrays shaped (256, 16, 16) [y, z, x] for a 1.12 chunk."""
    ids = np.zeros((16, 4096), dtype=np.uint16)
    data = np.zeros((16, 4096), dtype=np.uint8)
    for s in level.get('Sections', []):
        y = s['Y'] & 0xff
        if y > 15:
            continue
        ids[y] = np.frombuffer(s['Blocks'], dtype=np.uint8)
        if 'Add' in s:
            add = np.frombuffer(s['Add'], dtype=np.uint8)
            a = np.empty(4096, dtype=np.uint16)
            a[0::2] = add & 0x0f
            a[1::2] = add >> 4
            ids[y] |= a << 8
        d = np.frombuffer(s['Data'], dtype=np.uint8)
        data[y, 0::2] = d & 0x0f
        data[y, 1::2] = d >> 4
    return ids.reshape(256, 16, 16), data.reshape(256, 16, 16)


def item_name(it):
    if not isinstance(it, dict):
        return str(it), None
    n = str(it.get('id', '?')).replace('minecraft:', '')
    tag = it.get('tag')
    disp = None
    if isinstance(tag, dict) and isinstance(tag.get('display'), dict):
        disp = tag['display'].get('Name')
        if not isinstance(disp, str):
            disp = None
    return n, disp


ENTITY_ALIASES = {'item': 'item', 'xporb': 'xp_orb', 'xp_orb': 'xp_orb', 'pigzombie': 'zombie_pigman',
                  'entityhorse': 'horse', 'villagergolem': 'iron_golem', 'mushroomcow': 'mooshroom',
                  'ozelot': 'ocelot', 'snowman': 'snow_golem', 'minecartchest': 'chest_minecart',
                  'minecartrideable': 'minecart', 'itemframe': 'item_frame', 'armorstand': 'armor_stand',
                  'primedtnt': 'tnt', 'fallingsand': 'falling_block', 'lavaslime': 'magma_cube',
                  'enderdragon': 'ender_dragon', 'cavespider': 'cave_spider', 'witherboss': 'wither'}


def norm_entity(eid):
    e = str(eid).replace('minecraft:', '')
    return ENTITY_ALIASES.get(e.lower(), e.lower())


class JavaWorld:
    edition = 'Java'

    def __init__(self, path, palette, player_names=None):
        self.path = path
        self.palette = palette
        self.lut = java_lut(palette)
        self.player_names = player_names or {}
        self.level = nbt.load_file(os.path.join(path, 'level.dat'))['Data']

    # ------------------------------------------------------------------ metadata
    def metadata(self):
        L = self.level
        v = L.get('Version') or {}
        players = []
        pdir = os.path.join(self.path, 'playerdata')
        sdir = os.path.join(self.path, 'stats')
        if os.path.isdir(pdir):
            for f in sorted(os.listdir(pdir)):
                if not f.endswith('.dat'):
                    continue
                uuid = f[:-4]
                try:
                    p = nbt.load_file(os.path.join(pdir, f))
                except Exception:
                    continue
                stats = {}
                sp = os.path.join(sdir, uuid + '.json')
                if os.path.exists(sp):
                    try:
                        stats = json.load(open(sp))
                    except Exception:
                        pass
                inv = Counter()
                for it in p.get('Inventory', []):
                    n, disp = item_name(it)
                    inv[disp or n] += it.get('Count', 1)
                ticks = stats.get('stat.playOneMinute', 0)
                mined = sum(v for k, v in stats.items() if k.startswith('stat.mineBlock.'))
                crafted = sum(v for k, v in stats.items() if k.startswith('stat.craftItem.'))
                used = sum(v for k, v in stats.items() if k.startswith('stat.useItem.'))
                walked = (stats.get('stat.walkOneCm', 0) + stats.get('stat.sprintOneCm', 0)) / 100
                flown = stats.get('stat.flyOneCm', 0) / 100
                players.append({
                    'uuid': uuid,
                    'name': self.player_names.get(uuid),
                    'pos': [round(x) for x in p.get('Pos', [0, 0, 0])],
                    'dimension': p.get('Dimension', 0),
                    'xp_level': p.get('XpLevel', 0),
                    'game_mode': GAME_MODES.get(p.get('playerGameType', 0), '?'),
                    'play_ticks': ticks,
                    'blocks_placed': used,
                    'blocks_mined': mined,
                    'items_crafted': crafted,
                    'walked_m': round(walked),
                    'flown_m': round(flown),
                    'deaths': stats.get('stat.deaths', 0),
                    'mob_kills': stats.get('stat.mobKills', 0),
                    'jumps': stats.get('stat.jump', 0),
                    'inventory': inv.most_common(12),
                })
        players.sort(key=lambda p: -p['play_ticks'])
        return {
            'edition': 'Java',
            'level_name': L.get('LevelName'),
            'version': v.get('Name') or '1.12 or earlier',
            'data_version': L.get('DataVersion'),
            'game_mode': GAME_MODES.get(L.get('GameType', 0), '?'),
            'hardcore': bool(L.get('hardcore', 0)),
            'cheats': bool(L.get('allowCommands', 0)),
            'generator': {'default': 'Default', 'flat': 'Superflat', 'largeBiomes': 'Large Biomes',
                          'amplified': 'Amplified', 'customized': 'Customized'}.get(L.get('generatorName'),
                                                                                   L.get('generatorName')),
            'seed': L.get('RandomSeed'),
            'spawn': [L.get('SpawnX'), L.get('SpawnY'), L.get('SpawnZ')],
            'last_played': datetime.datetime.utcfromtimestamp(L.get('LastPlayed', 0) / 1000).isoformat() + 'Z',
            'world_ticks': L.get('Time', 0),
            'day_time': L.get('DayTime', 0),
            'raining': bool(L.get('raining', 0)),
            'thundering': bool(L.get('thundering', 0)),
            'players': players,
            'dimensions': [d for d, sub in (('Nether', 'DIM-1'), ('The End', 'DIM1'))
                           if os.path.isdir(os.path.join(self.path, sub, 'region'))
                           and os.listdir(os.path.join(self.path, sub, 'region'))],
        }

    # ------------------------------------------------------------------ scanning
    def region_files(self):
        d = os.path.join(self.path, 'region')
        return [os.path.join(d, f) for f in os.listdir(d) if f.endswith('.mca')]

    def scan(self):
        """Scan every overworld chunk. Returns dict with per-chunk arrays and world-level findings."""
        pal = self.palette
        P = pal.arrays()
        cx_l, cz_l, built_l, inh_l, ts_l, top_l, hgt_l = [], [], [], [], [], [], []
        cc_idx, cc_cnt = [], []
        counts = np.zeros(65536, dtype=np.int64)
        signs, containers, books, entities, named = [], [], [], Counter(), []
        self._chunk_index = {}
        for rpath in self.region_files():
            try:
                reg = Region(rpath)
            except Exception:
                continue
            for cx, cz, ts, root in reg.chunks():
                level = root.get('Level', root)
                ids, data = chunk_blocks(level)
                comb = (ids.astype(np.uint32) << 4) | data
                pidx = self.lut[np.minimum(comb, 65535)]
                bc = np.bincount(pidx.ravel(), minlength=len(pal.keys))
                if len(bc) > len(counts):
                    counts = np.pad(counts, (0, len(bc) - len(counts)))
                counts[:len(bc)] += bc
                # top block per column (ignoring skip blocks)
                drawable = P['kind'][pidx] != 0
                any_ = drawable.any(axis=0)
                top_y = 255 - np.argmax(drawable[::-1], axis=0)
                top_y[~any_] = 0
                zz, xx = np.meshgrid(np.arange(16), np.arange(16), indexing='ij')
                top_idx = pidx[top_y, zz, xx]
                top_idx[~any_] = 0
                built = float((bc * P['built'][:len(bc)]).sum()) if len(bc) else 0.0
                nz = np.nonzero(bc)[0]
                cc_idx.append(nz.astype(np.uint16)); cc_cnt.append(bc[nz].astype(np.int32))
                cx_l.append(cx); cz_l.append(cz); built_l.append(built)
                inh_l.append(level.get('InhabitedTime', 0)); ts_l.append(ts)
                top_l.append(top_idx.astype(np.uint16)); hgt_l.append(top_y.astype(np.uint8))
                self._chunk_index[(cx, cz)] = rpath
                for te in level.get('TileEntities', []):
                    tid = str(te.get('id', '')).replace('minecraft:', '')
                    pos = [te.get('x'), te.get('y'), te.get('z')]
                    if tid.lower() == 'sign':
                        lines = [text_component(te.get(f'Text{i}', '')) for i in range(1, 5)]
                        if any(l.strip() for l in lines):
                            signs.append({'pos': pos, 'lines': lines})
                    items = te.get('Items')
                    if items:
                        inv = Counter()
                        for it in items:
                            n, disp = item_name(it)
                            inv[disp or n] += it.get('Count', 1)
                            if n in ('written_book', 'writable_book'):
                                tag = it.get('tag') if isinstance(it.get('tag'), dict) else {}
                                pages = [text_component(p) if n == 'written_book' else p
                                         for p in tag.get('pages', [])]
                                books.append({'pos': pos, 'title': tag.get('title'), 'author': tag.get('author'),
                                              'pages': pages[:20]})
                        containers.append({'pos': pos, 'type': tid, 'items': inv.most_common(8),
                                           'total': sum(inv.values())})
                for e in level.get('Entities', []):
                    eid = norm_entity(e.get('id', ''))
                    entities[eid] += 1
                    if e.get('CustomName') and isinstance(e.get('CustomName'), str):
                        named.append({'type': eid, 'name': e.get('CustomName').strip('"'),
                                      'pos': [round(x) for x in e.get('Pos', [0, 0, 0])]})
        return {
            'cx': np.array(cx_l), 'cz': np.array(cz_l), 'built': np.array(built_l),
            'inhabited': np.array(inh_l), 'timestamp': np.array(ts_l),
            'top': np.array(top_l), 'height': np.array(hgt_l),
            'chunk_counts': (cc_idx, cc_cnt),
            'counts': counts, 'signs': signs, 'containers': containers, 'books': books,
            'entities': entities, 'named': named,
        }

    # ------------------------------------------------------------------ volume extraction
    def volume(self, x0, z0, w, d):
        """Return palette-index volume shaped (w, 256, d) indexed [x, y, z] for blocks
        x0 <= x < x0+w, z0 <= z < z0+d."""
        vol = np.zeros((w, 256, d), dtype=np.uint16)
        want = {}
        for cx in range(x0 >> 4, (x0 + w - 1 >> 4) + 1):
            for cz in range(z0 >> 4, (z0 + d - 1 >> 4) + 1):
                r = os.path.join(self.path, 'region', f'r.{cx >> 5}.{cz >> 5}.mca')
                if os.path.exists(r):
                    want.setdefault(r, set()).add((cx, cz))
        for rpath, cs in want.items():
            for cx, cz, ts, root in Region(rpath).chunks():
                if (cx, cz) not in cs:
                    continue
                level = root.get('Level', root)
                ids, data = chunk_blocks(level)
                pidx = self.lut[np.minimum((ids.astype(np.uint32) << 4) | data, 65535)]  # y, z, x
                blk = np.transpose(pidx, (2, 0, 1))  # x, y, z
                bx, bz = cx * 16, cz * 16
                ax0, az0 = max(bx, x0), max(bz, z0)
                ax1, az1 = min(bx + 16, x0 + w), min(bz + 16, z0 + d)
                if ax0 >= ax1 or az0 >= az1:
                    continue
                vol[ax0 - x0:ax1 - x0, :, az0 - z0:az1 - z0] = blk[ax0 - bx:ax1 - bx, :, az0 - bz:az1 - bz]
        return vol
