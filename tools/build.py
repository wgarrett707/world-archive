"""Build the World Archive data: scans every world referenced in ./worlds and writes
web/data/worlds.json plus rendered images.

Usage:  python tools/build.py [--only <id>] [--rescan] [--no-render]

./worlds may contain Windows shortcuts (.lnk) to save folders / .mcworld files,
save folders themselves, or .mcworld files.
"""
import argparse, datetime, json, os, pickle, re, shutil, subprocess, sys, time
from collections import Counter
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from blocks import Palette
import render
from sanitize import sanitize_world

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORLDS_DIR = os.path.join(ROOT, 'worlds')
OUT = os.path.join(ROOT, 'web', 'data')
CACHE = os.path.join(ROOT, 'tools', '.cache')
CURATION = os.path.join(ROOT, 'web', 'curation.json')
PLAYERS = os.path.join(ROOT, 'players.json')


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def resolve_lnk(path):
    ps = f"(New-Object -ComObject WScript.Shell).CreateShortcut('{path}').TargetPath"
    out = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True)
    return out.stdout.strip()


def find_sources():
    out = []
    for f in sorted(os.listdir(WORLDS_DIR)):
        p = os.path.join(WORLDS_DIR, f)
        if f.lower().endswith('.lnk'):
            t = resolve_lnk(p)
            if t and os.path.exists(t):
                out.append(t)
            else:
                log('  ! broken shortcut', f, '->', t)
        elif os.path.isdir(p) or f.lower().endswith(('.mcworld', '.zip')):
            out.append(p)
    return out


def open_world(src, palette, names):
    if os.path.isdir(src):
        if os.path.isdir(os.path.join(src, 'db')):
            from bedrock_world import BedrockWorld
            return BedrockWorld(src, palette, names)
        from java_world import JavaWorld
        return JavaWorld(src, palette, names)
    from bedrock_world import BedrockWorld
    return BedrockWorld(src, palette, names)


def world_id(src):
    base = os.path.basename(src.rstrip('\\/'))
    base = re.sub(r'\.(mcworld|zip)$', '', base, flags=re.I)
    return slug(base)


def save_img(img, path, quality=90):
    img.save(path, 'WEBP', quality=quality, method=6)


def to_jsonable(o):
    if isinstance(o, dict):
        return {str(k): to_jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [to_jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, bytes):
        return o.decode('utf-8', 'replace')
    return o


def hexcol(P, j):
    r, g, b = (int(x) for x in P['rgb'][j])
    return f'#{r:02x}{g:02x}{b:02x}'


SECTION = re.compile('§.')


def clean_signs(signs):
    out = []
    for s in signs:
        lines = [SECTION.sub('', l).rstrip() for l in s['lines']]
        if not any(ch.isalnum() for l in lines for ch in l):
            continue  # arrows / decoration only
        out.append({**s, 'lines': lines})
    return out


def dedupe_named(named):
    seen = Counter((n['name'], n['type']) for n in named)
    out, done = [], set()
    for n in named:
        k = (n['name'], n['type'])
        if k in done:
            continue
        done.add(k)
        out.append({**n, 'count': seen[k]})
    return out


def in_area(pos, a, pad=0):
    if not pos or pos[0] is None:
        return False
    return a['x0'] - pad <= pos[0] < a['x0'] + a['w'] + pad and a['z0'] - pad <= pos[-1] < a['z0'] + a['d'] + pad


def make_map(cx, cz, scan, P, areas, out_dir, wid, max_blocks=3072):
    """Top-down map of the main cluster (the one holding the first exhibit), cropped to
    max_blocks around that exhibit so long travel trails don't shrink the interesting part."""
    if not len(cx):
        return None
    cls = render.clusters(cx, cz, gap=4)
    main = cls[0]
    if areas:
        ac = areas[0]['chunks']
        for c in cls:
            if ((cx[c] >= ac[0]) & (cx[c] <= ac[2]) & (cz[c] >= ac[1]) & (cz[c] <= ac[3])).any():
                main = c
                break
    b = [int(cx[main].min()), int(cz[main].min()), int(cx[main].max()), int(cz[main].max())]
    half = max_blocks // 32
    cropped = False
    if areas and (b[2] - b[0] > 2 * half or b[3] - b[1] > 2 * half):
        ac = areas[0]['chunks']
        mx, mz = (ac[0] + ac[2]) // 2, (ac[1] + ac[3]) // 2
        nb = [max(b[0], mx - half), max(b[1], mz - half), min(b[2], mx + half), min(b[3], mz + half)]
        sel = main[(cx[main] >= nb[0]) & (cx[main] <= nb[2]) & (cz[main] >= nb[1]) & (cz[main] <= nb[3])]
        b = [int(cx[sel].min()), int(cz[sel].min()), int(cx[sel].max()), int(cz[sel].max())]
        main = sel
        cropped = True
    img, scale = render.render_map(cx, cz, scan['top'], scan['height'], P, tuple(b), max_px=1400)
    save_img(img, os.path.join(out_dir, 'map.webp'), 88)
    return {'src': f'data/{wid}/map.webp', 'w': img.size[0], 'h': img.size[1],
            'x0': b[0] * 16, 'z0': b[1] * 16, 'scale': scale, 'cropped': cropped,
            'chunks_in_view': int(len(main)), 'clusters': len(cls)}


def build_world(src, args, names):
    wid = world_id(src)
    log(f'== {wid}  ({src})')
    os.makedirs(CACHE, exist_ok=True)
    cache_path = os.path.join(CACHE, wid + '.pkl')
    palette = Palette()
    world = open_world(src, palette, names)
    meta = world.metadata()

    if os.path.exists(cache_path) and not args.rescan:
        log('  using cached scan')
        with open(cache_path, 'rb') as f:
            cached = pickle.load(f)
        for key in cached['palette']:
            palette.add(*key)
        scan = cached['scan']
    else:
        t = time.time()
        log('  scanning chunks...')
        scan = world.scan(progress=lambda n: log(f'    {n} records')) if meta['edition'] == 'Bedrock' else world.scan()
        log(f'  scanned {len(scan["cx"])} chunks in {time.time() - t:.0f}s')
        with open(cache_path, 'wb') as f:
            pickle.dump({'palette': palette.keys, 'scan': {k: v for k, v in scan.items()}}, f)

    P = palette.arrays()
    scan['signs'] = clean_signs(scan['signs'])
    meta['players'] = [p for p in meta['players'] if p.get('pos') != [0, 0, 0] or p.get('inventory')]
    out_dir = os.path.join(OUT, wid)
    # clear out renders from previous builds so stale exhibits don't linger
    if os.path.isdir(out_dir) and not args.no_render:
        for f in os.listdir(out_dir):
            if f.startswith('exhibit-'):
                os.remove(os.path.join(out_dir, f))
    os.makedirs(out_dir, exist_ok=True)

    cx, cz = scan['cx'], scan['cz']
    if 'chunk_counts' in scan:
        # re-score with the current block weights (lets weights change without a rescan)
        cc_idx, cc_cnt = scan['chunk_counts']
        W = P['built']
        scan['built'] = np.array([float((c * W[i]).sum()) if len(i) else 0.0 for i, c in zip(cc_idx, cc_cnt)])
    areas = render.pick_areas(cx, cz, scan['built'], scan['inhabited'], max_areas=3)
    if len(areas) == 1:
        # Only one real build site: add a wide "surroundings" view around it for context.
        a = areas[0]
        mx, mz = a['x0'] + a['w'] // 2, a['z0'] + a['d'] // 2
        areas.append({**a, 'x0': (mx - 256) // 16 * 16, 'z0': (mz - 256) // 16 * 16, 'w': 512, 'd': 512,
                      'wide': True})
    log(f'  picked {len(areas)} exhibit areas')

    # ---- volumes
    rects = [(a['x0'], a['z0'], a['w'], a['d']) for a in areas]
    if meta['edition'] == 'Bedrock':
        v = meta['version'].split('.')
        new_height = len(v) > 1 and v[0].isdigit() and (int(v[0]), int(v[1])) >= (1, 18)
        ymin, ymax = (-64, 320) if new_height else (0, 256)
        vols = world.volumes(rects, ymin, ymax) if not args.no_render else [None] * len(rects)
    else:
        ymin = 0
        vols = [world.volume(*r) for r in rects] if not args.no_render else [None] * len(rects)

    P = palette.arrays()  # volume extraction may have registered new block types
    exhibits = []
    for i, (a, vol) in enumerate(zip(areas, vols)):
        ex = dict(a)
        ex['id'] = f'exhibit-{i + 1}'
        if vol is not None:
            vol, floor = render.crop_volume(vol, P)
            ex['y_range'] = [int(floor + ymin), int(floor + ymin + vol.shape[1])]
            u = 6 if max(a['w'], a['d']) <= 160 else 4 if max(a['w'], a['d']) <= 256 else 2
            ex['scale'] = u
            # block composition of the exhibit
            bc = np.bincount(vol.ravel(), minlength=len(palette.keys))
            mats = [(palette.label(j), int(bc[j]), hexcol(P, j)) for j in np.argsort(-bc)
                    if bc[j] > 0 and P['kind'][j] != 0 and P['built'][j]][:10]
            ex['materials'] = mats
            ex['built_blocks'] = int(bc[:len(P['built'])][P['built'] > 0].sum())
            ex['score'] = round(float(a['score']), 1)
            ex['views'] = []
            for rot in range(4):
                t = time.time()
                img = render.render_iso(vol, P, u=u, rotation=rot)
                fn = f'{ex["id"]}-r{rot}.webp'
                save_img(img, os.path.join(out_dir, fn))
                ex['views'].append({'src': f'data/{wid}/{fn}', 'w': img.size[0], 'h': img.size[1]})
                if rot == 0:
                    th = img.copy()
                    th.thumbnail((640, 640))
                    save_img(th, os.path.join(out_dir, f'{ex["id"]}-thumb.webp'), 85)
                    ex['thumb'] = f'data/{wid}/{ex["id"]}-thumb.webp'
                log(f'    {ex["id"]} rot{rot} {img.size} {time.time() - t:.1f}s')
        ex['signs'] = [s for s in scan['signs'] if in_area(s['pos'], a)][:60]
        ex['containers'] = sorted([c for c in scan['containers'] if in_area(c['pos'], a)],
                                  key=lambda c: -c['total'])[:12]
        ex['books'] = [b for b in scan['books'] if in_area(b['pos'], a)][:10]
        ex['named'] = dedupe_named([n for n in scan['named'] if in_area(n['pos'], a)])[:30]
        exhibits.append(ex)

    # ---- overview map
    map_info = make_map(cx, cz, scan, P, areas, out_dir, wid)
    if args.map_only:
        p = os.path.join(out_dir, 'world.json')
        w = json.load(open(p, encoding='utf-8'))
        w['map'] = map_info
        json.dump(w, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        return w

    # ---- icon
    icon = None
    if os.path.isdir(src):
        for name in ('icon.png', 'world_icon.jpeg'):
            p = os.path.join(src, name)
            if os.path.exists(p):
                ext = os.path.splitext(name)[1]
                shutil.copy(p, os.path.join(out_dir, 'icon' + ext))
                icon = f'data/{wid}/icon{ext}'
    else:
        try:
            raw = world.db.zip.read(world.db.prefix + 'world_icon.jpeg')
            open(os.path.join(out_dir, 'icon.jpeg'), 'wb').write(raw)
            icon = f'data/{wid}/icon.jpeg'
        except Exception:
            pass

    # ---- dates from chunk save timestamps (ignore anything saved in the last 60 days,
    # which is just from re-opening the world recently)
    ts = scan['timestamp']
    cutoff = time.time() - 60 * 86400
    old = ts[(ts > 0) & (ts < cutoff)]
    dates = None
    if len(old):
        dates = {'first': datetime.datetime.utcfromtimestamp(int(old.min())).date().isoformat(),
                 'last': datetime.datetime.utcfromtimestamp(int(old.max())).date().isoformat()}
    elif meta['last_played'] and meta['last_played'][:4] != '1970':
        lp = meta['last_played'][:10]
        if datetime.datetime.fromisoformat(lp).timestamp() < cutoff:
            dates = {'first': None, 'last': lp}

    counts = scan['counts']
    top_blocks = [(palette.label(j), int(counts[j]), hexcol(P, j)) for j in np.argsort(-counts)[:400]
                  if j < len(palette.keys) and counts[j] > 0 and P['kind'][j] != 0][:16]
    built_blocks = [(palette.label(j), int(counts[j]), hexcol(P, j)) for j in np.argsort(-counts)[:2000]
                    if j < len(palette.keys) and counts[j] > 0 and P['built'][j]][:16]

    world_json = {
        'id': wid,
        'folder': os.path.basename(src.rstrip('\\/')),
        **meta,
        'seed': str(meta.get('seed')),
        'dates': dates,
        'icon': icon,
        'chunks': int(len(cx)),
        'area_km2': round(len(cx) * 256 / 1e6, 2),
        'top_blocks': top_blocks,
        'built_blocks': built_blocks,
        'total_built': int(sum(c[1] for c in built_blocks)),
        'entities': Counter(scan['entities']).most_common(14),
        'sign_count': len(scan['signs']),
        'container_count': len(scan['containers']),
        'book_count': len(scan['books']),
        'books': scan['books'][:12],
        'signs_sample': scan['signs'][:200],
        'named': dedupe_named(scan['named'])[:60],
        'map': map_info,
        'exhibits': exhibits,
        'other_dims': scan.get('other_dims'),
    }
    world_json = sanitize_world(to_jsonable(world_json))  # no signs, books, names or account IDs
    with open(os.path.join(out_dir, 'world.json'), 'w', encoding='utf-8') as f:
        json.dump(world_json, f, ensure_ascii=False, indent=1)
    return world_json


def summarize(w):
    keys = ['id', 'folder', 'edition', 'level_name', 'version', 'game_mode', 'generator', 'dates', 'icon',
            'chunks', 'area_km2', 'world_ticks', 'last_played', 'total_built']
    s = {k: w.get(k) for k in keys}
    s['players'] = len(w.get('players', []))
    s['exhibits_count'] = len(w.get('exhibits', []))
    s['thumb'] = w['exhibits'][0].get('thumb') if w.get('exhibits') else None
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only')
    ap.add_argument('--rescan', action='store_true')
    ap.add_argument('--no-render', action='store_true')
    ap.add_argument('--map-only', action='store_true', help='only redraw survey maps (keeps renders)')
    ap.add_argument('--index-only', action='store_true', help='rebuild worlds.json from existing world.json files')
    args = ap.parse_args()
    if args.map_only:
        args.no_render = True  # never touch renders when only redrawing maps
    names = json.load(open(PLAYERS)) if os.path.exists(PLAYERS) else {}
    os.makedirs(OUT, exist_ok=True)
    index_path = os.path.join(OUT, 'worlds.json')
    index = {}
    if os.path.exists(index_path):
        for w in json.load(open(index_path, encoding='utf-8')).get('worlds', []):
            index[w['id']] = w
    if args.index_only:
        index = {}
        for d in sorted(os.listdir(OUT)):
            p = os.path.join(OUT, d, 'world.json')
            if os.path.exists(p):
                index[d] = summarize(json.load(open(p, encoding='utf-8')))
    for src in ([] if args.index_only else find_sources()):
        wid = world_id(src)
        if args.only and args.only != wid:
            continue
        w = build_world(src, args, names)
        index[wid] = summarize(to_jsonable(w))
    curation = json.load(open(CURATION, encoding='utf-8')) if os.path.exists(CURATION) else {}
    worlds = list(index.values())
    for w in worlds:
        w.update({k: v for k, v in curation.get('worlds', {}).get(w['id'], {}).items() if k != 'exhibits'})
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump({'generated': datetime.datetime.utcnow().isoformat() + 'Z', 'worlds': worlds,
                   'collection': curation.get('collection', {})}, f, ensure_ascii=False, indent=1)
    log('wrote', index_path)


if __name__ == '__main__':
    main()
