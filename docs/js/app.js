/* Visor de documentación de Weapon Rebalancer. Sin dependencias; funciona abriendo index.html. */
(function () {
  'use strict';

  const docs = Array.isArray(window.WR_DOCS) ? window.WR_DOCS : [];
  const $ = (id) => document.getElementById(id);
  const el = {
    content: $('doc-content'), nav: $('docs-nav'), toc: $('page-toc'), prev: $('previous-doc'), next: $('next-doc'),
    search: $('search-input'), results: $('search-results'), menu: $('menu-button'), sidebar: $('sidebar'),
    backdrop: $('sidebar-backdrop'), theme: $('theme-button'), toast: $('toast'), version: $('version-badge'),
  };
  let active = '';
  let observer = null;

  const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[c]));

  function slugify(value) {
    return String(value).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9_]+/g, '-').replace(/^-|-$/g, '') || 'seccion';
  }

  function docHref(href) {
    const target = String(href || '').trim();
    if (/^https:\/\//i.test(target)) return { url: target, external: true };
    if (target.startsWith('#')) return { url: target, external: false };
    const [file, anchor] = target.replace(/^\.\//, '').split('#');
    const doc = docs.find((d) => d.source.endsWith(`/${file}`) || d.slug === file.replace(/\.md$/, ''));
    if (doc) return { url: `#${doc.slug}${anchor ? `/${anchor}` : ''}`, external: false };
    if (/^(\.\.\/)?(web|docs|img)\//.test(target) || /^img\//.test(target)) return { url: target, external: false };
    return { url: '#', external: false };
  }

  function inline(value) {
    let out = escapeHtml(value);
    out = out.replace(/`([^`]+)`/g, '<code>$1</code>');
    out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    out = out.replace(/(^|[^*])\*([^*\s][^*]*)\*/g, '$1<em>$2</em>');
    out = out.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt, src) => `<img src="${escapeHtml(src)}" alt="${alt}" loading="lazy">`);
    out = out.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, href) => {
      const link = docHref(href.replace(/&amp;/g, '&'));
      return `<a href="${escapeHtml(link.url)}"${link.external ? ' target="_blank" rel="noopener"' : ''}>${label}</a>`;
    });
    return out;
  }

  const isSeparator = (line) => /^\s*\|?\s*:?-{3,}/.test(line) && line.includes('|');
  const cells = (line) => line.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim());

  function render(markdown) {
    const lines = String(markdown || '').replace(/\r/g, '').split('\n');
    const html = [];
    const toc = [];
    const used = new Map();
    let i = 0;
    let skippedTitle = false;
    const makeId = (label, explicit) => {
      const base = explicit || slugify(label);
      const n = used.get(base) || 0;
      used.set(base, n + 1);
      return n ? `${base}-${n + 1}` : base;
    };
    while (i < lines.length) {
      const line = lines[i];
      if (!line.trim()) { i += 1; continue; }
      if (line.startsWith('```')) {
        const lang = line.slice(3).trim() || 'texto';
        const code = [];
        i += 1;
        while (i < lines.length && !lines[i].startsWith('```')) { code.push(lines[i]); i += 1; }
        i += 1;
        html.push(`<div class="code-block"><div class="code-block__head"><span>${escapeHtml(lang)}</span><button type="button" data-copy>Copiar</button></div><pre><code>${escapeHtml(code.join('\n'))}</code></pre></div>`);
        continue;
      }
      const heading = line.match(/^(#{1,4})\s+(.+?)(?:\s+\{#([a-z0-9_\-]+)\})?\s*$/);
      if (heading) {
        const level = heading[1].length;
        i += 1;
        if (level === 1 && !skippedTitle) { skippedTitle = true; continue; }
        const id = makeId(heading[2], heading[3]);
        if (level >= 2 && level <= 3) toc.push({ id, label: heading[2], level });
        html.push(`<h${level} id="${id}"><a class="anchor" href="#${active}/${id}" aria-hidden="true">#</a>${inline(heading[2])}</h${level}>`);
        continue;
      }
      if (/^---+$/.test(line.trim())) { html.push('<hr>'); i += 1; continue; }
      if (line.startsWith('> [!')) {
        const m = line.match(/^> \[!(NOTE|TIP|WARNING|DANGER|SUCCESS)\]\s*(.*)$/i);
        const kind = m ? m[1].toLowerCase() : 'note';
        const labels = { note: 'Nota', tip: 'Consejo', warning: 'Importante', danger: 'Peligro', success: 'Correcto' };
        const body = m && m[2] ? [m[2]] : [];
        i += 1;
        while (i < lines.length && lines[i].startsWith('>')) { body.push(lines[i].replace(/^>\s?/, '')); i += 1; }
        html.push(`<aside class="callout callout--${kind}"><strong>${labels[kind]}</strong><p>${inline(body.join(' '))}</p></aside>`);
        continue;
      }
      if (line.startsWith('>')) {
        const body = [];
        while (i < lines.length && lines[i].startsWith('>')) { body.push(lines[i].replace(/^>\s?/, '')); i += 1; }
        html.push(`<blockquote><p>${inline(body.join(' '))}</p></blockquote>`);
        continue;
      }
      if (i + 1 < lines.length && line.includes('|') && isSeparator(lines[i + 1])) {
        const head = cells(line);
        const rows = [];
        i += 2;
        while (i < lines.length && lines[i].includes('|') && lines[i].trim()) { rows.push(cells(lines[i])); i += 1; }
        html.push(`<div class="table-wrap"><table><thead><tr>${head.map((c) => `<th>${inline(c)}</th>`).join('')}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`);
        continue;
      }
      const ul = /^\s*[-*]\s+(.+)$/;
      const ol = /^\s*\d+\.\s+(.+)$/;
      if (ul.test(line) || ol.test(line)) {
        const ordered = ol.test(line);
        const matcher = ordered ? ol : ul;
        const items = [];
        while (i < lines.length && matcher.test(lines[i])) {
          let text = lines[i].match(matcher)[1];
          i += 1;
          while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !matcher.test(lines[i])) { text += ` ${lines[i].trim()}`; i += 1; }
          items.push(text);
        }
        const tag = ordered ? 'ol' : 'ul';
        html.push(`<${tag}>${items.map((t) => `<li>${inline(t)}</li>`).join('')}</${tag}>`);
        continue;
      }
      const para = [line.trim()];
      i += 1;
      while (i < lines.length && lines[i].trim() && !/^(#{1,4})\s/.test(lines[i]) && !lines[i].startsWith('```') && !lines[i].startsWith('>')
        && !ul.test(lines[i]) && !ol.test(lines[i]) && !/^---+$/.test(lines[i].trim()) && !(lines[i].includes('|') && i + 1 < lines.length && isSeparator(lines[i + 1]))) {
        para.push(lines[i].trim());
        i += 1;
      }
      html.push(`<p>${inline(para.join(' '))}</p>`);
    }
    return { html: html.join(''), toc };
  }

  function renderNav() {
    const groups = [];
    for (const doc of docs) {
      let group = groups.find((g) => g.name === doc.group);
      if (!group) { group = { name: doc.group, docs: [] }; groups.push(group); }
      group.docs.push(doc);
    }
    el.nav.innerHTML = groups.map((g) => `<div class="nav-group"><span>${escapeHtml(g.name)}</span>${g.docs.map((d) => `<a href="#${d.slug}" data-slug="${d.slug}">${escapeHtml(d.title)}</a>`).join('')}</div>`).join('');
  }

  function parseHash() {
    const raw = decodeURIComponent(location.hash.replace(/^#/, ''));
    const [slug, anchor] = raw.split('/');
    return { slug: slug || docs[0]?.slug, anchor };
  }

  function show() {
    const { slug, anchor } = parseHash();
    const doc = docs.find((d) => d.slug === slug) || docs[0];
    if (!doc) { el.content.innerHTML = '<p>No hay páginas.</p>'; return; }
    if (doc.slug !== active) {
      active = doc.slug;
      const { html, toc } = render(doc.content);
      el.content.innerHTML = `<header class="doc-header"><span class="eyebrow">${escapeHtml(doc.group)}</span><h1>${escapeHtml(doc.title)}</h1><p>${escapeHtml(doc.description)}</p></header>${html}`;
      el.toc.innerHTML = toc.map((t) => `<a href="#${doc.slug}/${t.id}" data-id="${t.id}" class="toc-l${t.level}">${inline(t.label)}</a>`).join('');
      document.title = `${doc.title} · Weapon Rebalancer`;
      for (const a of el.nav.querySelectorAll('a')) a.classList.toggle('active', a.dataset.slug === doc.slug);
      const index = docs.indexOf(doc);
      pager(el.prev, docs[index - 1]);
      pager(el.next, docs[index + 1]);
      watchHeadings();
    }
    if (anchor) {
      const target = document.getElementById(anchor);
      if (target) { target.scrollIntoView({ block: 'start' }); target.classList.add('flash'); setTimeout(() => target.classList.remove('flash'), 1600); }
    } else window.scrollTo(0, 0);
    closeMenu();
  }

  function pager(node, doc) {
    if (!doc) { node.hidden = true; return; }
    node.hidden = false;
    node.href = `#${doc.slug}`;
    node.querySelector('strong').textContent = doc.title;
  }

  function watchHeadings() {
    observer?.disconnect();
    const links = [...el.toc.querySelectorAll('a')];
    if (!('IntersectionObserver' in window) || !links.length) return;
    observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        for (const link of links) link.classList.toggle('active', link.dataset.id === entry.target.id);
      }
    }, { rootMargin: '-80px 0px -70% 0px' });
    for (const h of el.content.querySelectorAll('h2, h3')) observer.observe(h);
  }

  function search(query) {
    const q = query.trim().toLowerCase();
    if (q.length < 2) { el.results.hidden = true; return; }
    const hits = [];
    for (const doc of docs) {
      const text = doc.content.replace(/[#*`>|]/g, ' ');
      const lower = text.toLowerCase();
      const pos = lower.indexOf(q);
      const inTitle = doc.title.toLowerCase().includes(q);
      if (pos === -1 && !inTitle) continue;
      const start = Math.max(0, pos - 60);
      const snippet = pos === -1 ? doc.description : `${start ? '…' : ''}${text.slice(start, pos + q.length + 90)}…`;
      hits.push({ doc, snippet, score: (inTitle ? 10 : 0) + (lower.split(q).length - 1) });
    }
    hits.sort((a, b) => b.score - a.score);
    const mark = (s) => escapeHtml(s).replace(new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'), (m) => `<mark>${m}</mark>`);
    el.results.innerHTML = hits.length
      ? hits.slice(0, 12).map((h) => `<a href="#${h.doc.slug}"><strong>${escapeHtml(h.doc.title)}</strong><span>${mark(h.snippet)}</span></a>`).join('')
      : '<p class="empty">Sin resultados.</p>';
    el.results.hidden = false;
  }

  function toast(text) {
    el.toast.textContent = text;
    el.toast.classList.add('visible');
    setTimeout(() => el.toast.classList.remove('visible'), 1600);
  }

  function closeMenu() {
    el.sidebar.classList.remove('open');
    el.menu.setAttribute('aria-expanded', 'false');
  }

  function init() {
    const stored = (() => { try { return localStorage.getItem('wr-docs-theme'); } catch { return null; } })();
    if (stored) document.documentElement.dataset.theme = stored;
    el.version.textContent = window.WR_DOCS_VERSION ? `v${window.WR_DOCS_VERSION}` : '';
    renderNav();
    show();
    window.addEventListener('hashchange', show);
    el.search.addEventListener('input', () => search(el.search.value));
    el.results.addEventListener('click', () => { el.results.hidden = true; el.search.value = ''; });
    document.addEventListener('keydown', (e) => {
      if (e.key === '/' && document.activeElement !== el.search) { e.preventDefault(); el.search.focus(); }
      if (e.key === 'Escape') { el.results.hidden = true; closeMenu(); }
    });
    el.menu.addEventListener('click', () => { el.sidebar.classList.toggle('open'); el.menu.setAttribute('aria-expanded', String(el.sidebar.classList.contains('open'))); });
    el.backdrop.addEventListener('click', closeMenu);
    el.theme.addEventListener('click', () => {
      const next = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
      document.documentElement.dataset.theme = next;
      try { localStorage.setItem('wr-docs-theme', next); } catch { /* sin almacenamiento */ }
    });
    el.content.addEventListener('click', (e) => {
      const button = e.target.closest('[data-copy]');
      if (!button) return;
      navigator.clipboard?.writeText(button.closest('.code-block').querySelector('code').textContent).then(() => toast('Copiado'));
    });
  }

  init();
})();
