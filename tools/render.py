"""Isometric voxel renderer, top-down map renderer and "interesting area" picker."""
import numpy as np
from PIL import Image

FACE_TOP, FACE_LEFT, FACE_RIGHT = 1, 2, 0  # axis index of the hit face: x, y, z
SHAPE_BOXES = {
    0: ((0, 0, 0), (1, 1, 1)),              # full
    1: ((0, 0, 0), (1, 0.5, 1)),            # bottom slab
    2: ((0, 0.5, 0), (1, 1, 1)),            # top slab
    3: ((0.34, 0, 0.34), (0.66, 1, 0.66)),  # post (fences, walls, doors)
    4: ((0.3, 0, 0.3), (0.7, 0.55, 0.7)),   # small (torches, pots, saplings)
}


def sprite(u, box):
    """Rasterise a box inside a unit cell into a 2u x 2u sprite.
    Returns arrays (dx, dy, face, edge_factor) for every covered pixel."""
    lo = np.array(box[0], dtype=float)
    hi = np.array(box[1], dtype=float)
    out = []
    for j in range(2 * u):
        for i in range(2 * u):
            X = (-u + i + 0.5) / u
            Y = (-u + j + 0.5) / u
            p0 = np.array([(X + 2 * Y) / 2, 0.0, (2 * Y - X) / 2])
            tlo = lo - p0
            thi = hi - p0
            tmin, tmax = tlo.max(), thi.min()
            if tmin >= tmax:
                continue
            face = int(np.argmin(thi))
            h = p0 + tmax
            other = [a for a in range(3) if a != face]
            dist = min(min(h[a] - lo[a], hi[a] - h[a]) for a in other) * u
            ef = 0.86 if dist < 0.75 else 1.0
            out.append((i, j, face, ef))
    a = np.array(out, dtype=np.float32)
    return a[:, 0].astype(np.int32), a[:, 1].astype(np.int32), a[:, 2].astype(np.int32), a[:, 3]


_SPRITES = {}


def get_sprites(u):
    if u not in _SPRITES:
        _SPRITES[u] = {s: sprite(u, b) for s, b in SHAPE_BOXES.items()}
    return _SPRITES[u]


def _hash_noise(x, y, z):
    h = (x.astype(np.int64) * 73856093) ^ (y.astype(np.int64) * 19349663) ^ (z.astype(np.int64) * 83492791)
    h = (h ^ (h >> 13)) & 0xff
    return 0.95 + 0.10 * (h.astype(np.float32) / 255.0)


def render_iso(vol, P, u=4, rotation=0, world_origin=(0, 0, 0)):
    """Render a palette-index volume indexed [x, y, z] as an isometric RGBA image.
    rotation k rotates the view 90 degrees k times."""
    vol = np.rot90(vol, rotation, axes=(0, 2)) if rotation else vol
    vol = np.ascontiguousarray(vol)
    W, H, D = vol.shape
    kind = P['kind'][vol]
    shape = P['shape'][vol]

    # Overlays (carpet, snow, crops, rails...) are painted onto the top of the block below.
    ov = np.argwhere(kind == 3)
    ov = ov[ov[:, 1] > 0]
    ov_idx = vol[ov[:, 0], ov[:, 1], ov[:, 2]]
    if len(ov):
        vol = vol.copy()
        vol[kind == 3] = 0
        kind = np.where(kind == 3, 0, kind)

    occ = (kind == 1) & (shape == 0)
    occp = np.zeros((W + 1, H + 1, D + 1), dtype=bool)
    occp[:W, :H, :D] = occ
    hidden = occp[1:, :H, :D] & occp[:W, 1:, :D] & occp[:W, :H, 1:]

    ox, oy = D * u, H * u
    img_w, img_h = (W + D) * u, (W + D) * u // 2 + H * u + 2
    zbuf = np.full((img_h, img_w), -1, dtype=np.int32)
    color = np.zeros((img_h, img_w, 3), dtype=np.float32)
    sprites = get_sprites(u)

    def prepare(mask):
        xs, ys, zs = np.nonzero(mask)
        depth = (xs + ys + zs).astype(np.int32)
        order = np.argsort(depth, kind='stable')
        xs, ys, zs, depth = xs[order], ys[order], zs[order], depth[order]
        idx = vol[xs, ys, zs]
        bx = (xs - zs) * u + ox - u
        by = (xs + zs) * (u // 2) - ys * u + oy - u
        return xs, ys, zs, depth, idx, bx, by

    def face_colors(xs, ys, zs, idx, lin_lookup=None):
        top = P['rgb'][idx].copy()
        side = P['side'][idx].copy()
        if len(ov) and lin_lookup is not None:
            lin = (xs.astype(np.int64) * H + ys) * D + zs
            below = (ov[:, 0].astype(np.int64) * H + ov[:, 1] - 1) * D + ov[:, 2]
            pos = np.searchsorted(lin, below, sorter=lin_lookup)
            pos = np.clip(pos, 0, len(lin) - 1)
            hit = lin[lin_lookup[pos]] == below
            tgt = lin_lookup[pos[hit]]
            b = P['blend'][ov_idx[hit]][:, None]
            top[tgt] = top[tgt] * (1 - b) + P['rgb'][ov_idx[hit]] * b
        noise = _hash_noise(xs, ys, zs)[:, None]
        # simple ambient occlusion on top faces: neighbours one level up
        ao = np.ones(len(xs), dtype=np.float32)
        yp = np.minimum(ys + 1, H - 1)
        for dx, dz in ((-1, 0), (0, -1), (1, 0), (0, 1)):
            nx = np.clip(xs + dx, 0, W - 1)
            nz = np.clip(zs + dz, 0, D - 1)
            ao -= 0.07 * (occ[nx, yp, nz] & (ys + 1 < H))
        glow = P['glow'][idx][:, None]
        top = top * noise * ao[:, None]
        left = side * noise * np.where(glow, 0.95, 0.80)
        right = side * noise * np.where(glow, 0.9, 0.64)
        return {FACE_TOP: top, FACE_LEFT: left, FACE_RIGHT: right}

    def splat(xs, ys, zs, depth, idx, bx, by, cols, zb, cb, ab=None, alpha=None):
        shapes = P['shape'][idx]
        for s, (sdx, sdy, sface, sef) in sprites.items():
            sel = np.nonzero(shapes == s)[0]
            if not len(sel):
                continue
            bxs, bys, ds = bx[sel], by[sel], depth[sel]
            for k in range(len(sdx)):
                tx = bxs + sdx[k]
                ty = bys + sdy[k]
                m = ds > zb[ty, tx]
                if not m.any():
                    continue
                ii = sel[m]
                zb[ty[m], tx[m]] = ds[m]
                cb[ty[m], tx[m]] = cols[int(sface[k])][ii] * sef[k]
                if ab is not None:
                    ab[ty[m], tx[m]] = alpha[ii]

    # Opaque & partial solids
    solid = (kind == 1) & ~hidden
    xs, ys, zs, depth, idx, bx, by = prepare(solid)
    lin = (xs.astype(np.int64) * H + ys) * D + zs
    cols = face_colors(xs, ys, zs, idx, np.argsort(lin))
    splat(xs, ys, zs, depth, idx, bx, by, cols, zbuf, color)

    # Translucent layer (water, glass, ice): surface faces only, alpha-blended over solids.
    tr = kind == 2
    if tr.any():
        same = np.zeros((W + 1, H + 1, D + 1), dtype=np.int32) - 1
        same[:W, :H, :D] = np.where(tr, vol.astype(np.int32), -1)
        v32 = vol.astype(np.int32)
        cover = lambda nb, nocc: (nb == v32) | nocc
        hid_t = cover(same[1:, :H, :D], occp[1:, :H, :D]) & cover(same[:W, 1:, :D], occp[:W, 1:, :D]) & \
            cover(same[:W, :H, 1:], occp[:W, :H, 1:])
        txs, tys, tzs, tdepth, tidx, tbx, tby = prepare(tr & ~hid_t)
        tcols = face_colors(txs, tys, tzs, tidx)
        tz = np.full_like(zbuf, -1)
        tc = np.zeros_like(color)
        ta = np.zeros((img_h, img_w), dtype=np.float32)
        splat(txs, tys, tzs, tdepth, tidx, tbx, tby, tcols, tz, tc, ta, P['alpha'][tidx])
        front = tz > zbuf
        a = np.where(front, ta, 0)[..., None]
        color = color * (1 - a) + tc * a
        alpha_ch = np.where(zbuf >= 0, 1.0, np.where(front, ta, 0))
    else:
        alpha_ch = (zbuf >= 0).astype(np.float32)

    rgba = np.zeros((img_h, img_w, 4), dtype=np.uint8)
    rgba[..., :3] = np.clip(color, 0, 255).astype(np.uint8)
    rgba[..., 3] = (np.clip(alpha_ch, 0, 1) * 255).astype(np.uint8)
    img = Image.fromarray(rgba, 'RGBA')
    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img


def crop_volume(vol, P):
    """Trim empty sky and dig a shallow 'diorama' floor below the lowest surface."""
    kind = P['kind'][vol]
    drawable = kind != 0
    cols_any = drawable.any(axis=1)
    if not cols_any.any():
        return vol, 0
    ys_any = np.nonzero(drawable.any(axis=(0, 2)))[0]
    top = int(ys_any.max()) + 1
    Hh = vol.shape[1]
    surf = Hh - 1 - np.argmax(drawable[:, ::-1, :], axis=1)
    surf = surf[cols_any]
    floor = max(0, int(np.percentile(surf, 3)) - 8)
    return vol[:, floor:top, :], floor


def render_map(cx, cz, top, height, P, bounds, max_px=1600):
    """Top-down map with hillshading. bounds=(cx0, cz0, cx1, cz1) inclusive chunk coords."""
    cx0, cz0, cx1, cz1 = bounds
    full = max(cx1 - cx0 + 1, cz1 - cz0 + 1) * 16
    step = 1
    while full / step > max_px * 1.5 and step < 16:
        step *= 2
    cs = 16 // step  # pixels per chunk
    w, d = (cx1 - cx0 + 1) * cs, (cz1 - cz0 + 1) * cs
    idx = np.zeros((d, w), dtype=np.uint16)
    hm = np.zeros((d, w), dtype=np.float32)
    have = np.zeros((d, w), dtype=bool)
    sel = (cx >= cx0) & (cx <= cx1) & (cz >= cz0) & (cz <= cz1)
    for i in np.nonzero(sel)[0]:
        px, pz = (cx[i] - cx0) * cs, (cz[i] - cz0) * cs
        idx[pz:pz + cs, px:px + cs] = top[i][::step, ::step]
        hm[pz:pz + cs, px:px + cs] = height[i][::step, ::step]
        have[pz:pz + cs, px:px + cs] = True
    rgb = P['rgb'][idx].copy()
    # hillshade: compare with north-west neighbour
    shade = np.ones_like(hm)
    dh = hm - np.roll(np.roll(hm, 1, axis=0), 1, axis=1)
    shade += np.clip(dh, -3, 3) * 0.06
    trans = P['kind'][idx] == 2
    rgb *= shade[..., None]
    rgb[trans] = rgb[trans] * 0.85
    out = np.zeros((d, w, 4), dtype=np.uint8)
    out[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    out[..., 3] = np.where(have, 255, 0)
    img = Image.fromarray(out, 'RGBA')
    scale = float(step)  # blocks per pixel
    if max(w, d) > max_px:
        f = max(w, d) / max_px
        img = img.resize((max(1, int(w / f)), max(1, int(d / f))), Image.LANCZOS)
        scale *= f
    elif max(w, d) < 500:
        # small worlds: upscale so the map isn't tiny (nearest neighbour keeps it crisp)
        f = max(1, 800 // max(w, d))
        img = img.resize((w * f, d * f), Image.NEAREST)
        scale /= f
    return img, scale


# ---------------------------------------------------------------------------------- area picking

def chunk_scores(built, inhabited):
    # Building counts far more than standing around (AFK spots have high InhabitedTime but nothing built).
    b = built.astype(np.float64)
    return b + np.minimum(inhabited.astype(np.float64) / 80.0, b * 4 + 50)


def pick_areas(cx, cz, built, inhabited, max_areas=3, max_chunks=16, min_chunks=5, min_built=250, min_ratio=0.12):
    """Greedily pick up to `max_areas` rectangular areas (in chunk units) with the most building /
    player activity. Returns list of dicts with block bounds and a score."""
    if len(cx) == 0:
        return []
    s = chunk_scores(built, inhabited)
    gx0, gz0 = cx.min(), cz.min()
    gw, gd = cx.max() - gx0 + 1, cz.max() - gz0 + 1
    grid = {}
    for i in range(len(cx)):
        grid[(int(cx[i]), int(cz[i]))] = s[i]
    exists = set(grid)
    used = set()
    areas = []
    win = 8  # smoothing window radius (chunks)
    keys = np.array(list(grid.keys()))
    vals = np.array(list(grid.values()))
    first_score = None
    for _ in range(max_areas * 4):
        if len(areas) >= max_areas:
            break
        # find chunk whose neighbourhood has the highest total score
        best, best_c = 0, None
        avail = [(k, v) for k, v in zip(map(tuple, keys), vals) if k not in used and v > 0]
        if not avail:
            break
        # coarse search: evaluate neighbourhood for the top 400 chunks only
        avail.sort(key=lambda kv: -kv[1])
        for (kx, kz), _v in avail[:400]:
            tot = 0
            for dx in range(-win // 2, win // 2 + 1):
                for dz in range(-win // 2, win // 2 + 1):
                    c = (kx + dx, kz + dz)
                    if c not in used:
                        tot += grid.get(c, 0)
            if tot > best:
                best, best_c = tot, (kx, kz)
        if best_c is None or best <= 0:
            break
        if first_score is None:
            first_score = best
        elif best < first_score * min_ratio:
            break
        kx, kz = best_c
        # grow a bounding box around the peak over chunks with meaningful score
        peak = max(grid.get((kx + dx, kz + dz), 0) for dx in range(-2, 3) for dz in range(-2, 3))
        thr = max(peak * 0.06, 20)
        half = max_chunks // 2
        members = [(x, z) for x in range(kx - half, kx + half) for z in range(kz - half, kz + half)
                   if grid.get((x, z), 0) >= thr and (x, z) not in used]
        if not members:
            members = [(kx, kz)]
        xs = [m[0] for m in members]; zs = [m[1] for m in members]
        x0, x1, z0, z1 = min(xs) - 1, max(xs) + 1, min(zs) - 1, max(zs) + 1
        # enforce min/max size
        while x1 - x0 + 1 < min_chunks:
            x0 -= 1; x1 += 1 if x1 - x0 + 1 < min_chunks else 0
        while z1 - z0 + 1 < min_chunks:
            z0 -= 1; z1 += 1 if z1 - z0 + 1 < min_chunks else 0
        x0, x1 = max(x0, kx - half), min(x1, kx + half - 1)
        z0, z1 = max(z0, kz - half), min(z1, kz + half - 1)
        # shrink to chunks that actually exist
        ex = [c for c in exists if x0 <= c[0] <= x1 and z0 <= c[1] <= z1]
        if not ex:
            break
        x0 = min(c[0] for c in ex); x1 = max(c[0] for c in ex)
        z0 = min(c[1] for c in ex); z1 = max(c[1] for c in ex)
        for x in range(x0 - 2, x1 + 3):
            for z in range(z0 - 2, z1 + 3):
                used.add((x, z))
        tot_built = sum(built[i] for i in range(len(cx)) if x0 <= cx[i] <= x1 and z0 <= cz[i] <= z1)
        tot_inh = sum(inhabited[i] for i in range(len(cx)) if x0 <= cx[i] <= x1 and z0 <= cz[i] <= z1)
        if tot_built < min_built and areas:
            continue
        areas.append({'chunks': [int(x0), int(z0), int(x1), int(z1)],
                      'x0': int(x0 * 16), 'z0': int(z0 * 16),
                      'w': int((x1 - x0 + 1) * 16), 'd': int((z1 - z0 + 1) * 16),
                      'score': float(best), 'built_blocks': int(tot_built),
                      'inhabited_ticks': int(tot_inh)})
    return areas


def clusters(cx, cz, gap=3):
    """Group chunks into clusters (chunks within `gap` of each other). Returns list of index arrays,
    largest first."""
    pos = {(int(a), int(b)): i for i, (a, b) in enumerate(zip(cx, cz))}
    seen = set()
    out = []
    for start in pos:
        if start in seen:
            continue
        stack = [start]; seen.add(start); members = []
        while stack:
            c = stack.pop(); members.append(pos[c])
            for dx in range(-gap, gap + 1):
                for dz in range(-gap, gap + 1):
                    n = (c[0] + dx, c[1] + dz)
                    if n in pos and n not in seen:
                        seen.add(n); stack.append(n)
        out.append(np.array(members))
    out.sort(key=lambda m: -len(m))
    return out
