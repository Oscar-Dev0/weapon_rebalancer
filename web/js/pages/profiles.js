import { api } from '../core/api.js';
import { downloadText, h, icon, mount, setLoading } from '../core/dom.js';
import { date, num } from '../core/format.js';
import { loadStatus, openDraft, store } from '../core/store.js';
import {
  badge, callout, card, confirmDialog, dataTable, empty, formDialog, issueList, jsonView, loading, modal, tabs, toast, toastError,
} from '../components/ui.js';

const TIER_BADGE = { official: 'blue', server: 'purple', user: 'ok', legacy: 'outline' };

export async function render({ root, params, setTitle, navigate }) {
  setTitle('Perfiles', 'Oficiales, del servidor y de usuario: crear, derivar, comparar, versionar y activar');
  const showAll = params.get('all') === '1';
  const data = await api.get(`/api/profiles${showAll ? '?all=1' : ''}`);
  const profiles = data.profiles;
  const ids = profiles.map((p) => p.id);

  const toolbar = h('div', { class: 'row' },
    h('button', { class: 'btn btn--primary', onclick: () => createProfile(ids, navigate) }, icon('plus'), 'Nuevo perfil'),
    h('button', { class: 'btn', onclick: () => importProfile(navigate) }, icon('upload'), 'Importar'),
    h('button', { class: 'btn', onclick: () => compareProfiles(ids) }, icon('compare'), 'Comparar'),
    h('a', { class: 'btn btn--ghost', href: showAll ? '#/perfiles' : '#/perfiles?all=1' }, showAll ? 'Ocultar archivados' : 'Mostrar archivados'));

  const columns = [
    { key: 'name', label: 'Perfil', render: (p) => h('div', { class: 'weapon-cell' },
      h('strong', {}, p.name, p.id === data.active ? h('span', { style: { marginLeft: '6px' } }, badge('activo', 'purple')) : null),
      h('small', {}, p.id), p.description ? h('div', { class: 'small muted', style: { maxWidth: '560px' } }, truncate(p.description, 170)) : null) },
    { key: 'tier', label: 'Nivel', sortValue: (p) => ['official', 'server', 'user', 'legacy'].indexOf(p.tier),
      render: (p) => h('div', { class: 'row', style: { gap: '4px' } }, badge(p.tier_label, TIER_BADGE[p.tier]), p.editable ? null : badge('protegido', 'outline')) },
    { key: 'extends', label: 'Hereda de', render: (p) => p.extends || '—' },
    { key: 'format_version', label: 'Formato', render: (p) => (p.legacy ? badge(`legacy v${p.format_version}`, 'warn') : badge('v8', 'ok')) },
    { key: 'revision', label: 'Rev.', num: true },
    { key: 'updated_at', label: 'Actualizado', render: (p) => date(p.updated_at) },
    { key: 'actions', label: '', sortable: false, render: (p) => h('div', { class: 'row', style: { gap: '4px', justifyContent: 'flex-end' } },
      h('a', { class: 'btn btn--sm', href: `#/constructor?p=${p.id}` }, icon('builder'), p.editable ? 'Abrir' : 'Ver'),
      h('button', { class: 'btn btn--sm btn--ghost', title: 'Más acciones', onclick: () => actions(p, data.active, ids, navigate) }, '···')) },
  ];

  mount(root,
    callout('info', ['Tres perfiles ', h('strong', {}, 'oficiales'), ' (Balanced RP, Realistic Combat, Competitive PvP, protegidos), el perfil del ',
      h('strong', {}, 'servidor'), ' (Flow Caribe Custom) y los tuyos de ', h('strong', {}, 'usuario'),
      '. Para cambiar un oficial, crea un derivado: hereda todo y guarda solo tus cambios. Cada guardado deja la versión anterior en el historial.']),
    data.index_errors?.length ? issueList(data.index_errors.map((message) => ({ severity: 'warning', message }))) : null,
    card({ title: `${profiles.length} perfiles`, iconName: 'profiles', actions: toolbar,
      body: dataTable({ columns, rows: profiles, pageSize: 50, initialSort: { key: 'tier' } }) }));
}

function truncate(text, max) {
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

async function createProfile(ids, navigate) {
  const values = await formDialog({
    title: 'Nuevo perfil',
    intro: callout('info', 'Un perfil “vacío” no toca nada: lo que no configures queda exactamente como está en el META.'),
    fields: [
      { name: 'id', label: 'Identificador', placeholder: 'pvp_competitivo', hint: 'Minúsculas, números, - y _. Será el nombre del archivo.' },
      { name: 'name', label: 'Nombre visible', placeholder: 'PvP competitivo' },
      { name: 'description', label: 'Objetivo del perfil', type: 'textarea', placeholder: 'Qué busca este balance y para qué servidor/modo.' },
      { name: 'mode', label: 'Punto de partida', type: 'select', value: 'blank', options: [
        { value: 'blank', label: 'Vacío (recomendado)' },
        ...ids.map((id) => ({ value: `copy:${id}`, label: `Copia de ${id}` })),
        ...ids.map((id) => ({ value: `extends:${id}`, label: `Derivado de ${id} (hereda y sobrescribe)` })),
      ] },
    ],
    submitLabel: 'Crear',
  });
  if (!values) return;
  const body = { id: values.id, name: values.name || values.id, description: values.description };
  if (values.mode.startsWith('copy:')) body.source = values.mode.slice(5);
  if (values.mode.startsWith('extends:')) body.extends = values.mode.slice(8);
  try {
    await api.post('/api/profiles', body);
    toast(`Perfil “${body.id}” creado.`);
    await openDraft(body.id, { force: true });
    navigate(`/constructor?p=${body.id}`);
  } catch (error) { toastError(error, 'No se creó: '); }
}

async function importProfile(navigate) {
  const file = h('input', { type: 'file', accept: '.json,application/json' });
  const idInput = h('input', { class: 'input', placeholder: 'id del perfil' });
  const overwrite = h('input', { type: 'checkbox' });
  file.addEventListener('change', () => {
    const name = file.files[0]?.name.replace(/\.json$/i, '').toLowerCase().replace(/[^a-z0-9_-]/g, '_');
    if (name && !idInput.value) idInput.value = name;
  });
  modal({
    title: 'Importar perfil',
    body: h('div', { class: 'stack' },
      h('p', { class: 'muted' }, 'Acepta perfiles v3–v8. Se validan y se migran a v8 al importarlos.'),
      file, h('div', { class: 'field' }, h('label', {}, 'Guardar como'), idInput),
      h('label', { class: 'check' }, overwrite, 'Sobrescribir si existe (la versión actual queda en el historial)')),
    actions: [
      { label: 'Cancelar', class: 'btn--ghost' },
      { label: 'Importar', class: 'btn--primary', onClick: async () => {
        const selected = file.files[0];
        if (!selected) { toast('Elige un archivo.', { type: 'warn' }); return false; }
        try {
          const content = await selected.text();
          const result = await api.post('/api/profiles/import', { id: idInput.value.trim(), content, overwrite: overwrite.checked });
          toast(`Importado como “${idInput.value.trim()}”.`, { detail: (result.notes || []).join(' ') });
          navigate(`/constructor?p=${idInput.value.trim()}`);
          return true;
        } catch (error) { toastError(error, 'No se importó: '); return false; }
      } },
    ],
  });
}

function actions(profile, active, ids, navigate) {
  const item = (iconName, label, onClick, cls = '') => h('button', { class: `btn ${cls}`, style: { justifyContent: 'flex-start' }, onclick: async () => { close(); await onClick(); } }, icon(iconName), label);
  const info = h('div', { class: 'stack stack--sm' },
    h('div', { class: 'row' }, badge(profile.tier_label, TIER_BADGE[profile.tier]), profile.editable ? badge('editable', 'ok') : badge('protegido', 'outline'),
      profile.extends ? badge(`hereda de ${profile.extends}`, 'blue') : null),
    profile.objective ? h('div', { class: 'small' }, h('strong', {}, 'Objetivo: '), profile.objective) : null,
    profile.audience ? h('div', { class: 'small' }, h('strong', {}, 'Público: '), profile.audience) : null,
    profile.features?.length ? h('ul', { class: 'small', style: { margin: 0, paddingLeft: '18px' } }, profile.features.map((f) => h('li', {}, f))) : null,
    profile.warnings?.length ? callout('warn', h('ul', { style: { margin: 0, paddingLeft: '18px' } }, profile.warnings.map((w) => h('li', {}, w)))) : null);
  const { close } = modal({
    title: profile.name,
    body: h('div', { class: 'stack stack--sm' }, info, h('hr', { class: 'divider' }),
      profile.id !== active ? item('star', 'Marcar como perfil activo', () => activate(profile.id, navigate)) : null,
      item('builder', profile.editable ? 'Abrir en el Constructor' : 'Ver en el Constructor', () => navigate(`/constructor?p=${profile.id}`)),
      profile.editable ? item('editor', 'Abrir en el Editor de armas', () => navigate(`/editor?p=${profile.id}`)) : null,
      item('generator', 'Vista previa en el Generador', () => navigate(`/generador?p=${profile.id}`)),
      item('layers', 'Crear perfil derivado', () => derive(profile, navigate)),
      item('copy', 'Duplicar (copia completa)', () => duplicate(profile, navigate)),
      profile.tier === 'user' ? item('editor', 'Renombrar', () => rename(profile, navigate)) : null,
      item('weapons', 'Armas afectadas', () => affected(profile.id)),
      item('history', 'Historial de versiones', () => openHistory(profile.id)),
      item('download', 'Exportar', () => exportProfile(profile.id, {})),
      item('download', 'Exportar resuelto (con la herencia aplicada)', () => exportProfile(profile.id, { resolved: true })),
      item('download', 'Exportar en formato legacy (CLI antigua)', () => exportProfile(profile.id, { legacy: true })),
      profile.legacy && profile.editable ? item('refresh', 'Migrar a v8 (con respaldo)', () => migrateOne(profile.id, navigate)) : null,
      profile.tier === 'user' ? item('trash', 'Eliminar (va a la papelera)', () => remove(profile, active, navigate), 'btn--danger') : null),
  });
}

async function derive(profile, navigate) {
  const values = await formDialog({ title: `Crear derivado de ${profile.id}`,
    intro: callout('info', 'Hereda todo de este perfil y guarda solo tus cambios. Se crea como perfil de usuario.'),
    fields: [{ name: 'new_id', label: 'Identificador', value: `${profile.id}_mio` }, { name: 'name', label: 'Nombre', value: `${profile.name} (derivado)` }] });
  if (!values) return;
  try {
    await api.post(`/api/profiles/${profile.id}/derive`, values);
    toast('Perfil derivado creado.');
    navigate(`/constructor?p=${values.new_id}`);
  } catch (error) { toastError(error); }
}

async function affected(id) {
  const body = h('div', {}, loading('Ejecutando el motor…'));
  modal({ title: `Armas afectadas por ${id}`, body, wide: true });
  try {
    const { weapons } = await api.get(`/api/profiles/${id}/affected`);
    mount(body, weapons.length ? h('div', { class: 'table-wrap', style: { maxHeight: '60vh' } }, h('table', { class: 'table table--compact' },
      h('thead', {}, h('tr', {}, h('th', {}, 'Arma'), h('th', {}, 'Categoría'), h('th', {}, 'Campos que cambian'))),
      h('tbody', {}, weapons.map((w) => h('tr', {}, h('td', { class: 'mono small' }, w.weapon), h('td', {}, w.group || '—'), h('td', { class: 'small' }, w.fields.join(', '))))))) :
      callout('ok', 'Aplicarlo no cambia ninguna arma: el servidor ya coincide.'));
  } catch (error) { mount(body, callout('err', error.message)); }
}

async function activate(id, navigate) {
  try {
    await api.post(`/api/profiles/${id}/activate`, {});
    await loadStatus();
    toast(`“${id}” es ahora el perfil activo.`);
    navigate('/perfiles');
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  } catch (error) { toastError(error); }
}

async function duplicate(profile, navigate) {
  const values = await formDialog({ title: `Duplicar ${profile.id}`, fields: [
    { name: 'new_id', label: 'Nuevo identificador', value: `${profile.id}_copia` },
    { name: 'name', label: 'Nombre', value: `${profile.name} (copia)` }] });
  if (!values) return;
  try {
    await api.post(`/api/profiles/${profile.id}/duplicate`, values);
    toast('Perfil duplicado.');
    navigate(`/constructor?p=${values.new_id}`);
  } catch (error) { toastError(error); }
}

async function rename(profile, navigate) {
  const values = await formDialog({ title: `Renombrar ${profile.id}`, fields: [
    { name: 'new_id', label: 'Identificador', value: profile.id, hint: 'Si cambias el id, los perfiles derivados se actualizan solos.' },
    { name: 'name', label: 'Nombre', value: profile.name }] });
  if (!values) return;
  try {
    const result = await api.post(`/api/profiles/${profile.id}/rename`, values);
    if (store.draft?.id === profile.id) store.draft = null;
    await loadStatus();
    toast('Perfil renombrado.', { detail: result.updated_children?.length ? `Derivados actualizados: ${result.updated_children.join(', ')}` : '' });
    navigate('/perfiles');
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  } catch (error) { toastError(error); }
}

async function remove(profile, active, navigate) {
  if (profile.id === active) { toast('No puedes eliminar el perfil activo. Activa otro primero.', { type: 'warn' }); return; }
  const ok = await confirmDialog({ title: `Eliminar ${profile.id}`, danger: true, confirmLabel: 'Mover a la papelera',
    message: 'El archivo se mueve a data/trash/ y su historial se conserva. No afecta al servidor.' });
  if (!ok) return;
  try {
    await api.del(`/api/profiles/${profile.id}`);
    if (store.draft?.id === profile.id) store.draft = null;
    toast('Perfil movido a la papelera.');
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  } catch (error) { toastError(error); }
  void navigate;
}

async function exportProfile(id, { resolved = false, legacy = false }) {
  try {
    const data = await api.get(`/api/profiles/${id}/export?resolved=${resolved ? 1 : 0}&legacy=${legacy ? 1 : 0}`);
    downloadText(`${id}${resolved ? '.resuelto' : ''}${legacy ? '.legacy' : ''}.json`, `${JSON.stringify(data.profile, null, 2)}\n`);
  } catch (error) { toastError(error); }
}

async function migrateOne(id, navigate) {
  const ok = await confirmDialog({ title: `Migrar ${id} a v8`, confirmLabel: 'Migrar',
    message: 'El archivo actual se guarda en el historial y se puede revertir. El comportamiento del perfil no cambia (engine_defaults=true).' });
  if (!ok) return;
  try {
    const result = await api.post(`/api/profiles/${id}/migrate`, {});
    toast('Perfil migrado.', { detail: result.notes.join(' ') });
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  } catch (error) { toastError(error); }
  void navigate;
}

async function migrateAll() {
  try {
    const preview = await api.post('/api/profiles/migrate-all', { dry_run: true });
    const pending = preview.results.filter((r) => r.would_migrate);
    const ok = await confirmDialog({ title: 'Migrar perfiles legacy', confirmLabel: `Migrar ${pending.length}`,
      message: h('div', { class: 'stack stack--sm' },
        h('p', {}, 'Se migrarán estos perfiles. Cada archivo anterior queda en data/history/ y se puede revertir desde su historial.'),
        h('pre', { class: 'code' }, pending.map((r) => r.id).join('\n'))) });
    if (!ok) return;
    await api.post('/api/profiles/migrate-all', { dry_run: false });
    toast(`${pending.length} perfiles migrados a v8.`);
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  } catch (error) { toastError(error); }
}

export async function openHistory(id) {
  const body = h('div', {}, loading());
  modal({ title: `Historial de ${id}`, body, wide: true });
  try {
    const { history } = await api.get(`/api/profiles/${id}/history`);
    const viewer = h('div', {});
    mount(body, history.length ? h('div', { class: 'grid grid--2' },
      h('div', { class: 'stack stack--sm' }, history.map((entry) => h('div', { class: 'card', style: { padding: '10px 12px' } },
        h('div', { class: 'row row--between' },
          h('div', {}, h('strong', {}, actionLabel(entry.action)), ' ', h('span', { class: 'muted small' }, date(entry.ts))),
          entry.revision ? badge(`rev. ${entry.revision}`, 'outline') : null),
        entry.note ? h('div', { class: 'small muted' }, entry.note) : null,
        h('div', { class: 'row', style: { marginTop: '6px' } },
          !entry.file ? h('span', { class: 'small muted' }, 'Sin versión previa (creación).') : h('button', { class: 'btn btn--sm', onclick: async () => {
            mount(viewer, loading());
            const { profile } = await api.get(`/api/profiles/${id}/history/${entry.file}`);
            mount(viewer, h('div', { class: 'stack stack--sm' }, h('div', { class: 'small muted' }, `Contenido antes de “${actionLabel(entry.action)}”`), jsonView(profile)));
          } }, icon('eye'), 'Ver'),
          !entry.file ? null : h('button', { class: 'btn btn--sm', onclick: async () => {
            const ok = await confirmDialog({ title: 'Restaurar versión', confirmLabel: 'Restaurar',
              message: 'Se restaura esta versión. La versión actual queda guardada en el historial.' });
            if (!ok) return;
            try {
              await api.post(`/api/profiles/${id}/restore`, { file: entry.file });
              if (store.draft?.id === id) await openDraft(id, { force: true });
              toast('Versión restaurada.');
              openHistory(id);
            } catch (error) { toastError(error); }
          } }, icon('undo'), 'Restaurar'))))),
      h('div', {}, viewer)) : empty('Sin versiones anteriores todavía.', 'history'));
  } catch (error) { mount(body, callout('err', error.message)); }
}

function actionLabel(action) {
  return { edit: 'Edición', create: 'Creación', import: 'Importación', migrate: 'Migración a v8', restore: 'Restauración',
    rename: 'Renombrado', renamed: 'Renombrado', delete: 'Eliminado', parent_renamed: 'Cambio de herencia' }[action] || action;
}

async function compareProfiles(ids) {
  const options = [{ value: 'original', label: 'Valores originales (.bak)' }, { value: 'current', label: 'META actual' }, ...ids.map((id) => ({ value: id, label: id }))];
  const values = await formDialog({ title: 'Comparar', fields: [
    { name: 'a', label: 'Lado A', type: 'select', value: 'original', options },
    { name: 'b', label: 'Lado B', type: 'select', value: store.status.active_profile, options },
    { name: 'weapon', label: 'Arma concreta (opcional)', placeholder: 'WEAPON_PISTOL', hint: 'Con un arma se muestra también de dónde sale cada valor.' }],
  submitLabel: 'Comparar' });
  if (!values) return;
  const side = (v) => (['original', 'current'].includes(v) ? { source: v } : { profile_id: v });
  showComparison(side(values.a), side(values.b), values.a, values.b, values.weapon ? [values.weapon.toUpperCase()] : null);
}

const STATUS = { inherited: ['H', 'heredado', 'blue'], overridden: ['S', 'sobrescrito', 'purple'], own: ['P', 'del perfil', 'purple'],
  rule: ['R', 'regla del motor', 'warn'], original: ['O', 'original', 'outline'], ignored: ['X', 'sin efecto', 'err'] };

function statusBadge(status, source) {
  if (!status) return null;
  const [letter, label, variant] = STATUS[status] || ['?', status, 'outline'];
  const node = badge(letter, variant);
  node.title = `${label}${source ? ` — ${source}` : ''}`;
  return node;
}

export async function showComparison(a, b, labelA, labelB, weapons = null) {
  const body = h('div', {}, loading('Ejecutando ambos lados con el motor…'));
  modal({ title: `${labelA}  ↔  ${labelB}`, body, wide: true });
  try {
    const result = await api.post('/api/profiles/compare', { a, b, weapons, keys: weapons ? ['damage', 'network_player_damage_modifier', 'network_headshot', 'hit_limbs',
      'weapon_range', 'falloff_min', 'falloff_max', 'falloff_modifier', 'time_between_shots', 'clip_size', 'reload_time_mp', 'accuracy_spread',
      'recoil_accuracy_max', 'recoil_shake_amplitude', 'recoil_recovery_rate', 'bullets_in_batch'] : null });
    const state = { tab: 'effects' };
    const arrow = { up: ['↑', 'delta-up'], down: ['↓', 'delta-down'], same: ['=', 'muted'], changed: ['≠', ''] };
    const label = (key) => store.params.get(key)?.label || key;
    const draw = () => mount(body,
      h('div', { class: 'row small' }, badge(`${result.summary.weapons_affected} armas con resultado distinto`, 'purple'),
        result.structural ? badge(`${result.summary.structural_changes} diferencias en el JSON`, 'outline') : null,
        weapons ? h('span', { class: 'muted' }, 'H heredado · S sobrescrito · P del perfil · R regla del motor · O original (pasa el ratón para ver el detalle)') : null),
      tabs([{ id: 'effects', label: 'Efecto por arma', count: result.effects.length },
        ...(result.structural ? [{ id: 'json', label: 'Diferencias en el JSON', count: result.summary.structural_changes }] : [])], state.tab, (id) => { state.tab = id; draw(); }),
      state.tab === 'effects'
        ? (result.effects.length ? h('div', { class: 'table-wrap', style: { maxHeight: '60vh' } }, h('table', { class: 'table table--compact' },
          h('thead', {}, h('tr', {}, h('th', {}, 'Arma'), h('th', {}, 'Parámetro'), h('th', { class: 'num' }, labelA), h('th', { class: 'num' }, labelB), h('th', {}, ''))),
          h('tbody', {}, result.effects.flatMap((e) => Object.entries(e.fields).map(([key, v], i) => h('tr', {},
            h('td', { class: 'mono small' }, i === 0 ? e.weapon : ''), h('td', { class: 'small' }, label(key)),
            h('td', { class: 'num' }, statusBadge(v.a_status, v.a_source), ' ', fmt(v.a)),
            h('td', { class: 'num' }, statusBadge(v.b_status, v.b_source), ' ', fmt(v.b)),
            h('td', { class: arrow[v.direction]?.[1] || '' }, arrow[v.direction]?.[0] || ''))))))) : callout('ok', 'Ambos lados producen exactamente el mismo resultado en el pack.'))
        : h('div', { class: 'stack' },
          result.structural.changed.length ? h('div', {}, h('h3', {}, 'Cambiados'), h('table', { class: 'table table--compact' }, h('tbody', {},
            result.structural.changed.slice(0, 400).map((c) => h('tr', {}, h('td', { class: 'mono small' }, c.path), h('td', { class: 'num' }, fmt(c.a)), h('td', { class: 'num' }, fmt(c.b))))))) : null,
          result.structural.added.length ? h('div', {}, h('h3', {}, `Solo en ${labelB}`), h('pre', { class: 'code' }, result.structural.added.join('\n'))) : null,
          result.structural.removed.length ? h('div', {}, h('h3', {}, `Solo en ${labelA}`), h('pre', { class: 'code' }, result.structural.removed.join('\n'))) : null));
    draw();
  } catch (error) { mount(body, callout('err', error.message)); }
}

function fmt(value) {
  if (Array.isArray(value)) return value.join(' ');
  if (typeof value === 'number') return num(value, 4);
  if (value === undefined) return '—';
  if (typeof value === 'object' && value !== null) return JSON.stringify(value);
  return String(value);
}

void issueList; void setLoading;
