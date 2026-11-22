# The World Archive

A small museum for old Minecraft worlds. Each save is scanned straight from its files, its most
built-up / most-visited areas are rendered as isometric dioramas (from four angles), and everything
interesting that can be read from the save is put on display: version, mode, dates, play time, signs,
books, chests, named mobs, a survey map, a block census and per-player stats.

```
web/            the static site (open via any HTTP server)
  curation.json   hand-written titles, descriptions and exhibit captions
  data/           generated: worlds.json + one folder per world (renders, map, world.json)
tools/          the Python build pipeline (numpy + Pillow, no other dependencies)
worlds/         shortcuts (.lnk), save folders or .mcworld files to include (not committed)
```

## Viewing

```
python -m http.server 8000 -d web
```

then open <http://localhost:8000>. (Opening `index.html` directly from disk won't work because the
page fetches its JSON.)

## Adding / rebuilding worlds

1. Drop a save folder, a `.mcworld` file, or a Windows shortcut to either into `worlds/`.
2. Run `python tools/build.py` (needs `numpy` and `Pillow`).
   - `--only <id>` rebuild a single world (`id` is the slugified folder name, e.g. `glitchdemall-6`)
   - `--rescan` ignore the scan cache in `tools/.cache/`
   - `--map-only` only redraw the survey maps (keeps existing renders)
   - `--index-only` just regenerate `web/data/worlds.json` from existing per-world data
3. Edit `web/curation.json` to give worlds and exhibits titles and descriptions — no rebuild needed.
   Per world you can set `title`, `summary`, `description` (HTML allowed), `era`, `wing`, `order`,
   `exhibit_order`, `hide_exhibits`, `hide_signs` (`"x,y,z"` positions) and per-exhibit
   `title` / `caption`.
4. Optionally label your own account by mapping its UUID to `"You"` in `players.json` (gitignored).

### Privacy

The published data is sanitised by `tools/sanitize.py` (run automatically by the build): sign text,
books, pet / item custom names and player account IDs are stripped, leaving only anonymous counts and
statistics. The isometric renders themselves can still show any words players spelled out in blocks.

The first scan of a big Bedrock world is slow (~15–20 min for 237k chunks); results are cached in
`tools/.cache/`, so later builds only re-render.

### Supported formats

- **Java Edition** Anvil worlds with numeric block IDs (Beta 1.3 – 1.12.2).
- **Bedrock Edition** LevelDB worlds (palette sub-chunks, 1.2+), read with a bundled pure-Python
  LevelDB reader — works directly on `.mcworld` files without extracting them.

### How exhibits are chosen

Every chunk is scored by how many "player-made" blocks it contains (planks, wool, glass, concrete,
redstone, etc.) plus how long players spent nearby (`InhabitedTime`, Java only). The densest
neighbourhoods become exhibits, rendered up to 256×256 blocks with a cut-away "diorama" base.

### How dates are worked out

Java region files store a save timestamp per chunk. Chunks re-saved in the last 60 days (i.e. from
opening the world recently) are ignored, so the remaining range reflects when the world was really
being played. For Bedrock, the `LastPlayed` field is used.
