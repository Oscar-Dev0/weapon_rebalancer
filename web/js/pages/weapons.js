import { api } from '../core/api.js';
import { debounce, h, icon, mount, setLoading } from '../core/dom.js';
import { num, same, withUnit } from '../core/format.js';
import { loadCatalog, store } from '../core/store.js';
import { badge, callout, card, dataTable, drawer, empty, issueList, loading, sevDot, tabs, toast, toastError } from '../components/ui.js';

const STATUS_FILTERS = [
  { id: 'all', label: 'Todas' },
  { id: 'issues', label: 'Con problemas' },
  { id: 'modified', label: 'Modificadas vs .bak' },
  { id: 'custom', label: 'Personalizadas' },
  { id: 'official', label: 'Oficiales' },
  { id: 'ox_only', label: 'Solo ox_inventory' },
  { id: 'meta_only', label: 'Solo META' },
  { id: 'duplicates', label: 'Duplicadas' },
  { id: 'internal', label: 'Internas del juego' },
];

export async function render({ root, params, setTitle }) {
  setTitle('Armamento', 'Armas detectadas en ox_inventory y en los weapons.meta del servidor');
  const catalog = await loadCatalog();
  const state = { query: params.get('q') || '', category: params.get('cat') || 'all', status: params.get('f') || 'all' };

  const categories = new Map();
  for (const w of catalog.weapons) {
    if (w.internal) continue;
    const entry = categories.get(w.category.id) || { ...w.category, count: 0 };
    entry.count += 1;
    categories.set(w.category.id, entry);
  }
  const sortedCats = [...categories.values()].sort((a, b) => a.order - b.order);
  // Estado frente al perfil activo (se calcula con la vista previa real, en segundo plano).
  const profileState = { loaded: false, weapons: {} };

  const search = h('input', { class: 'input', placeholder: 'Buscar por nombre, etiqueta o hash…', value: state.query, spellcheck: 'false' });
  const statusSelect = h('select', { class: 'select', style: { width: '210px' } },
    STATUS_FILTERS.map((f) => h('option', { value: f.id, selected: f.id === state.status }, f.label)));
  const chips = h('div', { class: 'chips' });
  const counter = h('span', { class: 'muted small' });
  const tableHost = h('div', {});
  const rescan = h('button', { class: 'btn', onclick: async () => {
    setLoading(rescan, true);
    try {
      await loadCatalog(true);
      toast('Catálogo actualizado.', { detail: `${store.catalog.summary.weapons} armas · ${store.catalog.summary.duration_ms} ms` });
      render({ root, params, setTitle });
    } catch (error) { toastError(error); }
    setLoading(rescan, false);
  } }, icon('refresh'), 'Reescanear');

  function renderChips() {
    mount(chips,
      h('button', { class: `chip ${state.category === 'all' ? 'active' : ''}`, onclick: () => { state.category = 'all'; update(); } }, 'Todas',
        h('span', { class: 'count' }, catalog.weapons.filter((w) => !w.internal).length)),
      sortedCats.map((c) => h('button', { class: `chip ${state.category === c.id ? 'active' : ''}`, onclick: () => { state.category = c.id; update(); } },
        c.label, h('span', { class: 'count' }, c.count))));
  }

  function matches(w) {
    if (state.status === 'internal') { if (!w.internal) return false; } else if (w.internal) return false;
    if (state.category !== 'all' && w.category.id !== state.category) return false;
    switch (state.status) {
      case 'issues': if (w.severity === 'ok' || w.severity === 'info') return false; break;
      case 'modified': if (!w.modified_fields.length) return false; break;
      case 'custom': if (!w.custom) return false; break;
      case 'official': if (w.custom) return false; break;
      case 'ox_only': if (!(w.in_ox && !w.in_meta)) return false; break;
      case 'meta_only': if (!(w.in_meta && !w.in_ox)) return false; break;
      case 'duplicates': if (w.definition_count < 2) return false; break;
      default: break;
    }
    if (state.query) {
      const q = state.query.toLowerCase();
      const hay = `${w.name} ${w.label} ${w.hash} ${w.resources.join(' ')}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  }

  const columns = [
    { key: 'name', label: 'Arma', render: (w) => h('div', { class: 'weapon-cell' }, h('strong', {}, w.label), h('small', {}, w.name)) },
    { key: 'category', label: 'Categoría', sortValue: (w) => w.category.order, render: (w) => w.category.label },
    { key: 'source', label: 'Origen', sortable: false, render: (w) => h('div', { class: 'row', style: { gap: '4px' } },
      w.in_ox ? badge('ox', 'blue') : badge('sin ox', 'outline'),
      w.in_meta ? badge(w.definition_count > 1 ? `META ×${w.definition_count}` : 'META', w.definition_count > 1 ? 'warn' : 'purple') : badge('sin META', 'warn'),
      w.custom ? badge('custom') : null) },
    { key: 'damage', label: 'Daño', num: true, sortValue: (w) => w.current.damage ?? null, render: (w) => valueWithOriginal(w, 'damage') },
    { key: 'rpm', label: 'RPM', num: true, sortValue: (w) => w.rpm ?? null, render: (w) => (w.rpm ? Math.round(w.rpm) : '—') },
    { key: 'head', label: 'Cabeza (red)', num: true, sortValue: (w) => w.current.network_headshot ?? null, render: (w) => valueWithOriginal(w, 'network_headshot', 'x') },
    { key: 'range', label: 'Alcance', num: true, sortValue: (w) => w.current.weapon_range ?? null, render: (w) => valueWithOriginal(w, 'weapon_range', 'm') },
    { key: 'qbx', label: 'Recoil script', num: true, sortValue: (w) => w.qbx_recoil ?? -1, render: (w) => (w.qbx_recoil ?? '—') },
    { key: 'profile', label: 'Perfil activo', sortValue: (w) => profileState.weapons[w.name]?.changes ?? -1, render: (w) => {
      if (!profileState.loaded) return h('span', { class: 'muted small' }, '…');
      const row = profileState.weapons[w.name];
      if (!row) return '—';
      const state = row.profile_state;
      if (state.startsWith('cambia')) return badge(state, 'purple');
      return state === 'al día' ? badge(state, 'ok') : state === 'omitida' ? badge(state, 'outline') : h('span', { class: 'muted small' }, state);
    } },
    { key: 'severity', label: 'Estado', sortValue: (w) => ({ error: 0, warning: 1, info: 2, ok: 3 })[w.severity], render: (w) => h('span', { class: 'row', style: { gap: '6px' } },
      sevDot(w.severity), w.issue_count ? `${w.issue_count}` : 'OK') },
  ];
  let table = null;

  function update() {
    renderChips();
    const rows = catalog.weapons.filter(matches);
    counter.textContent = `${rows.length} resultado(s)`;
    if (!table) {
      table = dataTable({ columns, rows, pageSize: 60, onRowClick: (w) => openWeapon(w.name), initialSort: { key: 'category' } });
      mount(tableHost, table);
    } else table.update(rows);
    const hash = new URLSearchParams();
    if (state.query) hash.set('q', state.query);
    if (state.category !== 'all') hash.set('cat', state.category);
    if (state.status !== 'all') hash.set('f', state.status);
    history.replaceState(null, '', `#/armamento${hash.toString() ? `?${hash}` : ''}`);
  }

  search.addEventListener('input', debounce(() => { state.query = search.value.trim(); update(); }, 150));
  statusSelect.addEventListener('change', () => { state.status = statusSelect.value; update(); });

  mount(root,
    catalog.global_issues.length ? issueList(catalog.global_issues) : null,
    h('div', { class: 'card' },
      h('div', { class: 'row', style: { marginBottom: '12px' } },
        h('label', { class: 'search grow' }, icon('search'), search), statusSelect, counter, rescan),
      chips),
    h('div', { class: 'card card--flush' }, tableHost));
  update();
  // Misma tabla que `wr.py weapons` (services.App.weapon_rows): una sola lógica para web y terminal.
  api.post('/api/weapons/rows', { profile_id: store.status.active_profile }).then((data) => {
    profileState.loaded = true;
    profileState.weapons = Object.fromEntries(data.rows.map((row) => [row.name, row]));
    table?.update(catalog.weapons.filter(matches));
  }).catch(() => { profileState.loaded = true; table?.update(catalog.weapons.filter(matches)); });
  const initial = params.get('w');
  if (initial) openWeapon(initial);
}

function valueWithOriginal(w, key, unit = '') {
  const now = w.current[key];
  const orig = w.original[key];
  if (now === undefined) return '—';
  if (orig !== undefined && !same(now, orig)) {
    return h('span', { title: `Original (.bak): ${num(orig)}` }, h('span', { class: 'was' }, num(orig)), unit === 'x' ? `×${num(now)}` : num(now));
  }
  return unit === 'x' ? `×${num(now)}` : num(now);
}

export async function openWeapon(name) {
  const body = h('div', {}, loading());
  const actions = [
    h('a', { class: 'btn', href: `#/simulador?w=${name}` }, icon('simulator'), 'Simular'),
    h('a', { class: 'btn btn--primary', href: `#/editor?w=${name}` }, icon('editor'), 'Editar'),
  ];
  const { close } = drawer({ title: name, subtitle: 'Detalle del arma', body, actions });
  actions.forEach((a) => a.addEventListener('click', () => close()));
  try {
    const detail = await api.get(`/api/catalog/weapons/${encodeURIComponent(name)}`);
    let proposed = null;
    let explained = null;
    if (store.status?.active_profile && detail.in_meta) {
      try {
        const [preview, explain] = await Promise.all([
          api.post('/api/preview', { profile_id: store.status.active_profile, weapons: [name] }),
          api.post('/api/profiles/explain', { profile_id: store.status.active_profile, weapon: name }),
        ]);
        proposed = preview.weapons[name] || null;
        explained = explain.fields;
      } catch { proposed = null; }
    }
    mount(body, weaponDetail(detail, proposed, explained));
  } catch (error) {
    mount(body, callout('err', error.message));
  }
}

const ORIGIN = { inherited: ['H', 'blue'], overridden: ['S', 'purple'], own: ['P', 'purple'], rule: ['R', 'warn'], original: ['O', 'outline'], ignored: ['X', 'err'] };

export function weaponDetail(detail, proposed, explained = null) {
  const state = { tab: 'values', advanced: false };
  const host = h('div', {});
  const primary = detail.definitions[detail.definitions.length - 1];
  const current = primary?.values || {};
  const original = primary?.original_values || current;
  const proposedValues = proposed?.proposed || null;

  function valuesTable() {
    const sections = store.registry.sections;
    const rows = [];
    for (const section of sections) {
      const params = store.registry.params.filter((p) => p.section === section.id && p.method === 'meta' && (state.advanced || !p.advanced) && p.value_type !== 'flags');
      const present = params.filter((p) => current[p.key] !== undefined || original[p.key] !== undefined);
      if (!present.length) continue;
      rows.push(h('tr', {}, h('td', { colspan: 5, class: 'label', style: { paddingTop: '14px', color: 'var(--purple-2)' } }, section.label)));
      for (const p of present) {
        const now = current[p.key];
        const orig = original[p.key];
        const prop = proposedValues ? proposedValues[p.key] : undefined;
        rows.push(h('tr', {},
          h('td', {}, p.label, h('div', { class: 'muted small mono' }, p.tag)),
          h('td', { class: 'num muted' }, withUnit(orig, p.unit)),
          h('td', { class: `num ${orig !== undefined && !same(now, orig) ? 'delta-up' : ''}` }, withUnit(now, p.unit)),
          h('td', { class: 'num', style: { color: prop !== undefined && !same(prop, now) ? 'var(--purple-2)' : '' } }, proposedValues ? withUnit(prop, p.unit) : '—'),
          h('td', { class: 'small muted' }, explained?.[p.key] ? [badge(ORIGIN[explained[p.key].status]?.[0] || '?', ORIGIN[explained[p.key].status]?.[1] || 'outline'), ' ', explained[p.key].label] : '')));
      }
    }
    return h('div', { class: 'stack stack--sm' },
      h('div', { class: 'row row--between' },
        h('span', { class: 'small muted' }, 'Original = .bak · Actual = weapons.meta · Propuesto = perfil activo · H heredado · S sobrescrito · P del perfil · R regla · O original'),
        h('label', { class: 'check small' }, h('input', { type: 'checkbox', checked: state.advanced, onchange: (e) => { state.advanced = e.target.checked; draw(); } }), 'Mostrar avanzados')),
      h('table', { class: 'table table--compact' },
        h('thead', {}, h('tr', {}, h('th', {}, 'Parámetro'), h('th', { class: 'num' }, 'Original'), h('th', { class: 'num' }, 'Actual'), h('th', { class: 'num' }, 'Propuesto'), h('th', {}, 'Procedencia'))),
        h('tbody', {}, rows)));
  }

  function identity() {
    const ox = detail.ox;
    return h('div', { class: 'stack' },
      h('dl', { class: 'kv' },
        h('dt', {}, 'Etiqueta'), h('dd', {}, detail.label),
        h('dt', {}, 'Hash'), h('dd', { class: 'mono' }, `${detail.hash} (${detail.hash_signed})`),
        h('dt', {}, 'Grupo'), h('dd', {}, detail.group || '—', ' · ', detail.category.label),
        h('dt', {}, 'Tipo'), h('dd', {}, detail.custom ? 'Personalizada (no está en el catálogo oficial de Cfx.re)' : 'Oficial de GTA V'),
        h('dt', {}, 'Recoil por script'), h('dd', {}, detail.qbx_recoil !== null && detail.qbx_recoil !== undefined ? `${detail.qbx_recoil} (qbx_recoils)` : 'Sin entrada en qbx_recoils'),
      ),
      h('h3', {}, 'ox_inventory'),
      ox ? h('dl', { class: 'kv' },
        h('dt', {}, 'Línea'), h('dd', {}, `data/weapons.lua:${ox.line}`),
        h('dt', {}, 'Modelo / hash'), h('dd', { class: 'mono' }, `${ox.model} · ${ox.hash}`),
        h('dt', {}, 'Munición'), h('dd', {}, ox.ammoname || '—'),
        h('dt', {}, 'Peso'), h('dd', {}, ox.weight ?? '—'),
        h('dt', {}, 'Desgaste'), h('dd', {}, ox.durability ?? '—'),
        h('dt', {}, 'Rareza'), h('dd', {}, ox.rarity || '—'),
      ) : callout('warn', 'No está registrada en ox_inventory: no se puede obtener como ítem.'),
      h('h3', {}, `Definiciones META (${detail.definitions.length})`),
      detail.definitions.length ? h('div', { class: 'stack stack--sm' }, detail.definitions.map((d) => h('div', { class: 'card', style: { padding: '10px 12px' } },
        h('div', { class: 'mono small' }, d.relative),
        h('div', { class: 'row small muted', style: { marginTop: '4px' } },
          badge(d.resource, 'blue'), d.registered ? badge('registrado en fxmanifest', 'ok') : badge('sin WEAPONINFO_FILE', 'warn'),
          d.has_backup ? badge('.bak', 'outline') : badge('sin .bak', 'warn'), d.source !== 'CWeaponInfo' ? badge(d.source, 'warn') : null)))) : empty('Sin weapons.meta en los packs configurados.'),
      h('h3', {}, 'Flags'),
      current.weapon_flags ? h('div', { class: 'chips' }, current.weapon_flags.map((f) => h('span', { class: 'tag' }, f))) : h('span', { class: 'muted' }, '—'),
    );
  }

  function components() {
    if (!detail.components.length) return empty('El META no declara componentes.');
    return h('table', { class: 'table table--compact' },
      h('thead', {}, h('tr', {}, h('th', {}, 'Componente'), h('th', {}, 'Ítem ox_inventory'), h('th', { class: 'num' }, 'Cargador'), h('th', { class: 'num' }, 'Mod. daño'))),
      h('tbody', {}, detail.components.map((c) => h('tr', {},
        h('td', { class: 'mono small' }, c.name),
        h('td', {}, c.ox_item ? badge(c.ox_item, 'blue') : h('span', { class: 'muted small' }, 'sin ítem')),
        h('td', { class: 'num' }, c.clip_size ?? '—'),
        h('td', { class: 'num' }, c.damage_modifiers.length ? c.damage_modifiers.join(', ') : '—')))));
  }

  function proposedTab() {
    if (!proposed) return callout('info', 'El perfil activo no procesa esta arma o no hay vista previa disponible.');
    const changes = Object.entries(proposed.changes || {});
    return h('div', { class: 'stack' },
      proposed.processed ? null : callout('warn', `El perfil activo omite esta arma (${proposed.skipped_reason || 'sin regla'}).`),
      changes.length ? h('table', { class: 'table table--compact' },
        h('thead', {}, h('tr', {}, h('th', {}, 'Campo'), h('th', { class: 'num' }, 'Actual'), h('th', { class: 'num' }, 'Propuesto'))),
        h('tbody', {}, changes.map(([key, v]) => h('tr', {}, h('td', { class: 'mono small' }, key),
          h('td', { class: 'num' }, Array.isArray(v.current) ? v.current.join(' ') : num(v.current)),
          h('td', { class: 'num', style: { color: 'var(--purple-2)' } }, Array.isArray(v.proposed) ? v.proposed.join(' ') : num(v.proposed))))))
        : callout('ok', 'Aplicar el perfil activo no cambia esta arma.'),
      proposed.onetap ? callout(proposed.onetap.ready ? 'ok' : 'warn', `Auditoría one-tap: ${proposed.onetap.ready ? 'correcta' : proposed.onetap.issues.join(', ')}`) : null,
    );
  }

  function draw() {
    mount(host,
      tabs([
        { id: 'values', label: 'Valores' },
        { id: 'identity', label: 'Identificación' },
        { id: 'components', label: 'Componentes', count: detail.components.length },
        { id: 'proposed', label: 'Perfil activo', count: proposed ? Object.keys(proposed.changes || {}).length : null },
        { id: 'issues', label: 'Problemas', count: detail.issues.length, countVariant: detail.severity === 'warning' ? 'warn' : detail.severity === 'error' ? 'err' : '' },
      ], state.tab, (id) => { state.tab = id; draw(); }),
      state.tab === 'values' ? (primary ? valuesTable() : callout('warn', 'Sin weapons.meta: no hay valores de balance.'))
        : state.tab === 'identity' ? identity()
          : state.tab === 'components' ? components()
            : state.tab === 'proposed' ? proposedTab()
              : issueList(detail.issues));
  }
  draw();
  return host;
}

void card;
