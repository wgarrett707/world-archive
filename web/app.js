/* The World Archive — a tiny hash-routed museum for rendered Minecraft worlds. */
(() => {
  'use strict';

  const app = document.getElementById('app');
  const nav = document.getElementById('topnav');
  const lightbox = document.getElementById('lightbox');
  const state = { index: null, curation: {}, worlds: {}, order: [] };

  // ------------------------------------------------------------------ utils
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmt = (n) => (n == null ? '—' : Number(n).toLocaleString());
  const compact = (n) => (n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e4 ? Math.round(n / 1e3) + 'k' : fmt(n));
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const monthYear = (iso) => { if (!iso) return null; const [y, m] = iso.split('-'); return `${MONTHS[+m - 1]} ${y}`; };
  const fullDate = (iso) => { if (!iso) return null; const [y, m, d] = iso.slice(0, 10).split('-'); return `${MONTHS[+m - 1]} ${+d}, ${y}`; };
  const hours = (ticks) => ticks / 72000;
  const fmtHours = (h) => (h < 1 ? `${Math.round(h * 60)} min` : `${h < 10 ? h.toFixed(1) : Math.round(h)} h`);
  const el = (html) => { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; };
  const cap = (s) => String(s || '').replace(/^\w/, (c) => c.toUpperCase());

  async function getJSON(url) {
    const r = await fetch(url, { cache: 'no-cache' });
    if (!r.ok) throw new Error(`${url}: ${r.status}`);
    return r.json();
  }

  function cur(id) { return (state.curation.worlds || {})[id] || {}; }
  // Exhibits in display order, honouring curation's exhibit_order / hide_exhibits.
  function exhibitsFor(w) {
    const c = cur(w.id);
    let ex = (w.exhibits || []).filter((e) => !(c.hide_exhibits || []).includes(e.id));
    if (c.exhibit_order) {
      const rank = (e) => { const i = c.exhibit_order.indexOf(e.id); return i < 0 ? 99 : i; };
      ex = ex.slice().sort((a, b) => rank(a) - rank(b));
    }
    return ex;
  }
  function defaultExTitle(e, k) { return e && e.wide ? 'Surroundings' : `Exhibit ${k + 1}`; }
  function thumbFor(w) {
    const c = cur(w.id);
    if (c.thumb) return c.thumb;
    if (c.exhibit_order && c.exhibit_order.length) return `data/${w.id}/${c.exhibit_order[0]}-thumb.webp`;
    return w.thumb;
  }
  function title(w) { return cur(w.id).title || w.folder || w.level_name; }
  function dateLabel(w) {
    const c = cur(w.id);
    if (c.era) return c.era;
    const d = w.dates;
    if (!d) return 'Date unknown';
    const a = monthYear(d.first), b = monthYear(d.last);
    return a && b && a !== b ? `${a} – ${b}` : b || a;
  }
  function sortKey(w) {
    const c = cur(w.id);
    if (c.order != null) return c.order;
    return (w.dates && (w.dates.last || w.dates.first)) || '9999';
  }
  function catNo(w) { return `WA-${String(state.order.indexOf(w.id) + 1).padStart(3, '0')}`; }
  function editionBadge(w) { return `<span class="badge ${w.edition.toLowerCase()}">${esc(w.edition)}</span>`; }
  function subtitle(w) { return [`${w.edition} ${w.version}`, w.game_mode, w.generator === 'Superflat' || w.generator === 'Flat' ? 'Superflat' : null].filter(Boolean).join(' · '); }

  // ------------------------------------------------------------------ boot
  async function boot() {
    try {
      const [index, curation] = await Promise.all([
        getJSON('data/worlds.json'),
        getJSON('curation.json').catch(() => ({})),
      ]);
      state.index = index;
      state.curation = curation;
      const worlds = index.worlds.slice().sort((a, b) => (sortKey(a) < sortKey(b) ? -1 : sortKey(a) > sortKey(b) ? 1 : 0));
      state.index.worlds = worlds;
      state.order = worlds.map((w) => w.id);
      nav.innerHTML = `<a href="#/">The Hall</a><a href="#/world/${worlds[0]?.id || ''}">Begin the tour →</a>`;
      route();
    } catch (e) {
      app.innerHTML = `<div class="error">The archive could not be opened.<br><small>${esc(e.message)}</small><br><small>Serve the <code>web</code> folder over HTTP — e.g. <code>python -m http.server -d web</code></small></div>`;
    }
  }
  window.addEventListener('hashchange', route);

  function route() {
    const h = location.hash.replace(/^#\/?/, '');
    const parts = h.split('/');
    closeLightbox();
    if (parts[0] === 'world' && parts[1]) return showWorld(parts[1], parts[2]);
    showHall();
  }

  // ------------------------------------------------------------------ the hall
  function showHall() {
    document.title = 'The World Archive';
    const ws = state.index.worlds;
    const col = state.curation.collection || {};
    const totalChunks = ws.reduce((a, w) => a + (w.chunks || 0), 0);
    const years = ws.flatMap((w) => [w.dates?.first, w.dates?.last]).filter(Boolean).map((d) => +d.slice(0, 4));
    const span = years.length ? (Math.min(...years) === Math.max(...years) ? `${Math.min(...years)}` : `${Math.min(...years)}–${Math.max(...years)}`) : '';

    const wings = (col.wings || []).slice();
    const assigned = new Set();
    const groups = wings.map((wg) => {
      const items = ws.filter((w) => cur(w.id).wing === wg.id);
      items.forEach((w) => assigned.add(w.id));
      return { ...wg, items };
    }).filter((g) => g.items.length);
    const rest = ws.filter((w) => !assigned.has(w.id));
    if (rest.length) groups.push({ id: 'misc', title: groups.length ? 'Other Worlds' : 'The Collection', intro: '', items: rest });

    app.innerHTML = `
      <section class="hall-hero">
        <div class="eyebrow">${esc(col.eyebrow || 'A museum of saved worlds')}</div>
        <h1>${esc(col.title || 'The World Archive')}</h1>
        <p>${esc(col.intro || 'Minecraft worlds built as a kid and a teenager, recovered from old save files and preserved as dioramas. Pick a world to step inside.')}</p>
        <div class="hall-stats">
          <div><b>${ws.length}</b><span>Worlds</span></div>
          <div><b>${span || '—'}</b><span>Years</span></div>
          <div><b>${compact(totalChunks * 256)}</b><span>m² explored</span></div>
          <div><b>${ws.reduce((a, w) => a + Math.max(0, (w.exhibits_count || 0) - (cur(w.id).hide_exhibits || []).length), 0)}</b><span>Dioramas</span></div>
        </div>
      </section>
      <div class="wing">
        <div class="wing-head"><h2>Timeline</h2><span class="wing-meta">Ordered by when each world was last saved</span></div>
        <div class="timeline">
          ${ws.map((w) => `<a class="tl-item" href="#/world/${w.id}"><div class="tl-dot"></div><b>${esc(title(w))}</b><span>${esc(dateLabel(w))}</span></a>`).join('')}
        </div>
      </div>
      ${groups.map((g) => `
        <section class="wing">
          <div class="wing-head"><h2>${esc(g.title)}</h2><span class="wing-meta">${g.items.length} world${g.items.length > 1 ? 's' : ''}</span></div>
          ${g.intro ? `<p class="wing-intro">${esc(g.intro)}</p>` : ''}
          <div class="frames">${g.items.map(frameCard).join('')}</div>
        </section>`).join('')}
    `;
    window.scrollTo(0, 0);
  }

  function frameCard(w) {
    const c = cur(w.id);
    return `
      <a class="frame" href="#/world/${w.id}">
        <div class="frame-art">
          <span class="cat">${catNo(w)}</span>
          <span class="ed">${editionBadge(w)}</span>
          ${thumbFor(w) ? `<img src="${esc(thumbFor(w))}" alt="Isometric diorama of ${esc(title(w))}" loading="lazy">` : ''}
        </div>
        <div class="frame-plaque">
          <h3>${esc(title(w))}</h3>
          <div class="sub">${esc(subtitle(w))} · ${esc(dateLabel(w))}</div>
          ${c.summary || c.description ? `<div class="blurb">${esc(c.summary || stripTags(c.description))}</div>` : ''}
        </div>
      </a>`;
  }
  const stripTags = (s) => String(s || '').replace(/<[^>]+>/g, '');

  // ------------------------------------------------------------------ world page
  async function showWorld(id, exhibitId) {
    const summary = state.index.worlds.find((w) => w.id === id);
    if (!summary) { app.innerHTML = `<div class="error">No world called “${esc(id)}” in the archive.</div>`; return; }
    if (!state.worlds[id]) {
      app.innerHTML = `<div class="loading">Bringing “${esc(title(summary))}” up from storage…</div>`;
      try { state.worlds[id] = await getJSON(`data/${id}/world.json`); } catch (e) { app.innerHTML = `<div class="error">Could not load this world. ${esc(e.message)}</div>`; return; }
    }
    const w = state.worlds[id];
    const c = cur(id);
    document.title = `${title(summary)} — The World Archive`;
    const i = state.order.indexOf(id);
    const prev = state.order[i - 1], next = state.order[i + 1];
    const exhibits = exhibitsFor(w);
    const exIdx = Math.max(0, exhibits.findIndex((e) => e.id === exhibitId));
    const exTitle = (e, k) => (c.exhibits?.[e.id]?.title) || defaultExTitle(e, k);

    const playTicks = (w.players || []).reduce((a, p) => a + (p.play_ticks || 0), 0);
    const host = (w.players || []).find((p) => p.name === 'You');

    app.innerHTML = `
      <div class="world">
        <div class="crumbs">
          <a href="#/">The Hall</a><span>/</span><span>${catNo(summary)}</span>
          <div class="pager">
            ${prev ? `<a class="btn" href="#/world/${prev}" title="Previous world">← ${esc(title(state.index.worlds[i - 1]))}</a>` : ''}
            ${next ? `<a class="btn" href="#/world/${next}" title="Next world">${esc(title(state.index.worlds[i + 1]))} →</a>` : ''}
          </div>
        </div>
        <div class="world-grid">
          <div>
            <div class="stage" id="stage"></div>
            ${exhibits.length > 1 ? `<div class="exhibit-tabs">${exhibits.map((e, k) => `
              <button class="ex-tab ${k === exIdx ? 'active' : ''}" data-ex="${k}">
                ${e.thumb ? `<img src="${esc(e.thumb)}" alt="">` : ''}
                <div><b>${esc(exTitle(e, k))}</b><span>${e.w}×${e.d} blocks · ${compact(e.built_blocks)} built</span></div>
              </button>`).join('')}</div>` : ''}
            <div class="exhibit-notes" id="exnotes"></div>
          </div>
          <aside class="placard">
            ${w.icon ? `<img class="icon" src="${esc(w.icon)}" alt="World icon">` : ''}
            <div class="cat">${catNo(summary)}</div>
            <h1>${esc(title(summary))}</h1>
            <div class="ital">${esc(dateLabel(summary))}</div>
            ${c.description ? `<div class="desc">${c.description.split(/\n\n+/).map((p) => `<p>${p}</p>`).join('')}</div>` : ''}
            <dl>
              <dt>Edition</dt><dd>${esc(w.edition)} Edition ${esc(w.version)}</dd>
              <dt>Mode</dt><dd>${esc(w.game_mode)}${w.hardcore ? ' (Hardcore)' : ''}${w.cheats ? ' · cheats on' : ''}</dd>
              <dt>World type</dt><dd>${esc(w.generator || '—')}</dd>
              <dt>Save name</dt><dd>${esc(w.folder)}${w.level_name && w.level_name !== w.folder ? ` <span style="opacity:.6">(“${esc(w.level_name)}”)</span>` : ''}</dd>
              ${w.dates ? `<dt>Saved</dt><dd>${w.dates.first && w.dates.first !== w.dates.last ? `${esc(fullDate(w.dates.first))} → ` : ''}${esc(fullDate(w.dates.last))}</dd>` : ''}
              <dt>World age</dt><dd>${fmt(Math.round(w.world_ticks / 24000))} Minecraft days (${fmtHours(hours(w.world_ticks))})</dd>
              ${playTicks ? `<dt>Play time</dt><dd>${fmtHours(hours(playTicks))} across ${w.players.length} player${w.players.length > 1 ? 's' : ''}</dd>` : `<dt>Players</dt><dd>${(w.players || []).length || '—'}</dd>`}
              <dt>Explored</dt><dd>${fmt(w.chunks)} chunks · ${w.area_km2} km²</dd>
              <dt>Spawn</dt><dd>${(w.spawn || []).map(fmt).join(', ')}</dd>
              <dt>Seed</dt><dd style="font-family:var(--pixel);font-size:16px">${esc(w.seed)}</dd>
              ${w.dimensions?.length ? `<dt>Visited</dt><dd>Overworld, ${esc(w.dimensions.join(', '))}</dd>` : ''}
            </dl>
            ${w.dates ? '' : ''}
            <div class="note">${w.edition === 'Java' ? 'Dates come from the save timestamps of chunks that haven’t been touched since; “World age” is in-game time.' : 'The date is when the world was last opened; “World age” is in-game time.'}</div>
          </aside>
        </div>
        ${mapSection(w)}
        ${artifactsSection(w)}
        ${censusSection(w)}
        ${visitorsSection(w)}
      </div>`;

    // viewer
    const stageEl = document.getElementById('stage');
    const stage = new Stage(stageEl, { onExpand: () => openLightbox(w, stage.exhibit, stage.rot) });
    const showExhibit = (k, scroll) => {
      const e = exhibits[k];
      if (!e) { stageEl.innerHTML = '<div class="loading">No renders for this world yet.</div>'; return; }
      stage.load(e, `${exTitle(e, k)}`, `${e.w}×${e.d} blocks around ${fmt(e.x0 + e.w / 2)}, ${fmt(e.z0 + e.d / 2)}`);
      document.querySelectorAll('.ex-tab').forEach((t) => t.classList.toggle('active', +t.dataset.ex === k));
      document.querySelectorAll('.map-mark').forEach((t) => t.classList.toggle('active', +t.dataset.ex === k));
      document.getElementById('exnotes').innerHTML = exhibitNotes(w, e, k, c);
      history.replaceState(null, '', `#/world/${id}/${e.id}`);
      if (scroll) stageEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    };
    showExhibit(exIdx);
    document.querySelectorAll('.ex-tab').forEach((t) => t.addEventListener('click', () => showExhibit(+t.dataset.ex)));
    document.querySelectorAll('.map-mark').forEach((t) => t.addEventListener('click', () => showExhibit(+t.dataset.ex, true)));
    wireBooks(app);
    window.scrollTo(0, 0);
  }

  function exhibitNotes(w, e, k, c) {
    const note = c.exhibits?.[e.id]?.caption;
    const mats = (e.materials || []).slice(0, 8);
    const max = Math.max(1, ...mats.map((m) => m[1]));
    return `
      <div class="card">
        <h3>${esc(c.exhibits?.[e.id]?.title || defaultExTitle(e, k))}</h3>
        ${note ? `<p>${note}</p>` : e.wide ? `<p>A wider, lower-detail view of the 512×512 blocks around the main build site, for context.</p>` : `<p>One of the most built-up or most visited parts of the world, picked automatically from where players spent their time and placed blocks.</p>`}
        <p class="muted" style="margin-top:10px">
          ${fmt(e.built_blocks)} building blocks · 
          ${e.sign_count ? `${e.sign_count} sign${e.sign_count > 1 ? 's' : ''} · ` : ''}y ${e.y_range ? e.y_range.join('–') : ''}
        </p>
      </div>
      <div class="card">
        <h3>Materials on display</h3>
        <div class="bars">${mats.map((m) => bar(m, max)).join('') || '<span class="muted">No building blocks detected.</span>'}</div>
      </div>`;
  }

  function bar([label, n, color], max) {
    return `<div class="bar"><div class="label"><span class="sw" style="background:${color}"></span>${esc(label)}</div>
      <div class="track"><div class="fill" style="width:${Math.max(1.5, (n / max) * 100)}%;background:${color}"></div></div>
      <div class="num">${compact(n)}</div></div>`;
  }

  // ------------------------------------------------------------------ sections
  function mapSection(w) {
    const m = w.map;
    if (!m) return '';
    const pct = (x, z) => [((x - m.x0) / m.scale / m.w) * 100, ((z - m.z0) / m.scale / m.h) * 100];
    const inside = ([l, t]) => l >= 0 && l <= 100 && t >= 0 && t <= 100;
    const marks = exhibitsFor(w).map((e, k) => {
      const [l, t] = pct(e.x0, e.z0);
      const ww = (e.w / m.scale / m.w) * 100, hh = (e.d / m.scale / m.h) * 100;
      const name = cur(w.id).exhibits?.[e.id]?.title || defaultExTitle(e, k);
      return `<div class="map-mark" data-ex="${k}" style="left:${l}%;top:${t}%;width:${ww}%;height:${hh}%" title="${esc(name)}"><span>${k + 1}</span></div>`;
    }).join('');
    const sp = pct(w.spawn[0], w.spawn[2]);
    const pins = [];
    if (inside(sp)) pins.push(`<div class="map-pin spawn" style="left:${sp[0]}%;top:${sp[1]}%" title="World spawn"></div>`);
    (w.players || []).forEach((p, k) => {
      if (p.dimension && p.dimension !== 0 && p.dimension !== 'minecraft:overworld') return;
      const q = pct(p.pos[0], p.pos[2]);
      if (inside(q)) pins.push(`<div class="map-pin player" style="left:${q[0]}%;top:${q[1]}%" title="${esc(playerName(p, k))} — last seen here"></div>`);
    });
    const blocksAcross = Math.round(m.w * m.scale);
    return `
      <section class="section">
        <div class="section-head"><h2>Survey Map</h2><span class="meta">${fmt(m.chunks_in_view)} chunks · ${fmt(blocksAcross)} blocks across${m.clusters > 1 ? ` · ${m.clusters - 1} far-flung area${m.clusters > 2 ? 's' : ''} not shown` : ''}</span></div>
        <div class="map-wrap">
          <div class="map-frame"><div class="map-inner" style="width:min(100%, ${(78 * m.w / m.h).toFixed(2)}vh)"><img src="${esc(m.src)}" alt="Top-down map" loading="lazy">${marks}${pins.join('')}</div></div>
          <div class="legend">
            <p class="muted" style="margin:0 0 6px;color:var(--ink-3)">A top-down view of the main explored region${m.cropped ? ' (cropped to the area around the main build — the full explored area is much larger)' : ''}, drawn from the topmost block of every column. North is up.</p>
            <div class="row"><span class="sw" style="border:2px solid var(--gold-2)"></span>Exhibit area — click to view</div>
            <div class="row"><span class="sw" style="background:#e24b4b;border-radius:50%"></span>World spawn</div>
            <div class="row"><span class="sw" style="background:var(--accent);border-radius:50%"></span>Where a player last logged off</div>
            ${m.clusters > 1 ? `<p style="color:var(--ink-3);font-size:12.5px">This save also has ${m.clusters - 1} separate patch${m.clusters > 2 ? 'es' : ''} of terrain far from the main area (teleports, glitches or long journeys).</p>` : ''}
          </div>
        </div>
      </section>`;
  }

  function artifactsSection(w) {
    const signs = (w.signs_sample || [])
      .map((s) => ({ ...s, lines: s.lines.map((l) => String(l).replace(/§./g, '')) }))
      .filter((s) => s.lines.some((l) => /[\p{L}\p{N}]/u.test(l)))
      .filter((s) => !(cur(w.id).hide_signs || []).includes(s.pos.join(',')));
    const books = w.books || [];
    const containers = (w.exhibits || []).flatMap((e) => e.containers || []).sort((a, b) => b.total - a.total).slice(0, 8);
    const named = w.named || [];
    if (!signs.length && !books.length && !containers.length && !named.length) return '';
    return `
      <section class="section">
        <div class="section-head"><h2>Artifacts</h2><span class="meta">${fmt(w.container_count)} filled containers</span></div>
        <p class="section-intro">Things left behind in the world — read straight out of the save file. (Sign text, books and custom names are left out to keep players' personal details private.)</p>
        ${signs.length ? `<h3 style="font-size:22px;margin:0 0 16px;color:var(--ink-2)">Signs</h3>
          <div class="signs">${signs.slice(0, 48).map((s) => `<div><div class="sign">${s.lines.map((l) => `<div class="line">${esc(l)}</div>`).join('')}</div><div class="sign-pos">${s.pos.join(' ')}</div></div>`).join('')}</div>
          ${signs.length > 48 ? `<p class="muted" style="color:var(--ink-3)">…and ${signs.length - 48} more.</p>` : ''}` : ''}
        ${books.length ? `<h3 style="font-size:22px;margin:36px 0 16px;color:var(--ink-2)">Books</h3>
          <div class="cards">${books.map((b, k) => bookCard(b, k)).join('')}</div>` : ''}
        ${containers.length ? `<h3 style="font-size:22px;margin:36px 0 16px;color:var(--ink-2)">Fullest chests</h3>
          <div class="cards">${containers.map((ch) => `
            <div class="card chest"><h3>${esc(cap(ch.type.replace(/_/g, ' ')))}</h3><div class="muted">${fmt(ch.total)} items · at ${ch.pos.join(', ')}</div>
            <ul>${ch.items.map(([n, c]) => `<li>${esc(n.replace(/_/g, ' '))}<b>×${fmt(c)}</b></li>`).join('')}</ul></div>`).join('')}</div>` : ''}
        ${named.length ? `<h3 style="font-size:22px;margin:36px 0 16px;color:var(--ink-2)">Named residents</h3>
          <div class="chips">${named.map((n) => `<span class="chip">“${esc(n.name)}”<b>${esc(n.type.replace(/_/g, ' '))}${n.count > 1 ? ` ×${n.count}` : ''}</b></span>`).join('')}</div>` : ''}
      </section>`;
  }

  function bookCard(b, k) {
    const pages = (b.pages || []).map((p) => String(p));
    return `<div class="book" data-book='${esc(JSON.stringify(pages))}'>
      <h3>${esc(b.title || 'Book & Quill')}</h3>
      <div class="by">${b.author ? `by ${esc(b.author)}` : 'unsigned'}</div>
      <div class="page">${esc(pages[0] || '(blank)')}</div>
      <div class="pager"><button data-d="-1" aria-label="Previous page">‹</button><span>1 / ${Math.max(1, pages.length)}</span><button data-d="1" aria-label="Next page">›</button></div>
    </div>`;
  }
  function wireBooks(root) {
    root.querySelectorAll('.book').forEach((b) => {
      let pages; try { pages = JSON.parse(b.dataset.book); } catch { pages = []; }
      let i = 0;
      b.querySelectorAll('button').forEach((btn) => btn.addEventListener('click', () => {
        i = Math.min(Math.max(0, i + +btn.dataset.d), Math.max(0, pages.length - 1));
        b.querySelector('.page').textContent = pages[i] || '(blank)';
        b.querySelector('.pager span').textContent = `${i + 1} / ${Math.max(1, pages.length)}`;
      }));
    });
  }

  function censusSection(w) {
    const built = w.built_blocks || [];
    const top = w.top_blocks || [];
    if (!built.length && !top.length) return '';
    const mb = Math.max(1, ...built.map((b) => b[1]));
    const mt = Math.max(1, ...top.map((b) => b[1]));
    const ents = (w.entities || []).filter(([n]) => !['item', 'xp_orb', 'arrow', 'falling_block'].includes(n));
    return `
      <section class="section">
        <div class="section-head"><h2>Census</h2><span class="meta">Every block in every explored chunk, counted</span></div>
        <div class="census">
          <div><h3>Building materials</h3><div class="bars">${built.slice(0, 14).map((b) => bar(b, mb)).join('')}</div></div>
          <div><h3>The whole world</h3><div class="bars">${top.slice(0, 14).map((b) => bar(b, mt)).join('')}</div></div>
        </div>
        ${ents.length ? `<h3 style="font-size:20px;margin:32px 0 14px;color:var(--ink-2)">Creatures & objects still in the world</h3>
          <div class="chips">${ents.map(([n, c]) => `<span class="chip">${esc(n.replace(/_/g, ' ').replace(/^minecraft:/, ''))}<b>${fmt(c)}</b></span>`).join('')}</div>` : ''}
      </section>`;
  }

  function playerName(p, k) {
    if (p.name) return p.name;
    if (p.host) return 'Host';
    return `Player ${k + 1}`;
  }

  function visitorsSection(w) {
    const ps = w.players || [];
    if (!ps.length) return '';
    return `
      <section class="section">
        <div class="section-head"><h2>Visitors</h2><span class="meta">${ps.length} player${ps.length > 1 ? 's' : ''} left a save file here</span></div>
        <div class="cards">${ps.map((p, k) => `
          <div class="card visitor">
            <h3>${esc(playerName(p, k))}${p.name === 'You' ? '<span class="you">that’s you</span>' : ''}</h3>
            <div class="muted">${esc(p.game_mode)} · level ${p.xp_level} · last at ${p.pos.join(', ')}</div>
            ${p.play_ticks != null ? `<div class="stat-grid">
              <div><span>Played</span><b>${fmtHours(hours(p.play_ticks || 0))}</b></div>
              <div><span>Items used</span><b>${compact(p.blocks_placed || 0)}</b></div>
              <div><span>Mined</span><b>${compact(p.blocks_mined || 0)}</b></div>
              <div><span>Crafted</span><b>${compact(p.items_crafted || 0)}</b></div>
              <div><span>Walked</span><b>${compact(p.walked_m || 0)} m</b></div>
              <div><span>Flown</span><b>${compact(p.flown_m || 0)} m</b></div>
              <div><span>Jumps</span><b>${compact(p.jumps || 0)}</b></div>
              <div><span>Deaths</span><b>${fmt(p.deaths || 0)}</b></div>
            </div>` : ''}
            ${p.inventory?.length ? `<div class="inv">${p.inventory.slice(0, 10).map(([n, c]) => `<span>${esc(String(n).replace(/_/g, ' '))}${c > 1 ? ` ×${c}` : ''}</span>`).join('')}</div>` : ''}
          </div>`).join('')}</div>
      </section>`;
  }

  // ------------------------------------------------------------------ the diorama stage (pan / zoom / rotate)
  const NORTH_ANGLE = [63, 117, 243, 297];

  class Stage {
    constructor(root, opts = {}) {
      this.root = root;
      this.opts = opts;
      this.rot = 0;
      this.s = 1; this.tx = 0; this.ty = 0;
      root.innerHTML = `
        <div class="stage-canvas"><img alt="Isometric render" draggable="false"></div>
        <div class="stage-caption"></div>
        <div class="compass" title="Compass"><div class="needle"><span class="n">N</span><span class="s">S</span></div></div>
        <div class="stage-hint">Drag to pan · ${opts.wheelZoom ? 'scroll' : 'Ctrl + scroll'} to zoom<br>Double-click to zoom in · R to rotate</div>
        <div class="stage-toolbar">
          <div class="group">
            <button class="btn icon" data-a="rotl" title="Rotate left (Shift+R)">⟲</button>
            <button class="btn icon" data-a="rotr" title="Rotate right (R)">⟳</button>
          </div>
          <div class="group">
            <button class="btn icon" data-a="out" title="Zoom out (−)">−</button>
            <button class="btn" data-a="fit" title="Fit (0)">Fit</button>
            <button class="btn icon" data-a="in" title="Zoom in (+)">+</button>
          </div>
          <div class="spacer"></div>
          ${opts.onExpand ? `<div class="group"><button class="btn" data-a="expand" title="Full screen (F)">⤢ Full screen</button></div>` : ''}
        </div>`;
      this.canvas = root.querySelector('.stage-canvas');
      this.img = root.querySelector('img');
      this.caption = root.querySelector('.stage-caption');
      this.needle = root.querySelector('.needle');
      root.querySelectorAll('[data-a]').forEach((b) => b.addEventListener('click', () => this.action(b.dataset.a)));
      this.img.addEventListener('load', () => { if (this.pendingFit) { this.fit(); this.pendingFit = false; } });
      this.bind();
      this.ro = new ResizeObserver(() => this.fit());
      this.ro.observe(root);
      this.onKey = (e) => {
        if (!document.body.contains(root)) { document.removeEventListener('keydown', this.onKey); return; }
        if (e.target.closest && e.target.closest('input,textarea')) return;
        if (lightbox.hidden === false && !lightbox.contains(root)) return;
        if (e.key === 'r' || e.key === 'R') this.action(e.shiftKey ? 'rotl' : 'rotr');
        else if (e.key === '+' || e.key === '=') this.action('in');
        else if (e.key === '-') this.action('out');
        else if (e.key === '0') this.action('fit');
        else if ((e.key === 'f' || e.key === 'F') && this.opts.onExpand) this.action('expand');
      };
      document.addEventListener('keydown', this.onKey);
    }

    load(exhibit, title, sub, rot = 0) {
      this.exhibit = exhibit;
      this.rot = rot;
      this.caption.innerHTML = `${esc(title)}<small>${esc(sub || '')}</small>`;
      this.show();
    }
    show() {
      const v = this.exhibit.views[this.rot];
      this.view = v;
      this.pendingFit = true;
      this.img.src = v.src;
      this.needle.style.transform = `rotate(${NORTH_ANGLE[this.rot]}deg)`;
      if (this.img.complete && this.img.naturalWidth) { this.fit(); this.pendingFit = false; }
    }
    fit() {
      if (!this.view) return;
      const r = this.canvas.getBoundingClientRect();
      const pad = 40;
      this.s = Math.min((r.width - pad * 2) / this.view.w, (r.height - pad * 2 - 40) / this.view.h);
      this.fitScale = this.s;
      this.tx = (r.width - this.view.w * this.s) / 2;
      this.ty = (r.height - 40 - this.view.h * this.s) / 2 + 10;
      this.apply();
    }
    apply() {
      this.img.style.width = this.view.w + 'px';
      this.img.style.height = this.view.h + 'px';
      this.img.style.transform = `translate(${this.tx}px, ${this.ty}px) scale(${this.s})`;
      this.img.classList.toggle('pixelated', this.s >= 1.5);
    }
    zoomAt(factor, cx, cy) {
      const ns = Math.min(Math.max(this.s * factor, (this.fitScale || 0.1) * 0.5), 12);
      const f = ns / this.s;
      this.tx = cx - (cx - this.tx) * f;
      this.ty = cy - (cy - this.ty) * f;
      this.s = ns;
      this.apply();
    }
    nudgeHint() {
      const h = this.root.querySelector('.stage-hint');
      if (!h) return;
      h.classList.add('flash');
      clearTimeout(this._hintT);
      this._hintT = setTimeout(() => h.classList.remove('flash'), 900);
    }
    action(a) {
      const r = this.canvas.getBoundingClientRect();
      if (a === 'rotr') { this.rot = (this.rot + 1) % 4; this.show(); }
      else if (a === 'rotl') { this.rot = (this.rot + 3) % 4; this.show(); }
      else if (a === 'in') this.zoomAt(1.5, r.width / 2, r.height / 2);
      else if (a === 'out') this.zoomAt(1 / 1.5, r.width / 2, r.height / 2);
      else if (a === 'fit') this.fit();
      else if (a === 'expand') this.opts.onExpand?.();
      else if (a === 'close') this.opts.onClose?.();
    }
    bind() {
      const c = this.canvas;
      const pts = new Map();
      let last = null, pinch = null;
      c.addEventListener('wheel', (e) => {
        // On the page, plain scrolling should scroll the page; zoom needs Ctrl/⌘ (or a trackpad pinch).
        if (!this.opts.wheelZoom && !e.ctrlKey && !e.metaKey) { this.nudgeHint(); return; }
        e.preventDefault();
        const r = c.getBoundingClientRect();
        this.zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
      }, { passive: false });
      c.addEventListener('dblclick', (e) => {
        const r = c.getBoundingClientRect();
        this.zoomAt(2, e.clientX - r.left, e.clientY - r.top);
      });
      c.addEventListener('pointerdown', (e) => {
        c.setPointerCapture(e.pointerId);
        pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
        c.classList.add('dragging');
        last = { x: e.clientX, y: e.clientY };
        if (pts.size === 2) {
          const [a, b] = [...pts.values()];
          pinch = { d: Math.hypot(a.x - b.x, a.y - b.y) };
        }
      });
      c.addEventListener('pointermove', (e) => {
        if (!pts.has(e.pointerId)) return;
        pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
        if (pts.size === 2 && pinch) {
          const [a, b] = [...pts.values()];
          const d = Math.hypot(a.x - b.x, a.y - b.y);
          const r = c.getBoundingClientRect();
          this.zoomAt(d / pinch.d, (a.x + b.x) / 2 - r.left, (a.y + b.y) / 2 - r.top);
          pinch.d = d;
          return;
        }
        if (last) {
          this.tx += e.clientX - last.x;
          this.ty += e.clientY - last.y;
          last = { x: e.clientX, y: e.clientY };
          this.apply();
        }
      });
      const up = (e) => {
        pts.delete(e.pointerId);
        if (pts.size < 2) pinch = null;
        if (!pts.size) { c.classList.remove('dragging'); last = null; }
        else { const p = [...pts.values()][0]; last = { x: p.x, y: p.y }; }
      };
      c.addEventListener('pointerup', up);
      c.addEventListener('pointercancel', up);
    }
  }

  function openLightbox(w, exhibit, rot) {
    lightbox.hidden = false;
    lightbox.innerHTML = '<button class="btn close" title="Close (Esc)">✕ Close</button><div class="stage"></div>';
    const st = new Stage(lightbox.querySelector('.stage'), { wheelZoom: true });
    const k = exhibitsFor(w).indexOf(exhibit);
    st.load(exhibit, cur(w.id).exhibits?.[exhibit.id]?.title || defaultExTitle(exhibit, k), title(w), rot);
    lightbox.querySelector('.close').addEventListener('click', closeLightbox);
    document.body.style.overflow = 'hidden';
  }
  function closeLightbox() {
    if (lightbox.hidden) return;
    lightbox.hidden = true;
    lightbox.innerHTML = '';
    document.body.style.overflow = '';
  }
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeLightbox();
    if (!lightbox.hidden) return;
    const m = location.hash.match(/^#\/world\/([^/]+)/);
    if (!m || (e.target.closest && e.target.closest('input,textarea'))) return;
    const i = state.order.indexOf(m[1]);
    if (e.key === 'ArrowRight' && state.order[i + 1]) location.hash = `#/world/${state.order[i + 1]}`;
    if (e.key === 'ArrowLeft' && state.order[i - 1]) location.hash = `#/world/${state.order[i - 1]}`;
  });

  boot();
})();
