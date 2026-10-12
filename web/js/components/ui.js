// Componentes de interfaz reutilizables.
import { h, icon, mount, clear } from '../core/dom.js';
import { SEVERITY } from '../core/format.js';

// ---- toasts ---------------------------------------------------------------
export function toast(message, { type = 'ok', detail = '', timeout = 4200 } = {}) {
  const host = document.getElementById('toasts');
  const iconName = { ok: 'check', err: 'alert', warn: 'alert', info: 'info' }[type] || 'info';
  const node = h('div', { class: `toast toast--${type}` }, icon(iconName), h('div', {}, message, detail ? h('small', {}, detail) : null));
  host.append(node);
  setTimeout(() => node.remove(), timeout);
}

export function toastError(error, prefix = '') {
  const detail = [error.hint, Array.isArray(error.details) ? error.details.slice(0, 3).map((d) => d.message || d).join(' · ') : '']
    .filter(Boolean).join(' — ');
  toast(`${prefix}${error.message}`, { type: 'err', detail, timeout: 7000 });
}

// ---- modal ---------------------------------------------------------------
export function modal({ title, body, actions = [], wide = false, onClose }) {
  const overlay = h('div', { class: 'overlay' });
  const close = () => { overlay.remove(); wrap.remove(); document.removeEventListener('keydown', onKey); onClose?.(); };
  const onKey = (event) => { if (event.key === 'Escape') close(); };
  const foot = h('div', { class: 'modal__foot' });
  const wrap = h('div', { class: 'modal-wrap', role: 'dialog', 'aria-modal': 'true', onclick: (e) => { if (e.target === wrap) close(); } },
    h('div', { class: `modal ${wide ? 'modal--wide' : ''}` },
      h('div', { class: 'modal__head' }, h('h2', {}, title), h('button', { class: 'btn btn--ghost btn--icon', 'aria-label': 'Cerrar', onclick: close }, icon('x'))),
      h('div', { class: 'modal__body' }, body),
      foot,
    ));
  for (const action of actions) {
    foot.append(h('button', {
      class: `btn ${action.class || ''}`,
      onclick: async (event) => {
        const result = await action.onClick?.(event, close);
        if (result !== false) close();
      },
    }, action.label));
  }
  if (!actions.length) foot.append(h('button', { class: 'btn', onclick: close }, 'Cerrar'));
  document.addEventListener('keydown', onKey);
  document.body.append(overlay, wrap);
  wrap.querySelector('input, textarea, select')?.focus();
  return { close, wrap };
}

export function confirmDialog({ title, message, confirmLabel = 'Confirmar', danger = false }) {
  return new Promise((resolve) => {
    let decided = false;
    modal({
      title,
      body: typeof message === 'string' ? h('p', {}, message) : message,
      onClose: () => { if (!decided) resolve(false); },
      actions: [
        { label: 'Cancelar', class: 'btn--ghost', onClick: () => { decided = true; resolve(false); } },
        { label: confirmLabel, class: danger ? 'btn--danger' : 'btn--primary', onClick: () => { decided = true; resolve(true); } },
      ],
    });
  });
}

/** Confirmación escrita: el usuario debe teclear la palabra exacta (p. ej. APLICAR). */
export function typedConfirm({ title, message, word = 'APLICAR', confirmLabel = 'Aplicar' }) {
  return new Promise((resolve) => {
    let decided = false;
    const input = h('input', { class: 'input', placeholder: word, autocomplete: 'off', spellcheck: 'false' });
    const body = h('div', { class: 'stack' }, message, h('div', { class: 'field' }, h('label', {}, `Escribe ${word} para continuar`), input));
    const { close, wrap } = modal({
      title, body,
      onClose: () => { if (!decided) resolve(null); },
      actions: [
        { label: 'Cancelar', class: 'btn--ghost', onClick: () => { decided = true; resolve(null); } },
        { label: confirmLabel, class: 'btn--primary', onClick: () => {
          if (input.value.trim() !== word) { input.focus(); input.style.borderColor = 'var(--err)'; return false; }
          decided = true; resolve(word); return true;
        } },
      ],
    });
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && input.value.trim() === word) { decided = true; resolve(word); close(); } });
    void wrap;
  });
}

/** Formulario simple en modal. fields: [{name,label,value,placeholder,hint,type,options}] */
export function formDialog({ title, fields, submitLabel = 'Guardar', intro = null }) {
  return new Promise((resolve) => {
    let decided = false;
    const inputs = {};
    const body = h('div', { class: 'stack' }, intro,
      fields.map((f) => {
        let input;
        if (f.type === 'select') {
          input = h('select', { class: 'select' }, f.options.map((o) => h('option', { value: o.value, selected: o.value === f.value }, o.label)));
        } else if (f.type === 'textarea') {
          input = h('textarea', { class: `textarea ${f.code ? 'textarea--code' : ''}`, placeholder: f.placeholder || '' });
          input.value = f.value ?? '';
        } else if (f.type === 'checkbox') {
          input = h('input', { type: 'checkbox', checked: !!f.value });
          inputs[f.name] = input;
          return h('label', { class: 'check' }, input, f.label);
        } else {
          input = h('input', { class: 'input', value: f.value ?? '', placeholder: f.placeholder || '', spellcheck: 'false' });
        }
        inputs[f.name] = input;
        return h('div', { class: 'field' }, h('label', {}, f.label), input, f.hint ? h('span', { class: 'hint' }, f.hint) : null);
      }));
    modal({
      title, body,
      onClose: () => { if (!decided) resolve(null); },
      actions: [
        { label: 'Cancelar', class: 'btn--ghost', onClick: () => { decided = true; resolve(null); } },
        { label: submitLabel, class: 'btn--primary', onClick: () => {
          decided = true;
          const values = {};
          for (const [name, input] of Object.entries(inputs)) values[name] = input.type === 'checkbox' ? input.checked : input.value.trim();
          resolve(values);
        } },
      ],
    });
  });
}

// ---- drawer ---------------------------------------------------------------
export function drawer({ title, subtitle, body, actions = [] }) {
  const overlay = h('div', { class: 'overlay', onclick: () => close() });
  const foot = actions.length ? h('div', { class: 'drawer__foot' }, actions) : null;
  const panel = h('aside', { class: 'drawer', role: 'dialog', 'aria-modal': 'true' },
    h('div', { class: 'drawer__head' },
      h('div', { class: 'grow' }, h('h2', {}, title), subtitle ? h('div', { class: 'muted small' }, subtitle) : null),
      h('button', { class: 'btn btn--ghost btn--icon', 'aria-label': 'Cerrar', onclick: () => close() }, icon('x'))),
    h('div', { class: 'drawer__body' }, body), foot);
  const onKey = (event) => { if (event.key === 'Escape') close(); };
  function close() { overlay.remove(); panel.remove(); document.removeEventListener('keydown', onKey); }
  document.addEventListener('keydown', onKey);
  document.body.append(overlay, panel);
  return { close, panel };
}

// ---- ayuda contextual ---------------------------------------------------------------
let openPopover = null;
export function help(spec) {
  // spec: { title, text, notes, doc }
  const button = h('button', { class: 'help', type: 'button', 'aria-label': `Ayuda: ${spec.title}` }, '?');
  const show = () => {
    hidePopover();
    const rect = button.getBoundingClientRect();
    const pop = h('div', { class: 'popover', role: 'tooltip' },
      h('strong', {}, spec.title),
      spec.text ? h('p', {}, spec.text) : null,
      spec.notes ? h('p', { class: 'warn' }, spec.notes) : null,
      spec.doc ? h('a', { href: `/docs/#${spec.doc}`, target: '_blank', rel: 'noopener' }, 'Ver en la documentación →') : null);
    document.body.append(pop);
    const left = Math.min(window.innerWidth - pop.offsetWidth - 12, Math.max(12, rect.left - 10));
    const top = rect.bottom + 8 + pop.offsetHeight > window.innerHeight ? rect.top - pop.offsetHeight - 8 : rect.bottom + 8;
    pop.style.left = `${left}px`;
    pop.style.top = `${top}px`;
    openPopover = pop;
  };
  button.addEventListener('click', (e) => { e.stopPropagation(); openPopover ? hidePopover() : show(); });
  button.addEventListener('mouseenter', show);
  button.addEventListener('mouseleave', () => setTimeout(() => { if (openPopover && !openPopover.matches(':hover')) hidePopover(); }, 150));
  return button;
}
function hidePopover() { openPopover?.remove(); openPopover = null; }
document.addEventListener('click', (e) => { if (openPopover && !openPopover.contains(e.target)) hidePopover(); });
window.addEventListener('scroll', hidePopover, true);

// ---- piezas pequeñas ---------------------------------------------------------------
export function badge(text, variant = '') {
  return h('span', { class: `badge ${variant ? `badge--${variant}` : ''}` }, text);
}

export function sevDot(severity) {
  return h('span', { class: `sev-dot sev-dot--${severity}`, title: SEVERITY[severity]?.label || severity });
}

export function callout(type, content, iconName) {
  const name = iconName || { info: 'info', warn: 'alert', err: 'alert', ok: 'check', purple: 'info' }[type];
  return h('div', { class: `callout callout--${type}` }, icon(name), h('div', { class: 'grow' }, content));
}

export function loading(text = 'Cargando…') {
  return h('div', { class: 'loading' }, h('span', { class: 'spinner' }), text);
}

export function empty(text, iconName = 'info') {
  return h('div', { class: 'empty' }, icon(iconName), h('div', {}, text));
}

export function card({ title, iconName, actions, body, className = '' }) {
  return h('section', { class: `card ${className}` },
    title ? h('div', { class: 'card__head' }, iconName ? icon(iconName) : null, h('h2', {}, title), actions || null) : null,
    body);
}

export function kpi(value, label, { variant = '', hint = '' } = {}) {
  return h('div', { class: `card kpi kpi--${variant}` }, h('span', { class: 'kpi__value' }, value), h('span', { class: 'kpi__label' }, label),
    hint ? h('span', { class: 'kpi__hint' }, hint) : null);
}

export function tabs(items, active, onChange) {
  return h('div', { class: 'tabs', role: 'tablist' }, items.map((item) => h('button', {
    class: `tab ${item.id === active ? 'active' : ''}`, role: 'tab', 'aria-selected': item.id === active ? 'true' : 'false',
    onclick: () => onChange(item.id),
  }, item.icon ? icon(item.icon) : null, item.label, item.count !== undefined && item.count !== null ? badge(item.count, item.countVariant || '') : null)));
}

export function segmented(options, value, onChange) {
  const group = h('div', { class: 'segmented' }, options.map((o) => h('button', {
    type: 'button', class: o.value === value ? 'active' : '',
    onclick: (event) => {
      for (const button of group.children) button.classList.toggle('active', button === event.currentTarget);
      onChange(o.value);
    },
  }, o.label)));
  return group;
}

/** Lista de problemas con su arreglo sugerido. */
export function issueList(issues, { emptyText = 'Sin problemas.', limitWeapons = 12 } = {}) {
  if (!issues?.length) return empty(emptyText, 'check');
  return h('div', {}, issues.map((item) => h('div', { class: 'issue' },
    sevDot(item.severity || 'info'),
    h('div', {},
      h('div', { class: 'issue__msg' }, item.message),
      item.fix ? h('div', { class: 'issue__fix' }, item.fix) : null,
      item.condition ? h('div', { class: 'small muted' }, 'Dentro de: ', h('code', {}, `if ${item.condition} then`)) : null,
      item.weapons?.length ? h('details', { class: 'issue__extra' }, h('summary', {}, `${item.weapons.length} arma(s)`),
        h('div', { class: 'chips', style: { marginTop: '6px' } }, item.weapons.slice(0, 200).map((w) => h('a', { class: 'tag', href: `#/armamento?w=${w}` }, w))),
        item.weapons.length > 200 ? h('div', { class: 'small muted' }, `… y ${item.weapons.length - 200} más`) : null) : null,
      item.snippet ? h('pre', {}, item.snippet) : null,
      Array.isArray(item.details) ? h('pre', {}, item.details.map((d) => (typeof d === 'string' ? d : d.message || JSON.stringify(d))).join('\n')) : null,
    ))));
  void limitWeapons;
}

// ---- JSON y diff ---------------------------------------------------------------
export function jsonView(data) {
  const text = JSON.stringify(data, null, 2);
  const pre = h('pre', { class: 'code' });
  const re = /("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g;
  let last = 0;
  for (const match of text.matchAll(re)) {
    pre.append(text.slice(last, match.index));
    if (match[1]) pre.append(h('span', { class: match[2] ? 'k' : 's' }, match[1]), match[2] || '');
    else if (match[3]) pre.append(h('span', { class: 'b' }, match[3]));
    else pre.append(h('span', { class: 'n' }, match[4]));
    last = match.index + match[0].length;
  }
  pre.append(text.slice(last));
  return pre;
}

export function diffView(text) {
  const pre = h('pre', { class: 'code diff' });
  for (const line of String(text).split('\n')) {
    let cls = '';
    if (line.startsWith('@@')) cls = 'hunk';
    else if (line.startsWith('+') && !line.startsWith('+++')) cls = 'add';
    else if (line.startsWith('-') && !line.startsWith('---')) cls = 'del';
    pre.append(cls ? h('span', { class: cls }, line) : `${line}\n`);
  }
  return pre;
}

// ---- tabla ordenable con paginación ---------------------------------------------------------------
export function dataTable({ columns, rows, pageSize = 50, onRowClick, rowClass, initialSort, emptyText = 'Sin resultados.' }) {
  const state = { sort: initialSort || null, dir: initialSort?.dir || 1, page: 0 };
  const wrap = h('div', {});
  function sortedRows() {
    if (!state.sort) return rows;
    const column = columns.find((c) => c.key === state.sort.key);
    const value = column?.sortValue || ((row) => row[column?.key]);
    return [...rows].sort((a, b) => {
      const va = value(a); const vb = value(b);
      if (va === vb) return 0;
      if (va === null || va === undefined) return 1;
      if (vb === null || vb === undefined) return -1;
      return (va > vb ? 1 : -1) * state.dir;
    });
  }
  function render() {
    clear(wrap);
    const data = sortedRows();
    const pages = Math.max(1, Math.ceil(data.length / pageSize));
    state.page = Math.min(state.page, pages - 1);
    const slice = data.slice(state.page * pageSize, (state.page + 1) * pageSize);
    const table = h('table', { class: 'table' },
      h('thead', {}, h('tr', {}, columns.map((c) => {
        const sorted = state.sort?.key === c.key;
        return h('th', {
          class: `${c.sortable === false ? '' : 'sortable'} ${c.num ? 'num' : ''}`,
          onclick: c.sortable === false ? null : () => { state.dir = sorted ? -state.dir : (c.defaultDir || 1); state.sort = { key: c.key }; render(); },
        }, c.label, sorted ? h('span', { class: 'arrow' }, state.dir > 0 ? '↑' : '↓') : null);
      }))),
      h('tbody', {}, slice.map((row) => h('tr', {
        class: `${onRowClick ? 'clickable' : ''} ${rowClass ? rowClass(row) : ''}`,
        onclick: onRowClick ? (e) => { if (!e.target.closest('button, a, input, select')) onRowClick(row); } : null,
      }, columns.map((c) => h('td', { class: c.num ? 'num' : (c.className || '') }, c.render ? c.render(row) : (row[c.key] ?? '—')))))));
    mount(wrap, data.length ? h('div', { class: 'table-wrap' }, table) : empty(emptyText),
      pages > 1 ? h('div', { class: 'pager' },
        h('span', {}, `${state.page * pageSize + 1}–${Math.min(data.length, (state.page + 1) * pageSize)} de ${data.length}`),
        h('div', { class: 'row' },
          h('button', { class: 'btn btn--sm', disabled: state.page === 0, onclick: () => { state.page -= 1; render(); } }, 'Anterior'),
          h('span', {}, `Página ${state.page + 1} / ${pages}`),
          h('button', { class: 'btn btn--sm', disabled: state.page >= pages - 1, onclick: () => { state.page += 1; render(); } }, 'Siguiente'))) : null);
  }
  render();
  wrap.update = (newRows) => { rows = newRows; state.page = 0; render(); };
  return wrap;
}

// ---- gráficas SVG ---------------------------------------------------------------
const SERIES_COLORS = ['#a78bfa', '#60a5fa', '#34d399', '#fbbf24', '#f472b6', '#38bdf8', '#f87171', '#c084fc'];
export function seriesColor(index) { return SERIES_COLORS[index % SERIES_COLORS.length]; }

/** Gráfica de líneas. series: [{label, color, points:[[x,y]...], dashed}] */
export function lineChart({ series, xLabel = '', yLabel = '', height = 260, yMin = 0, formatY = (v) => String(Math.round(v * 10) / 10) }) {
  const width = 760;
  const pad = { l: 48, r: 14, t: 12, b: 34 };
  const all = series.flatMap((s) => s.points.filter((p) => p[1] !== null && p[1] !== undefined));
  if (!all.length) return empty('Sin datos suficientes para graficar.');
  const xMax = Math.max(...all.map((p) => p[0])) || 1;
  const yMaxRaw = Math.max(...all.map((p) => p[1]));
  const yMax = yMaxRaw <= yMin ? yMin + 1 : yMaxRaw * 1.08;
  const sx = (x) => pad.l + (x / xMax) * (width - pad.l - pad.r);
  const sy = (y) => height - pad.b - ((y - yMin) / (yMax - yMin)) * (height - pad.t - pad.b);
  const NS = 'http://www.w3.org/2000/svg';
  const el = (tag, attrs) => { const n = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); return n; };
  const svg = el('svg', { viewBox: `0 0 ${width} ${height}`, class: 'chart', role: 'img', 'aria-label': yLabel });
  for (let i = 0; i <= 4; i += 1) {
    const y = yMin + ((yMax - yMin) * i) / 4;
    svg.append(el('line', { x1: pad.l, x2: width - pad.r, y1: sy(y), y2: sy(y), class: 'grid-line' }));
    const t = el('text', { x: pad.l - 8, y: sy(y) + 4, 'text-anchor': 'end' }); t.textContent = formatY(y); svg.append(t);
  }
  for (let i = 0; i <= 5; i += 1) {
    const x = (xMax * i) / 5;
    const t = el('text', { x: sx(x), y: height - pad.b + 16, 'text-anchor': 'middle' }); t.textContent = Math.round(x); svg.append(t);
  }
  const xl = el('text', { x: width - pad.r, y: height - 4, 'text-anchor': 'end' }); xl.textContent = xLabel; svg.append(xl);
  const yl = el('text', { x: 6, y: pad.t + 2 }); yl.textContent = yLabel; svg.append(yl);
  series.forEach((s, index) => {
    const points = s.points.filter((p) => p[1] !== null && p[1] !== undefined);
    if (!points.length) return;
    const d = points.map((p, i) => `${i ? 'L' : 'M'}${sx(p[0]).toFixed(1)},${sy(p[1]).toFixed(1)}`).join(' ');
    svg.append(el('path', { d, fill: 'none', stroke: s.color || seriesColor(index), 'stroke-width': 2.2, 'stroke-dasharray': s.dashed ? '6 5' : '', 'stroke-linejoin': 'round' }));
  });
  const legend = h('div', { class: 'legend' }, series.map((s, index) => h('span', {}, h('i', { style: { background: s.color || seriesColor(index) } }), s.label)));
  return h('div', { class: 'stack stack--sm' }, svg, legend);
}

export function barList(items, { max, variant = '' } = {}) {
  const top = max ?? Math.max(1, ...items.map((i) => i.value));
  return h('div', { class: 'bars' }, items.map((item) => h('div', { class: 'bar' },
    h('span', { class: 'nowrap', title: item.label }, item.label),
    h('div', { class: 'bar__track' }, h('div', { class: `bar__fill ${variant ? `bar__fill--${variant}` : ''}`, style: { width: `${(item.value / top) * 100}%` } })),
    h('span', { class: 'right mono small' }, item.value))));
}
