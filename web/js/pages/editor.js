import { api } from '../core/api.js';
import { debounce, h, icon, mount, setLoading } from '../core/dom.js';
import { num, same } from '../core/format.js';
import {
  countOverrides, effectiveModule, getFlags, getHeadshot, getQbxRecoil, inList, scopeLabel, scopeOp,
} from '../core/profile-edit.js';
import { applyOps, protectedNotice } from '../core/ops.js';
import { draftPreview, loadCatalog, openDraft, store, subscribe } from '../core/store.js';
import { helpFor, methodBadge, paramRow } from '../components/param-row.js';
import { badge, callout, card, empty, help, issueList, loading, segmented, tabs, toast, toastError } from '../components/ui.js';

const TABS = [
  { id: 'damage', label: 'Daño', icon: 'target' },
  { id: 'headshot', label: 'Cabeza', icon: 'crosshair' },
  { id: 'range', label: 'Alcance', icon: 'ruler' },
  { id: 'fire_rate', label: 'Cadencia', icon: 'zap' },
  { id: 'recoil', label: 'Recoil', icon: 'activity' },
  { id: 'accuracy', label: 'Precisión', icon: 'aperture' },
  { id: 'ammo', label: 'Munición', icon: 'package' },
  { id: 'projectile', label: 'Proyectil', icon: 'share' },
  { id: 'flags', label: 'Flags', icon: 'flag' },
  { id: 'resource', label: 'Recursos', icon: 'layers' },
  { id: 'advanced', label: 'Avanzado', icon: 'settings' },
];
const ADVANCED_SECTIONS = ['force', 'aim', 'camera', 'hud', 'rumble', 'animation', 'identity'];

export async function render({ root, params, setTitle, navigate, isCurrent }) {
  setTitle('Editor de armas', 'Ajustes individuales sobre el perfil en edición');
  const [catalog] = await Promise.all([loadCatalog()]);
  const profileId = params.get('p') || store.draft?.id || store.status.active_profile;
  await openDraft(profileId);
  if (!isCurrent()) return null;

  const weapons = catalog.weapons.filter((w) => w.in_meta && !w.internal);
  const state = {
    weapon: params.get('w') || (weapons.find((w) => w.name === 'WEAPON_PISTOL') || weapons[0])?.name,
    scope: params.get('s') || 'weapon',
    tab: params.get('t') || 'damage',
    query: '',
    detail: null,
    preview: null,
    previewing: false,
  };

  const listHost = h('div', { style: { maxHeight: 'calc(100vh - 230px)', overflowY: 'auto' } });
  const editorHost = h('div', { class: 'stack' });
  const search = h('input', { class: 'input', placeholder: 'Buscar arma…', spellcheck: 'false' });
  search.addEventListener('input', debounce(() => { state.query = search.value.trim().toLowerCase(); drawList(); }, 120));

  mount(root, h('div', { class: 'grid grid--side-left' },
    h('div', { class: 'card', style: { padding: '12px', position: 'sticky', top: '76px' } },
      h('div', { class: 'stack stack--sm' },
        profilePicker(profileId, navigate),
        h('label', { class: 'search' }, icon('search'), search),
        listHost)),
    editorHost));

  function drawList() {
    const profile = store.draft.profile;
    const rows = weapons.filter((w) => !state.query || `${w.name} ${w.label}`.toLowerCase().includes(state.query));
    mount(listHost, rows.length ? rows.slice(0, 400).map((w) => {
      const count = countOverrides(profile, w.name);
      return h('a', {
        href: `#/editor?w=${w.name}&p=${store.draft.id}`,
        class: 'row', style: {
          padding: '7px 9px', borderRadius: '8px', gap: '8px', color: 'inherit', textDecoration: 'none',
          background: w.name === state.weapon ? 'var(--purple-soft)' : '',
        },
        onclick: (e) => { e.preventDefault(); selectWeapon(w.name); },
      },
      h('div', { class: 'grow weapon-cell' }, h('strong', { style: { fontSize: '12.5px' } }, w.label), h('small', {}, w.name)),
      count ? badge(String(count), 'purple') : null);
    }) : empty('Sin resultados.'));
  }

  async function selectWeapon(name) {
    state.weapon = name;
    state.detail = null;
    history.replaceState(null, '', `#/editor?w=${name}&p=${store.draft.id}&s=${state.scope}&t=${state.tab}`);
    drawList();
    await loadDetail();
  }

  async function loadDetail() {
    mount(editorHost, loading());
    try {
      state.detail = await api.get(`/api/catalog/weapons/${encodeURIComponent(state.weapon)}`);
      if (!isCurrent()) return;
      drawEditor();
      refreshPreview();
    } catch (error) {
      mount(editorHost, callout('err', error.message));
    }
  }

  const refreshPreview = debounce(async () => {
    state.previewing = true;
    drawPreviewBox();
    try {
      state.preview = await draftPreview();
    } catch (error) {
      state.preview = { error };
    }
    state.previewing = false;
    if (isCurrent()) { drawEditor(); }
  }, 450);

  function refValues() {
    const defs = state.detail?.definitions || [];
    const primary = defs[defs.length - 1];
    const current = primary?.values || {};
    const original = primary?.original_values || current;
    const proposed = state.preview?.weapons?.[state.weapon]?.proposed;
    return { current, original, proposed };
  }

  function currentScope() {
    if (state.scope === 'group') return { type: 'group', name: state.detail?.group || 'UNKNOWN' };
    if (state.scope === 'defaults') return { type: 'defaults', name: '*' };
    return { type: 'weapon', name: state.weapon };
  }

  const previewBox = h('div', {});
  function drawPreviewBox() {
    const p = state.preview;
    if (state.previewing) { mount(previewBox, h('div', { class: 'row small muted' }, h('span', { class: 'spinner' }), 'Calculando con el motor…')); return; }
    if (!p) { mount(previewBox); return; }
    if (p.error) { mount(previewBox, callout('err', p.error.message)); return; }
    const entry = p.weapons?.[state.weapon];
    const changes = entry ? Object.keys(entry.changes || {}).length : 0;
    const relevant = (p.issues || []).filter((i) => (i.path || '').includes(state.weapon) || (i.weapons || []).includes(state.weapon)
      || (state.scope !== 'weapon' && (i.path || '').includes(currentScope().name)));
    mount(previewBox, h('div', { class: 'stack stack--sm' },
      h('div', { class: 'row small' },
        entry?.processed === false ? badge(`omitida: ${entry.skipped_reason}`, 'warn') : badge(changes ? `${changes} campo(s) cambiarían` : 'sin cambios frente al META', changes ? 'purple' : 'ok'),
        badge(`perfil: ${p.summary.weapons_changed} armas · ${p.summary.files_changed} archivos`, 'outline'),
        p.idempotency?.idempotent === false ? badge('no repetible', 'warn') : null),
      relevant.length ? issueList(relevant) : null));
  }

  function drawEditor() {
    if (!state.detail) return;
    const d = state.detail;
    const profile = store.draft.profile;
    const scope = currentScope();
    const ref = refValues();
    const header = h('div', { class: 'card card--accent' },
      h('div', { class: 'row row--between row--top' },
        h('div', {},
          h('h2', {}, d.label, ' ', h('span', { class: 'muted mono small' }, d.name)),
          h('div', { class: 'row small muted', style: { marginTop: '6px' } },
            badge(d.category.label, 'blue'), d.custom ? badge('personalizada') : badge('oficial', 'outline'),
            d.definition_count > 1 ? badge(`${d.definition_count} definiciones`, 'warn') : null,
            h('span', {}, `RPM actual: ${d.rpm ? Math.round(d.rpm) : '—'}`))),
        h('div', { class: 'row' },
          h('a', { class: 'btn btn--sm', href: `#/simulador?w=${d.name}&p=${store.draft.id}` }, icon('simulator'), 'Simular'),
          h('a', { class: 'btn btn--sm btn--ghost', href: `#/armamento?w=${d.name}` }, icon('eye'), 'Detalle'))),
      h('div', { class: 'row', style: { marginTop: '14px' } },
        h('span', { class: 'label' }, 'Aplicar cambios a:'),
        segmented([
          { value: 'weapon', label: 'Esta arma' },
          { value: 'group', label: `Categoría ${d.group || '—'}` },
          { value: 'defaults', label: 'Global' },
        ], state.scope, (v) => { state.scope = v; history.replaceState(null, '', `#/editor?w=${state.weapon}&p=${store.draft.id}&s=${v}&t=${state.tab}`); drawEditor(); }),
        help({ title: 'Ámbito', text: 'Arma: solo esta arma. Categoría: todas las armas del mismo <Group>. Global: todas las armas que procese el perfil. El valor por arma tiene prioridad sobre categoría y global.', doc: 'perfiles/precedencia' })),
      state.scope === 'weapon' ? exceptionsRow(profile, d.name) : null,
      h('div', { style: { marginTop: '12px' } }, previewBox));
    drawPreviewBox();

    let body;
    if (state.tab === 'headshot') body = headshotTab(profile, scope, ref);
    else if (state.tab === 'flags') body = flagsTab(profile, scope, ref);
    else if (state.tab === 'resource') body = resourceTab(profile, d);
    else if (state.tab === 'advanced') body = h('div', { class: 'stack' }, ADVANCED_SECTIONS.map((section) => sectionCard(section, scope, ref, { includeAdvanced: true })));
    else body = sectionCard(state.tab, scope, ref, { includeAdvanced: false, extraAdvanced: true });

    mount(editorHost, protectedNotice(navigate, `/editor?w=${state.weapon}`), header,
      tabs(TABS.map((t) => ({ ...t })), state.tab, (id) => { state.tab = id; history.replaceState(null, '', `#/editor?w=${state.weapon}&p=${store.draft.id}&s=${state.scope}&t=${id}`); drawEditor(); }),
      moduleNotice(profile, state.tab),
      body);
  }

  function sectionCard(sectionId, scope, ref, { includeAdvanced, extraAdvanced }) {
    const section = store.registry.sections.find((s) => s.id === sectionId);
    const specs = store.registry.params.filter((p) => p.section === sectionId && p.value_type !== 'flags' && p.value_type !== 'text');
    const main = specs.filter((p) => includeAdvanced || !p.advanced);
    const advanced = extraAdvanced ? specs.filter((p) => p.advanced) : [];
    const readonly = store.registry.params.filter((p) => p.section === sectionId && p.method === 'readonly');
    const rowsFor = (list) => list.map((spec) => paramRow(spec, scope, { original: ref.original[spec.key], current: ref.current[spec.key], proposed: ref.proposed?.[spec.key] }));
    if (!main.length && !readonly.length && !advanced.length) return null;
    return h('section', { class: 'card card--flush' },
      h('div', { class: 'card__head', style: { padding: '14px 14px 0' } }, icon(section?.icon || 'circle'), h('h2', {}, section?.label || sectionId),
        h('span', { class: 'muted small' }, section?.summary || '')),
      h('div', {}, rowsFor(main)),
      advanced.length ? h('details', { style: { borderTop: '1px solid var(--line)' } },
        h('summary', { style: { padding: '10px 14px', cursor: 'pointer', color: 'var(--purple-2)', fontSize: '12.5px' } }, `Avanzados (${advanced.length})`),
        rowsFor(advanced)) : null,
      readonly.length ? h('div', { style: { padding: '10px 14px', borderTop: '1px solid var(--line)' } },
        h('div', { class: 'label', style: { marginBottom: '6px' } }, 'Solo lectura'),
        h('dl', { class: 'kv small' }, readonly.flatMap((spec) => [h('dt', {}, spec.label, ' ', helpFor(spec)), h('dd', { class: 'mono' }, ref.current[spec.key] ?? '—')]))) : null);
  }

  function moduleNotice(profile, tab) {
    const moduleFor = { damage: 'damage', range: 'range', fire_rate: 'fire_rate', recoil: 'recoil', accuracy: 'accuracy', ammo: 'reload', headshot: 'headshot' }[tab];
    if (!moduleFor) return null;
    const mode = effectiveModule(profile, moduleFor);
    if (tab === 'headshot') return null;
    if (mode === 'original') {
      return callout('warn', [h('strong', {}, `modules.${moduleFor} = original. `), 'Los valores de esta sección escritos en el perfil no se aplican. Al editar uno, el panel te propondrá activarlo.']);
    }
    if (!['configured', 'normal'].includes(mode) || (['recoil', 'accuracy'].includes(moduleFor) && mode !== 'configured')) {
      return callout('info', [h('strong', {}, `modules.${moduleFor} = ${mode}. `), 'Es un preset: algunos campos de esta sección se recalculan después de tus valores. Revisa la columna “Propuesto”.']);
    }
    return null;
  }

  function exceptionsRow(profile, weapon) {
    const toggle = (list, label, hint) => {
      const input = h('input', { type: 'checkbox', checked: inList(profile, list, weapon) });
      input.disabled = !store.draft.editable;
      input.addEventListener('change', () => applyOps([{ op: 'set_list', list, weapon, enabled: input.checked }], { quiet: true }));
      return h('label', { class: 'check', title: hint }, input, label);
    };
    return h('div', { class: 'row', style: { marginTop: '10px' } },
      h('span', { class: 'label' }, 'Excepciones:'),
      toggle('ignore_weapons', 'No tocar esta arma (ignore_weapons)', 'El motor la omite por completo.'),
      toggle('harmless_weapons', 'Inofensiva: daño 0 (harmless_weapons)', 'Fuerza daño y multiplicadores a 0.'),
      help({ title: 'Excepciones', text: 'Una arma ignorada no se modifica aunque tenga valores en el perfil. Una inofensiva se fuerza a daño 0 al final, por encima de cualquier otra regla.', doc: 'perfiles/excepciones' }));
  }

  function headshotTab(profile, scope, ref) {
    const policy = getHeadshot(profile, scope);
    const globalMode = effectiveModule(profile, 'headshot');
    const isGlobal = scope.type === 'defaults';
    const modeValue = isGlobal ? globalMode : (policy.mode || 'inherit');
    const modeSelect = h('select', { class: 'select', style: { width: '240px' } },
      (isGlobal
        ? [['original', 'No tocar la cabeza (original)'], ['off', 'Sin multiplicador de cabeza'], ['normal', 'Headshot normal'], ['onetap', 'One-tap']]
        : [['inherit', `Heredar (${globalMode})`], ['off', 'Sin multiplicador de cabeza'], ['normal', 'Headshot normal'], ['onetap', 'One-tap']]
      ).map(([value, label]) => h('option', { value, selected: value === modeValue }, label)));
    modeSelect.disabled = !store.draft.editable;
    modeSelect.addEventListener('change', () => applyOps([{ op: 'set_headshot', scope: scopeOp(scope), values: { mode: modeSelect.value } }]));
    const numberField = (key, label, hint, step = 0.1) => {
      const input = h('input', { class: 'input input--num', type: 'number', step, value: policy[key] ?? '', placeholder: 'heredar' });
      input.disabled = !store.draft.editable;
      input.addEventListener('change', () => applyOps([{ op: 'set_headshot', scope: scopeOp(scope), values: { [key]: input.value === '' ? null : Number(input.value) } }]));
      return h('div', { class: 'field' }, h('label', {}, label, ' ', help({ title: label, text: hint, doc: 'parametros/cabeza' })), input);
    };
    const boolField = (key, label, hint) => {
      const input = h('input', { type: 'checkbox', checked: policy[key] === true });
      input.disabled = !store.draft.editable;
      input.addEventListener('change', () => applyOps([{ op: 'set_headshot', scope: scopeOp(scope), values: { [key]: input.checked ? true : null } }], { quiet: true }));
      return h('label', { class: 'check', title: hint }, input, label, ' ', help({ title: label, text: hint, doc: 'parametros/cabeza' }));
    };
    const disabled = globalMode === 'original';
    const fields = ['headshot_player', 'network_headshot', 'headshot_ai', 'min_headshot_player', 'max_headshot_player'];
    return h('div', { class: 'stack' },
      callout('purple', [h('strong', {}, 'Cómo funciona la cabeza. '),
        'Los multiplicadores y distancias de cabeza los escribe la política de cabeza (no se editan uno a uno). ',
        'Para que el multiplicador funcione contra jugadores, el objetivo debe tener critical hits activos (os_headshot_guard o sin scripts que los apaguen: ver Diagnóstico).']),
      disabled && !isGlobal ? callout('warn', 'La política global está en “original”: ninguna política por arma/categoría tiene efecto hasta activarla en Global.') : null,
      card({ title: `Política de cabeza — ${scopeLabel(scope)}`, iconName: 'crosshair', body: h('div', { class: 'stack' },
        h('div', { class: 'row' }, h('span', { class: 'label' }, 'Modo'), modeSelect),
        h('div', { class: 'grid grid--3' },
          numberField('multiplier', 'Multiplicador', 'Multiplica el daño en la cabeza (jugador, red y NPC). En one-tap se usa como valor fijo salvo que actives el cálculo dinámico.'),
          numberField('distance', 'Distancia máxima (m)', 'Más allá de esta distancia el disparo a la cabeza cuenta como torso.', 1),
          numberField('target_effective_health', 'Vida objetivo one-tap', 'Vida + blindaje que un disparo a la cabeza debe superar (one-tap). 100 = jugador sin blindaje.', 1)),
        h('div', { class: 'row' },
          boolField('dynamic_multiplier_from_damage', 'Multiplicador calculado desde el daño (one-tap)', 'Calcula el multiplicador justo para matar según el daño base final, en vez de usar un valor fijo alto.'),
          boolField('no_falloff', 'Sin caída de daño dentro de la distancia (one-tap)', 'Fuerza la caída a 1.0 hasta la distancia de cabeza.'),
          boolField('bypass_helmets', 'Atravesar cascos (one-tap)', 'Agrega IgnoreHelmets/ArmourPenetrating y ajusta LightlyArmouredDamageModifier.')),
      ) }),
      card({ title: 'Valores resultantes', iconName: 'eye', body: h('table', { class: 'table table--compact' },
        h('thead', {}, h('tr', {}, h('th', {}, 'Campo'), h('th', { class: 'num' }, 'Original'), h('th', { class: 'num' }, 'Actual'), h('th', { class: 'num' }, 'Propuesto'))),
        h('tbody', {}, fields.map((key) => {
          const spec = store.params.get(key);
          const changed = ref.proposed && !same(ref.proposed[key], ref.current[key]);
          return h('tr', {}, h('td', {}, spec.label, ' ', helpFor(spec)), h('td', { class: 'num muted' }, num(ref.original[key])),
            h('td', { class: 'num' }, num(ref.current[key])), h('td', { class: 'num', style: { color: changed ? 'var(--purple-2)' : '' } }, ref.proposed ? num(ref.proposed[key]) : '—'));
        }))) }),
      card({ title: 'Precisión mínima para contar headshot', iconName: 'aperture', body: h('div', {},
        h('div', { class: 'small muted', style: { marginBottom: '8px' } }, 'Estos dos campos sí se editan por arma; requieren una política de cabeza activa (modo distinto de “original”).'),
        ['recoil_accuracy_to_allow_headshot_player', 'recoil_accuracy_to_allow_headshot_ai'].map((key) => paramRow(store.params.get(key), scope,
          { original: ref.original[key], current: ref.current[key], proposed: ref.proposed?.[key] }))) }),
    );
  }

  function flagsTab(profile, scope, ref) {
    const flags = getFlags(profile, scope);
    const currentFlags = ref.current.weapon_flags || [];
    const proposedFlags = state.preview?.weapons?.[state.weapon]?.proposed_flags;
    const datalist = h('datalist', { id: 'known-flags' }, store.registry.known_flags.map((f) => h('option', { value: f })));
    const listEditor = (kind, label, variant) => {
      const input = h('input', { class: 'input input--sm', list: 'known-flags', placeholder: 'Nombre de la flag', style: { width: '240px' }, spellcheck: 'false' });
      const add = () => {
        const value = input.value.trim();
        if (!value) return;
        if (!store.registry.known_flags.includes(value)) toast(`“${value}” no es una flag conocida.`, { type: 'warn', detail: 'Se agregará igual; revisa que exista en el juego.' });
        applyOps([{ op: kind === 'add' ? 'add_flag' : 'remove_flag', scope: scopeOp(scope), flag: value }], { quiet: true });
      };
      input.addEventListener('keydown', (e) => { if (e.key === 'Enter') add(); });
      return h('div', { class: 'stack stack--sm' },
        h('div', { class: 'label' }, label),
        h('div', { class: 'chips' }, flags[kind].length ? flags[kind].map((f) => h('span', { class: `tag tag--${variant}` }, f,
          h('button', { title: 'Quitar', onclick: () => applyOps([{ op: 'clear_flag', scope: scopeOp(scope), flag: f }], { quiet: true }) }, '×')))
          : h('span', { class: 'muted small' }, 'Ninguna')),
        h('div', { class: 'row' }, input, h('button', { class: 'btn btn--sm', onclick: add }, icon('plus'), 'Agregar')));
    };
    return h('div', { class: 'stack' }, datalist,
      callout('info', 'Las flags se editan agregando o quitando nombres concretos; el resto de flags del META se conservan tal cual. Flags como Automatic u OnlyFireOneShotPerTriggerPress cambian el gatillo: compruébalo en el juego.'),
      card({ title: `Flags — ${scopeLabel(scope)}`, iconName: 'flag', body: h('div', { class: 'grid grid--2' },
        listEditor('add', 'Agregar', 'add'), listEditor('remove', 'Quitar', 'remove')) }),
      card({ title: 'Flags actuales del META', iconName: 'eye', body: h('div', { class: 'stack stack--sm' },
        h('div', { class: 'chips' }, currentFlags.length ? currentFlags.map((f) => h('span', { class: 'tag' }, f)) : h('span', { class: 'muted' }, '—')),
        proposedFlags ? h('div', { class: 'small muted' }, 'Propuestas: ', proposedFlags.join(' ')) : null) }));
  }

  function resourceTab(profile, d) {
    const value = getQbxRecoil(profile, d.name);
    const current = d.qbx_recoil;
    const input = h('input', { class: 'input input--num', type: 'number', step: 0.05, min: 0, max: 10, value: typeof value === 'number' ? value : '', placeholder: current ?? 'sin entrada', disabled: !store.draft.editable });
    input.addEventListener('change', () => {
      applyOps([{ op: 'set_qbx_recoil', weapon: d.name, value: input.value === '' ? 'unset' : Number(input.value) }], { quiet: true });
    });
    const removeBtn = h('button', { class: 'btn btn--sm btn--ghost', onclick: () => applyOps([{ op: 'set_qbx_recoil', weapon: d.name, value: false }], { quiet: true }) }, 'Desactivar la entrada');
    const resourceSpec = store.registry.resource.find((r) => r.key === 'qbx.recoil');
    return h('div', { class: 'stack' },
      card({ title: 'Recoil vertical de cámara (qbx_recoils)', iconName: 'activity', body: h('div', { class: 'stack' },
        h('div', { class: 'row' }, methodBadge('resource'), h('span', { class: 'small muted' }, resourceSpec?.description || '')),
        h('dl', { class: 'kv' },
          h('dt', {}, 'Valor actual en el servidor'), h('dd', {}, current ?? 'Sin entrada (sin recoil vertical por script)'),
          h('dt', {}, 'Valor en el perfil'), h('dd', {}, value === undefined || value === null ? 'Sin cambio' : value === false ? 'Desactivar la entrada' : String(value))),
        h('div', { class: 'row' }, h('span', { class: 'label' }, 'Nuevo valor'), input, removeBtn,
          help({ title: 'qbx_recoils', text: 'Grados de cámara que sube cada disparo (aprox.). 0.1–0.3 suave, 0.5–0.9 fuerte. Vacío = no cambiar. El Generador edita qbx_smallresources/qbx_recoils/config.lua con respaldo; hay que reiniciar qbx_smallresources.', doc: 'fivem/qbx-recoils' })),
      ) }),
      card({ title: 'ox_inventory (solo lectura)', iconName: 'package', body: d.ox ? h('dl', { class: 'kv' },
        store.registry.resource.filter((r) => r.key.startsWith('ox.')).flatMap((r) => [h('dt', {}, r.label, ' ', help({ title: r.label, text: r.description })), h('dd', {}, String(d.ox[r.key.slice(3)] ?? '—'))]))
        : callout('warn', 'El arma no está en ox_inventory.') }),
      card({ title: 'Mecanismos no disponibles', iconName: 'info', body: h('div', { class: 'stack stack--sm' },
        store.registry.unsupported.map((u) => h('div', {}, h('strong', {}, u.label), ' ', methodBadge('unsupported'), h('div', { class: 'small muted' }, u.description)))) }));
  }

  const unsubscribe = subscribe((event) => {
    if (event === 'draft' && isCurrent()) { drawList(); drawEditor(); refreshPreview(); }
  });
  drawList();
  await loadDetail();
  return () => unsubscribe();
}

function profilePicker(currentId, navigate) {
  const select = h('select', { class: 'select', title: 'Perfil en edición' });
  api.get('/api/profiles').then((data) => {
    mount(select, data.profiles.map((p) => h('option', { value: p.id, selected: p.id === currentId }, `${p.id}${p.id === data.active ? ' ★' : ''}`)));
  }).catch(toastError);
  select.addEventListener('change', async () => {
    try {
      await openDraft(select.value);
      navigate(`/editor?p=${select.value}`);
    } catch (error) { toastError(error); }
  });
  return h('div', { class: 'field' }, h('label', {}, 'Perfil en edición'), select);
}

void setLoading;
