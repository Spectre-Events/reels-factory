/* Construit le reel à partir de window.REEL et expose window.__seek(t).
   Toute l'animation vit dans une seule frise GSAP en pause : chaque image est une fonction pure du temps. */
(async () => {
  const R = window.REEL, T = R.timing, PITCH = 1936, SQ = 88, NS = 'http://www.w3.org/2000/svg';
  const sheet = document.getElementById('sheet'), caps = document.getElementById('captions');
  const tl = gsap.timeline({ paused: true });

  await Promise.all([document.fonts.load('800 100px "Archivo"'), document.fonts.load('400 38px "Playwrite FR"')]);

  // aléa déterministe : deux rendus du même script donnent les mêmes traits de stylo
  let seed = 20231115;
  const rnd = (a, b) => { seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return a + ((t ^ t >>> 14) >>> 0) / 4294967296 * (b - a); };

  const el = (tag, cls, parent, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; if (parent) parent.appendChild(e); return e; };
  const svgEl = (tag, attrs, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
  const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const mk = s => esc(s).replace(/==(.+?)==/g, '<span class="hl"><i></i>$1</span>').replace(/~~(.+?)~~/g, '<span class="st">$1</span>').replace(/__(.+?)__/g, '<span class="ul">$1</span>');
  const plain = s => s.replace(/==|~~|__/g, '');

  // ---------- repères temporels : « quand la voix dit tel mot »
  const norm = s => s.toLowerCase().replace(/[  ]/g, '').replace(/[^\p{L}\p{N}]+/gu, '');
  const forms = w => [norm(w), norm(w.split(/['’]/).pop())];
  function cue(si, phrase, fallback) {
    if (!phrase) return fallback;
    const words = T.scenes[si].words, want = phrase.split(/\s+/).map(norm).filter(Boolean);
    for (let i = 0; i + want.length <= words.length; i++) {
      if (want.every((p, k) => forms(words[i + k].t).includes(p))) return words[i].s;
    }
    console.warn('repère introuvable dans la scène ' + (si + 1) + ' : « ' + phrase + ' »');
    return fallback;
  }

  // ---------- gestes d'écriture
  function writeOn(node, t, chars) {
    const d = Math.min(.7, Math.max(.2, chars * .026));
    gsap.set(node, { clipPath: 'inset(-16px 100% -16px -30px)' });
    tl.to(node, { clipPath: 'inset(-16px -30px -16px -30px)', duration: d, ease: 'power1.out' }, t);
    return t + d;
  }
  function pen(scene, x1, y1, x2, y2, t, d = .34, bulge = 7) {
    const mx = (x1 + x2) / 2 + rnd(-10, 10), my = (y1 + y2) / 2 - bulge + rnd(-3, 3);
    const p = svgEl('path', { d: `M${x1.toFixed(1)} ${y1.toFixed(1)} Q${mx.toFixed(1)} ${my.toFixed(1)} ${x2.toFixed(1)} ${y2.toFixed(1)}`, class: 'pen' }, scene._ink);
    const L = p.getTotalLength() + 2;
    gsap.set(p, { strokeDasharray: L, strokeDashoffset: L, autoAlpha: 0 });
    tl.set(p, { autoAlpha: 1 }, t).to(p, { strokeDashoffset: 0, duration: d, ease: 'power2.out' }, t);
    return t + d;
  }
  function marks(scene, node, t) {
    const sr = scene.getBoundingClientRect();
    node.querySelectorAll('.hl > i').forEach((i, k) => {
      gsap.set(i, { rotation: rnd(-.9, .5), scaleX: 0 });
      tl.to(i, { scaleX: 1, duration: .34, ease: 'power2.out' }, t + k * .12);
    });
    node.querySelectorAll('.st').forEach((s, k) => {
      const r = s.getBoundingClientRect(), y = r.top - sr.top + r.height * .54;
      pen(scene, r.left - sr.left - 6, y + rnd(2, 8), r.right - sr.left + 10, y - rnd(2, 8), t + k * .15, .5, 4);
    });
    node.querySelectorAll('.ul').forEach((s, k) => {
      const r = s.getBoundingClientRect(), y = r.bottom - sr.top - r.height * .08;
      pen(scene, r.left - sr.left - 4, y, r.right - sr.left + 8, y - rnd(0, 5), t + k * .15, .32, -5);
    });
  }
  function lines(parent, arr, t) {
    let last = t;
    const nodes = arr.map(s => el('span', 'ln', parent, mk(s)));
    nodes.forEach((n, i) => { last = writeOn(n, last + (i ? .05 : 0), plain(arr[i]).length); });
    return { nodes, end: last };
  }
  function note(parent, arr, t) {
    const n = el('div', 'note', parent);
    lines(n, arr, t);
  }
  function fit(node, max) {  // réduit un nombre trop long pour la colonne
    const w = node.getBoundingClientRect().width;
    if (w > max) node.style.fontSize = (parseFloat(getComputedStyle(node).fontSize) * max / w).toFixed(1) + 'px';
  }

  // ---------- blocs
  function textBlock(scene, si, body, b, t) {
    const blk = el('div', 'blk k-' + b.kind + (b.blue ? ' blue' : ''), body);
    if (b.gap) blk.style.marginTop = b.gap * SQ + 'px';
    if (b.note) note(blk, b.note, Math.max(T.scenes[si].start, t - .15));
    const { nodes, end } = lines(blk, b.lines, t);
    if (b.kind === 'num') nodes.forEach(n => fit(n, 800));
    const tm = b.markAt ? Math.max(end, cue(si, b.markAt, end) - .1) : end + .08;
    scene._late.push(() => marks(scene, blk, tm));
    return end;
  }

  function timeline(scene, si, body, b, t) {
    const blk = el('div', 'blk timeline', body);
    if (b.gap) blk.style.marginTop = b.gap * SQ + 'px';
    let last = t;
    b.events.forEach(ev => {
      const te = Math.max(last + .1, cue(si, ev.at, last + .6) - .1);
      const e = el('div', 'ev', blk);
      const dot = el('div', 'dot', e);
      gsap.set(dot, { scale: 0 });
      tl.to(dot, { scale: 1, duration: .22, ease: 'back.out(2.2)' }, te);
      if (ev.note) note(e, ev.note, te);
      let end = lines(el('div', 't', e), ev.title, te + .08).end;
      if (ev.sub) end = lines(el('div', 's', e), ev.sub, end + .05).end;
      const tm = ev.markAt ? Math.max(end, cue(si, ev.markAt, end) - .1) : end + .08;
      scene._late.push(() => marks(scene, e, tm));
      last = end;
    });
    return last;
  }

  function chart(scene, si, body, b, t) {
    const sc = T.scenes[si];
    const c = el('div', 'blk chart', body);
    const off = (c.offsetTop + (b.gap || 0) * SQ) % SQ;      // le tracé doit tomber pile sur les carreaux
    c.style.marginTop = ((b.gap || 0) * SQ + (off ? SQ - off : 0)) + 'px';
    const X0 = 48, H = 616, DEC = 44;                       // origine calée sur une ligne verticale du papier
    const x = v => X0 + (v - b.x.from) * SQ, y = v => H - (Math.log10(v) - (b.y.fromExp || 0)) * DEC;
    const t0 = Math.max(sc.start, cue(si, b.at, t) - .1);

    writeOn(el('div', 'ctitle', c, esc(b.title)), t0, b.title.length);
    if (b.hint) writeOn(el('div', 'chint', c, esc(b.hint)), t0 + .3, b.hint.length);

    const svg = svgEl('svg', { viewBox: '0 0 800 616' }, c);
    const axis = svgEl('line', { x1: X0, y1: H, x2: x(b.x.to) + 14, y2: H, class: 'axis' }, svg);
    const AL = x(b.x.to) + 14 - X0;
    gsap.set(axis, { strokeDasharray: AL, strokeDashoffset: AL });
    tl.to(axis, { strokeDashoffset: 0, duration: .4, ease: 'power1.out' }, t0);
    b.x.ticks.forEach((v, i) => {
      const k = el('div', 'xtick', c, String(v)); k.style.left = x(v) + 'px';
      gsap.set(k, { autoAlpha: 0 }); tl.set(k, { autoAlpha: 1 }, t0 + .2 + i * .05);
    });
    b.y.ticks.forEach((k, i) => {
      const d = el('div', 'ytick', c, esc(k.label)); d.style.top = (88 + H - (k.exp - (b.y.fromExp || 0)) * DEC - 17) + 'px';
      gsap.set(d, { autoAlpha: 0 }); tl.set(d, { autoAlpha: 1 }, t0 + .3 + i * .08);
    });

    const pts = b.points.map(p => [x(p[0]), y(p[1])]);
    const path = seg => svgEl('path', { d: 'M' + seg.map(p => p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' L'), class: 'series' }, svg);
    const split = b.split == null ? pts.length - 1 : b.split;
    const tSpike = Math.max(t0 + 1.2, cue(si, b.spikeAt, sc.end - 1.2) - .25);
    const draw = (p, at, d, ease) => { const L = p.getTotalLength() + 2; gsap.set(p, { strokeDasharray: L, strokeDashoffset: L, autoAlpha: 0 }); tl.set(p, { autoAlpha: 1 }, at).to(p, { strokeDashoffset: 0, duration: d, ease }, at); };
    draw(path(pts.slice(0, split + 1)), t0 + .5, Math.max(.8, tSpike - t0 - .7), 'none');
    if (split < pts.length - 1) draw(path(pts.slice(split)), tSpike, .55, 'power2.in');

    const [ex, ey] = pts[pts.length - 1], tEnd = tSpike + .55;
    const dot = svgEl('circle', { cx: ex, cy: ey, r: 14, class: 'end' }, svg);
    gsap.set(dot, { scale: 0, transformOrigin: '50% 50%' });
    tl.to(dot, { scale: 1, duration: .25, ease: 'back.out(2.4)' }, tEnd);
    if (b.endLabel) {
      const lab = el('div', 'endlabel', c, mk(b.endLabel));
      lab.style.right = (800 - ex + 30) + 'px'; lab.style.top = (88 + ey - 36) + 'px';
      writeOn(lab, tEnd + .05, plain(b.endLabel).length);
      scene._late.push(() => marks(scene, lab, tEnd + .45));
    }
    if (b.endNote) {
      const n = el('div', 'endnote', c, esc(b.endNote));
      n.style.right = (800 - ex + 30) + 'px'; n.style.top = (88 + ey + 34) + 'px';
      writeOn(n, tEnd + .5, b.endNote.length);
    }
    return tEnd + .8;
  }

  // ---------- scènes : une seule longue feuille que l'on descend
  sheet.style.height = R.scenes.length * PITCH + 'px';
  R.scenes.forEach((s, si) => {
    const scene = el('section', 'scene', sheet); scene.style.top = si * PITCH + 'px';
    scene._ink = svgEl('svg', { class: 'ink' }, scene); scene._late = [];
    const body = el('div', 'body', scene);
    let t = T.scenes[si].start;
    (s.blocks || []).forEach(b => {
      const at = b.at ? cue(si, b.at, t) - .1 : (b.delay != null ? T.scenes[si].start + b.delay : t + .1);
      const start = Math.max(T.scenes[si].start - .05, at);
      if (b.kind === 'timeline') t = timeline(scene, si, body, b, start);
      else if (b.kind === 'chart') t = chart(scene, si, body, b, start);
      else t = textBlock(scene, si, body, b, start);
    });
    // centrage dans la zone sûre (264–1320 px), arrondi au carreau
    const top = s.top != null ? s.top * SQ : Math.max(264, Math.round((792 - body.offsetHeight / 2) / SQ) * SQ);
    body.style.top = top + 'px';
    if (top + body.offsetHeight > 1330) console.warn('scène ' + (si + 1) + ' : contenu trop haut (' + body.offsetHeight + ' px), il passe sous les sous-titres');
    scene._late.forEach(f => f());   // traits mesurés une fois la mise en page figée
  });
  T.cuts.forEach((c, i) => tl.to(sheet, { y: -(i + 1) * PITCH, duration: .5, ease: 'power3.inOut' }, c - .25));

  // ---------- sous-titres : 1 à 4 mots, le mot prononcé passe en jaune
  const all = T.scenes.flatMap(s => s.words);
  const groups = []; let cur = [], len = 0;
  const flush = () => { if (cur.length) groups.push(cur); cur = []; len = 0; };
  const weak = w => /^\d[\d\u202f]*$/.test(w.t) || (norm(w.t).length <= 3 && !/[.!?…:;,]$/.test(w.t));
  all.forEach((w, i) => {
    const L = w.t.length, pause = i ? w.s - all[i - 1].e > .3 : false;
    if (cur.length && pause) flush();
    else if (cur.length && (len + 1 + L > 22 || cur.length >= 4)) {
      const carry = [];                       // pas de petit mot ni de nombre orphelin en fin de groupe
      while (cur.length > 1 && weak(cur[cur.length - 1]) && carry.length < 2) carry.unshift(cur.pop());
      flush(); cur = carry; len = carry.reduce((a, x) => a + x.t.length + 1, -1); if (len < 0) len = 0;
    }
    cur.push(w); len += (len ? 1 : 0) + L;
    if (/[.!?…:;,]$/.test(w.t)) flush();
  });
  flush();
  groups.forEach((g, gi) => {
    const pill = el('div', 'pill', caps);
    const next = groups[gi + 1], endG = g[g.length - 1].e;
    const off = next && next[0].s - endG < .45 ? next[0].s : endG + .18;
    g.forEach(w => {
      const span = el('span', null, pill, esc(w.t) + ' ');
      tl.set(span, { color: '#FFE646' }, w.s).set(span, { color: '#FFFFFF' }, w.e);
    });
    pill.lastChild.innerHTML = pill.lastChild.innerHTML.trim();
    tl.set(pill, { visibility: 'visible' }, g[0].s).set(pill, { visibility: 'hidden' }, off);
  });

  tl.set({}, {}, T.total);
  window.__seek = t => { tl.time(Math.max(0, Math.min(t, T.total))); };   // ne rien renvoyer : la frise n'est pas sérialisable
  window.__seek(0);
  window.__ready = true;
})();
