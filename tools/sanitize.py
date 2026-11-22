"""Strip personal information from generated world data before it is published.

Removes sign text, books, custom names (pets, renamed items) and player account IDs, keeping only
anonymous counts and statistics. build.py runs this on every world it writes; run this file directly
to clean existing web/data/*/world.json files without re-rendering:

    python tools/sanitize.py
"""
import glob, json, os, re
from collections import Counter

ITEM_ID = re.compile(r'^[a-z0-9_:.]+$')
RENAMED = 'renamed item'


def _items(pairs):
    c = Counter()
    for name, count in pairs or []:
        c[name if ITEM_ID.match(str(name)) else RENAMED] += count
    return [[n, k] for n, k in c.most_common()]


def sanitize_world(w):
    w = dict(w)
    for key in ('signs_sample', 'books', 'named', 'signs'):
        w.pop(key, None)
    players = []
    for p in w.get('players', []):
        p = dict(p)
        uid = p.pop('uuid', '')
        if uid == '~local_player':
            p['host'] = True
        if p.get('name') != 'You':
            p.pop('name', None)
        p['inventory'] = _items(p.get('inventory'))
        players.append(p)
    w['players'] = players
    exhibits = []
    for e in w.get('exhibits', []):
        e = dict(e)
        e['sign_count'] = len(e.pop('signs', []) or [])
        e.pop('books', None)
        e.pop('named', None)
        e['containers'] = [{**c, 'items': _items(c.get('items'))} for c in e.get('containers', [])]
        exhibits.append(e)
    w['exhibits'] = exhibits
    return w


def main():
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web', 'data')
    for p in sorted(glob.glob(os.path.join(root, '*', 'world.json'))):
        w = json.load(open(p, encoding='utf-8'))
        json.dump(sanitize_world(w), open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('cleaned', os.path.relpath(p, root))


if __name__ == '__main__':
    main()
