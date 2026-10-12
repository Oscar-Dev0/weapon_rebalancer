import { api } from '../core/api.js';
import { h, icon, mount, setLoading } from '../core/dom.js';
import { num } from '../core/format.js';
import { countOverrides, effectiveModule, getHeadshot, getQbxRecoil, scopeOp } from '../core/profile-edit.js';
import { applyOps, protectedNotice } from '../core/ops.js';
import { draftPreview, loadCatalog, openDraft, saveDraft, store, subscribe } from '../core/store.js';
import { paramRow } from '../components/param-row.js';
import {
  badge, callout, card, confirmDialog, empty, help, issueList, jsonView, loading, segmented, toast, toastError,
} from '../components/ui.js';

const STEPS = [
  { id: 'general', label: 'General' },
  { id: 'modules', label: 'Módulos' },
  { id: 'global', label: 'Global' },
  { id: 'groups', label: 'Categorías' },
  { id: 'weapons', label: 'Armas' },
  { id: 'exceptions', label: 'Excepciones' },
  { id: 'rules', label: 'Reglas avanzadas' },
  { id: 'resources', label: 'Recursos' },
  { id: 'review', label: 'Revisión' },
];

const MODULE_HELP = {
  damage: { label: 'Daño', values: { original: 'No tocar daño', configured: 'Usar los valores del perfil', normal: 'Igual que configured', none: 'Daño 0 en todo', head_only: 'Cuerpo casi 0 (solo cabeza)', low: 'Perfil ×0.72', high: 'Perfil ×1.20', lethal: 'Perfil ×1.45' } },
  armour: { label: 'Blindaje ligero', values: { original: 'No tocar', configured: 'Valores del perfil', none: '0', normal: '1.0', piercing: '1.5', max: '2.0' } },
  recoil: { label: 'Recoil', values: { original: 'No tocar', configured: 'Valores del perfil', none: 'Preset sin recoil', low: 'Preset bajo', normal: 'Preset normal', high: 'Preset alto' } },
  accuracy: { label: 'Precisión', values: { original: 'No tocar', configured: 'Valores del perfil', laser: 'Preset láser', high: 'Preset alta', normal: 'Preset normal', low: 'Preset baja' } },
  range: { label: 'Alcance', values: { original: 'No tocar', configured: 'Valores del perfil', short: 'Perfil ×0.65', normal: 'Igual que configured', long: 'Perfil ×1.35', very_long: 'Perfil ×1.75' } },
  fire_rate: { label: 'Cadencia', values: { original: 'No tocar', configured: 'Valores del perfil', slow: 'TBS ×1.25', normal: 'Igual que configured', fast: 'TBS ×0.82', very_fast: 'TBS ×0.68' } },
  reload: { label: 'Recarga', values: { original: 'No tocar', configured: 'Valores del perfil', slow: '×1.25', normal: 'Igual que configured', fast: '×0.78', very_fast: '×0.58' } },
  headshot: { label: 'Cabeza', values: { original: 'No tocar la cabeza', off: 'Sin multiplicador de cabeza', normal: 'Headshot normal (política)', onetap: 'One-tap (política)' } },
};

export async function render({ root, params, setTitle, navigate, isCurrent }) {
  const catalog = await loadCatalog();
  const profileId = params.get('p') || store.draft?.id || store.status.active_profile;
  await openDraft(profileId);
  if (!isCurrent()) return null;
  setTitle(`Constructor · ${profileId}`, 'Crea y ajusta el perfil paso a paso, sin editar JSON');
  const state = { step: params.get('step') || 'general', group: null, refWeapon: 'WEAPON_PISTOL', review: null, reviewing: false, jsonMode: 'own' };
  const groups = [...new Set(catalog.weapons.filter((w) => w.in_meta && w.group && !w.internal).map((w) => w.group))].sort();
  state.group = params.get('g') || (groups.includes('GROUP_PISTOL') ? 'GROUP_PISTOL' : groups[0]);
  const host = h('div', { class: 'stack' });
  mount(root, host);

  function profile() { return store.draft.profile; }
  function meta() { const p = profile(); p.profile = p.profile || {}; return p.profile; }

  async function refValues(name) {
    try {
      const detail = await api.get(`/api/catalog/weapons/${encodeURIComponent(name)}`);
      const primary = detail.definitions[detail.definitions.length - 1];
      return { current: primary?.values || {}, original: primary?.original_values || primary?.values || {} };
    } catch { return { current: {}, original: {} }; }
  }

  function stepper() {
    return h('div', { class: 'stepper' }, STEPS.map((s, i) => h('button', {
      class: `step ${s.id === state.step ? 'active' : ''}`, onclick: () => go(s.id),
    }, h('b', {}, i + 1), s.label)));
  }

  function go(step) {
    state.step = step;
    history.replaceState(null, '', `#/constructor?p=${store.draft.id}&step=${step}`);
    draw();
  }

  function nav() {
    const index = STEPS.findIndex((s) => s.id === state.step);
    return h('div', { class: 'row row--between' },
      index > 0 ? h('button', { class: 'btn', onclick: () => go(STEPS[index - 1].id) }, '← ', STEPS[index - 1].label) : h('span'),
      index < STEPS.length - 1 ? h('button', { class: 'btn btn--primary', onclick: () => go(STEPS[index + 1].id) }, STEPS[index + 1].label, ' →') : null);
  }

  // ---- pasos ---------------------------------------------------------------
  function stepGeneral() {
    const m = meta();
    const p = profile();
    const editable = store.draft.editable;
    const text = (key, label, hint, area = false) => {
      const isList = Array.isArray(m[key]);
      const current = isList ? m[key].join('\n') : (m[key] ?? '');
      const input = area ? h('textarea', { class: 'textarea', disabled: !editable }) : h('input', { class: 'input', value: current, disabled: !editable });
      if (area) input.value = current;
      input.addEventListener('change', () => applyOps([{ op: 'set_meta', key, value: input.value.trim() }], { quiet: true }));
      return h('div', { class: 'field' }, h('label', {}, label), input, hint ? h('span', { class: 'hint' }, hint) : null);
    };
    const tags = h('input', { class: 'input', value: (m.tags || []).join(', '), placeholder: 'pvp, rp, experimental', disabled: !editable });
    tags.addEventListener('change', () => applyOps([{ op: 'set_meta', key: 'tags', value: tags.value }], { quiet: true }));
    const extendsSelect = h('select', { class: 'select' }, h('option', { value: '' }, 'Ninguno (perfil base)'));
    api.get('/api/profiles').then((data) => {
      for (const other of data.profiles) if (other.id !== store.draft.id) extendsSelect.append(h('option', { value: other.id, selected: other.id === m.extends }, other.id));
    });
    extendsSelect.disabled = !editable;
    extendsSelect.addEventListener('change', () => applyOps([{ op: 'set_meta', key: 'extends', value: extendsSelect.value || null }]));
    const resolved = store.draft.resolved || p;
    const engineDefaults = h('input', { type: 'checkbox', checked: resolved.engine_defaults !== false, disabled: !editable });
    engineDefaults.addEventListener('change', () => applyOps([{ op: 'set_section', key: 'engine_defaults', value: engineDefaults.checked }], { quiet: true }));
    const restore = h('input', { type: 'checkbox', checked: resolved.restore?.from_backup === true, disabled: !editable });
    restore.addEventListener('change', () => {
      const next = { ...(resolved.restore || {}) };
      if (restore.checked) next.from_backup = true; else delete next.from_backup;
      applyOps([{ op: 'set_section', key: 'restore', value: Object.keys(next).length ? next : null }], { quiet: true });
    });
    const presets = ['none', 'rp_balanced', 'rp_serious', 'pvp_controlled', 'hardcore', 'pvp_lethal'];
    const preset = h('select', { class: 'select', disabled: resolved.engine_defaults === false || !editable },
      presets.map((v) => h('option', { value: v, selected: (resolved.base_preset || (resolved.engine_defaults === false ? 'none' : 'pvp_lethal')) === v }, v)));
    preset.addEventListener('change', () => applyOps([{ op: 'set_section', key: 'base_preset', value: preset.value }], { quiet: true }));
    return h('div', { class: 'grid grid--2' },
      card({ title: 'Identidad', iconName: 'tag', body: h('div', { class: 'stack' },
        h('div', { class: 'field' }, h('label', {}, 'Identificador'), h('input', { class: 'input', value: store.draft.id, disabled: true }), h('span', { class: 'hint' }, 'Se cambia desde Perfiles → Renombrar.')),
        text('name', 'Nombre visible'),
        text('short_name', 'Nombre corto', 'Para tablas y la terminal.'),
        text('description', 'Descripción', '', true),
        text('objective', 'Objetivo de balanceo', 'Qué busca este balance. Los valores no son “realistas” salvo que estén verificados.'),
        text('audience', 'Público', 'Para qué servidor o modo está pensado.'),
        text('features', 'Características principales', 'Una por línea.', true),
        text('warnings', 'Advertencias', 'Una por línea.', true),
        h('div', { class: 'field' }, h('label', {}, 'Etiquetas'), tags)) }),
      card({ title: 'Base y comportamiento', iconName: 'layers', body: h('div', { class: 'stack' },
        h('div', { class: 'field' }, h('label', {}, 'Hereda de ', help({ title: 'Perfiles derivados', text: 'El perfil base se aplica primero y este perfil sobrescribe lo que declare. Objetos se combinan; listas se reemplazan completas.', doc: 'perfiles/herencia' })), extendsSelect),
        h('label', { class: 'check' }, engineDefaults, 'Heredar valores internos del motor (engine_defaults)', help({ title: 'engine_defaults', text: 'Activado: el perfil hereda el preset y los overrides de config.py (comportamiento de los perfiles antiguos). Desactivado (recomendado para perfiles nuevos): solo se aplica lo que configures aquí.', doc: 'perfiles/engine-defaults' })),
        p.engine_defaults !== false ? callout('warn', 'Con engine_defaults activo, las categorías sin valores en el perfil reciben el preset interno (por ejemplo pvp_lethal) cuando su módulo está en configured.') : null,
        h('div', { class: 'field' }, h('label', {}, 'Preset interno (base_preset)'), preset, h('span', { class: 'hint' }, '“none” = sin valores base.')),
        h('label', { class: 'check' }, restore, 'Partir siempre del .bak original (restore.from_backup)', help({ title: 'Restaurar desde .bak', text: 'Antes de aplicar, cada arma vuelve a su valor del .bak. Hace que el resultado sea repetible aunque uses multiplicadores sobre el valor del META.', doc: 'perfiles/repetible' }))) }));
  }

  function stepModules() {
    const p = profile();
    const values = store.registry.module_values;
    return card({ title: 'Módulos', iconName: 'layers', body: h('div', { class: 'stack' },
      callout('info', 'Cada módulo decide si su sección se toca. “original” = el motor descarta los valores de esa sección. “configured” = mandan los valores del perfil. Los demás son presets que recalculan después de tus valores.'),
      h('table', { class: 'table' }, h('tbody', {}, Object.keys(values).map((module) => {
        const select = h('select', { class: 'select', style: { width: '220px' } }, values[module].map((v) => h('option', { value: v, selected: effectiveModule(p, module) === v }, `${v} — ${MODULE_HELP[module]?.values[v] || ''}`)));
        select.disabled = !store.draft.editable;
        select.addEventListener('change', () => applyOps([{ op: 'set_module', module, value: select.value }]));
        const declared = p.modules && module in p.modules;
        return h('tr', {}, h('td', {}, h('strong', {}, MODULE_HELP[module]?.label || module), h('div', { class: 'mono small muted' }, `modules.${module}`)),
          h('td', {}, select), h('td', { class: 'small muted' }, declared ? 'declarado en el perfil' : `por defecto del motor (${store.registry.module_defaults[module]})`));
      })))) });
  }

  async function scopeEditor(scope, refName, title) {
    const body = h('div', {}, loading());
    const ref = await refValues(refName);
    const preview = store.preview?.data?.weapons?.[refName]?.proposed;
    const sections = ['damage', 'range', 'fire_rate', 'recoil', 'accuracy', 'ammo', 'projectile'];
    mount(body, h('div', { class: 'stack' }, sections.map((sectionId) => {
      const section = store.registry.sections.find((s) => s.id === sectionId);
      const specs = store.registry.params.filter((p) => p.section === sectionId && p.editable && !p.advanced && p.value_type !== 'flags');
      if (!specs.length) return null;
      return h('details', { class: 'card card--flush', open: sectionId === 'damage' },
        h('summary', { style: { padding: '12px 14px', cursor: 'pointer', fontWeight: 650 } }, section.label, h('span', { class: 'muted small', style: { marginLeft: '8px', fontWeight: 400 } }, section.summary)),
        specs.map((spec) => paramRow(spec, scope, { original: ref.original[spec.key], current: ref.current[spec.key], proposed: preview?.[spec.key] })));
    })));
    return h('div', { class: 'stack' }, h('div', { class: 'row small muted' }, title, ' · referencia: ', h('code', {}, refName)), body);
  }

  function headshotPolicyCard(scope) {
    const p = profile();
    const policy = getHeadshot(p, scope);
    const isGlobal = scope.type === 'defaults';
    const globalMode = effectiveModule(p, 'headshot');
    const mode = h('select', { class: 'select', style: { width: '230px' } },
      (isGlobal ? ['original', 'off', 'normal', 'onetap'] : ['inherit', 'off', 'normal', 'onetap']).map((v) => h('option', {
        value: v, selected: (isGlobal ? globalMode : policy.mode || 'inherit') === v,
      }, v === 'inherit' ? `Heredar (${globalMode})` : MODULE_HELP.headshot.values[v] || v)));
    mode.addEventListener('change', () => {
      if (isGlobal) {
        applyOps([{ op: 'set_headshot', scope: 'global', values: { mode: mode.value } }]);
      } else applyOps([{ op: 'set_headshot', scope: scopeOp(scope), values: { mode: mode.value } }]);
    });
    const field = (key, label, step = 0.1) => {
      const input = h('input', { class: 'input input--num', type: 'number', step, value: policy[key] ?? '', placeholder: 'heredar' });
      input.disabled = !store.draft.editable;
      input.addEventListener('change', () => applyOps([{ op: 'set_headshot', scope: scopeOp(scope), values: { [key]: input.value === '' ? null : Number(input.value) } }]));
      return h('div', { class: 'field' }, h('label', {}, label), input);
    };
    return card({ title: 'Política de cabeza', iconName: 'crosshair', body: h('div', { class: 'stack' },
      h('div', { class: 'row' }, mode, help({ title: 'Política de cabeza', text: 'Escribe los multiplicadores y distancias de cabeza de todas las armas del ámbito. One-tap además ajusta daño mínimo, caída y flags de casco según sus opciones.', doc: 'parametros/cabeza' })),
      h('div', { class: 'grid grid--3' }, field('multiplier', 'Multiplicador'), field('distance', 'Distancia máx. (m)', 1), field('target_effective_health', 'Vida objetivo one-tap', 1))) });
  }

  async function stepGlobal() {
    const container = h('div', { class: 'stack' }, loading());
    const select = h('select', { class: 'select', style: { width: '260px' } },
      catalog.weapons.filter((w) => w.in_meta && !w.internal).map((w) => h('option', { value: w.name, selected: w.name === state.refWeapon }, `${w.label} (${w.name})`)));
    select.addEventListener('change', () => { state.refWeapon = select.value; draw(); });
    const editor = await scopeEditor({ type: 'defaults', name: '*' }, state.refWeapon, 'Valores globales');
    mount(container,
      callout('info', 'Los valores globales se aplican a todas las armas que procese el perfil. Una categoría o un arma con su propio valor tiene prioridad.'),
      h('div', { class: 'row' }, h('span', { class: 'label' }, 'Arma de referencia para las columnas'), select),
      headshotPolicyCard({ type: 'defaults', name: '*' }), editor);
    return container;
  }

  async function stepGroups() {
    const container = h('div', { class: 'stack' }, loading());
    const counts = Object.fromEntries(groups.map((g) => [g, catalog.weapons.filter((w) => w.group === g && !w.internal).length]));
    const picker = h('div', { class: 'chips' }, groups.map((g) => h('button', {
      class: `chip ${g === state.group ? 'active' : ''}`, onclick: () => { state.group = g; draw(); },
    }, g.replace('GROUP_', ''), h('span', { class: 'count' }, counts[g]), profile().groups?.[g] ? badge('perfil', 'purple') : null)));
    const ref = catalog.weapons.find((w) => w.group === state.group && w.in_meta && !w.custom) || catalog.weapons.find((w) => w.group === state.group && w.in_meta);
    const editor = await scopeEditor({ type: 'group', name: state.group }, ref?.name || state.refWeapon, `Categoría ${state.group} (${counts[state.group]} armas)`);
    mount(container, card({ title: 'Categoría', iconName: 'layers', body: picker }),
      headshotPolicyCard({ type: 'group', name: state.group }), editor);
    return container;
  }

  function stepWeapons() {
    const p = profile();
    const configured = Object.keys(p.weapons || {}).concat(Object.keys(p.weapon_field_multipliers || {}), Object.keys(p.resources?.qbx_recoils || {}));
    const unique = [...new Set(configured)].sort();
    const picker = h('input', { class: 'input', list: 'all-weapons', placeholder: 'Escribe un arma para configurarla…', style: { maxWidth: '360px' } });
    const datalist = h('datalist', { id: 'all-weapons' }, catalog.weapons.filter((w) => w.in_meta && !w.internal).map((w) => h('option', { value: w.name }, w.label)));
    const open = () => { const name = picker.value.trim().toUpperCase(); if (name) navigate(`/editor?w=${name}&p=${store.draft.id}`); };
    picker.addEventListener('keydown', (e) => { if (e.key === 'Enter') open(); });
    return h('div', { class: 'stack' },
      card({ title: 'Configurar un arma', iconName: 'editor', body: h('div', { class: 'row' }, datalist, picker, h('button', { class: 'btn btn--primary', onclick: open }, 'Abrir en el editor'),
        h('span', { class: 'small muted' }, 'El editor guarda los cambios en este mismo borrador.')) }),
      card({ title: `${unique.length} armas con valores propios`, iconName: 'weapons', body: unique.length ? h('table', { class: 'table' },
        h('thead', {}, h('tr', {}, h('th', {}, 'Arma'), h('th', {}, 'Configurado'), h('th', {}))),
        h('tbody', {}, unique.map((name) => {
          const w = catalog.weapons.find((x) => x.name === name);
          const fields = Object.keys(p.weapons?.[name]?.fields || {}).concat(Object.keys(p.weapons?.[name] || {}).filter((k) => !['fields', 'headshot', 'weapon_flags', 'meta', '_comment', '_documentation'].includes(k)));
          return h('tr', {},
            h('td', {}, h('div', { class: 'weapon-cell' }, h('strong', {}, w?.label || name), h('small', {}, name)), !w?.in_meta ? badge('sin META', 'warn') : null),
            h('td', { class: 'small' }, h('div', { class: 'chips' },
              fields.map((f) => h('span', { class: 'tag' }, f)),
              p.weapons?.[name]?.headshot ? h('span', { class: 'tag' }, `cabeza: ${p.weapons[name].headshot.mode || '…'}`) : null,
              p.weapons?.[name]?.weapon_flags ? h('span', { class: 'tag' }, 'flags') : null,
              Object.entries(p.weapon_field_multipliers?.[name] || {}).map(([k, v]) => h('span', { class: 'tag' }, `${k} ×${v}`)),
              getQbxRecoil(p, name) !== undefined ? h('span', { class: 'tag' }, `qbx: ${getQbxRecoil(p, name) ?? 'quitar'}`) : null)),
            h('td', { class: 'right' }, h('a', { class: 'btn btn--sm', href: `#/editor?w=${name}&p=${store.draft.id}` }, 'Editar'), ' ', badge(String(countOverrides(p, name)), 'purple')));
        }))) : empty('Ninguna arma tiene valores propios en este perfil.') }));
  }

  function listEditor(key, title, hint) {
    const p = profile();
    const list = p[key] || [];
    const input = h('input', { class: 'input input--sm', list: 'all-weapons-ex', placeholder: 'WEAPON_…', style: { width: '260px' } });
    const add = () => { const v = input.value.trim().toUpperCase(); if (!v) return; applyOps([{ op: 'set_list', list: key, weapon: v, enabled: true }], { quiet: true }); };
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') add(); });
    return card({ title, iconName: 'shield', body: h('div', { class: 'stack stack--sm' },
      h('div', { class: 'small muted' }, hint),
      h('div', { class: 'chips' }, list.length ? list.map((w) => h('span', { class: 'tag' }, w, h('button', { onclick: () => applyOps([{ op: 'set_list', list: key, weapon: w, enabled: false }], { quiet: true }) }, '×'))) : h('span', { class: 'muted small' }, 'Vacía')),
      h('div', { class: 'row' }, input, h('button', { class: 'btn btn--sm', onclick: add }, icon('plus'), 'Agregar'))) });
  }

  function stepExceptions() {
    return h('div', { class: 'stack' },
      h('datalist', { id: 'all-weapons-ex' }, catalog.weapons.filter((w) => w.in_meta).map((w) => h('option', { value: w.name }))),
      callout('info', ['El motor ya trae listas por defecto: ignora ', h('code', {}, 'RPG, RAILGUN, MINIGUN, GRENADELAUNCHER'), ' y fuerza daño 0 en ', h('code', {}, 'SNOWBALL, BALL'), '. Usa las listas “permitir” para sacarlas de esas listas.']),
      h('div', { class: 'grid grid--2' },
        listEditor('ignore_weapons', 'No tocar nunca (ignore_weapons)', 'El motor omite estas armas aunque tengan valores.'),
        listEditor('harmless_weapons', 'Inofensivas (harmless_weapons)', 'Daño y multiplicadores forzados a 0 al final de todo.'),
        listEditor('allow_ignored_weapons', 'Permitir ignoradas por defecto', 'Quita armas de la lista interna de ignoradas.'),
        listEditor('allow_damage_weapons', 'Permitir daño a inofensivas por defecto', 'Quita armas de la lista interna de inofensivas.')));
  }

  function stepRules() {
    const p = profile();
    const inherited = p.fire_rate_damage_rules === undefined && Array.isArray(store.draft.resolved?.fire_rate_damage_rules);
    const rules = structuredClone(p.fire_rate_damage_rules ?? store.draft.resolved?.fire_rate_damage_rules ?? []);
    const saveRules = () => applyOps([{ op: 'set_section', key: 'fire_rate_damage_rules', value: rules.length ? rules : null }], { quiet: true });
    const groupOptions = groups;
    const ruleRow = (rule, index) => {
      const field = (key, type = 'number', width = '90px') => {
        const input = h('input', { class: 'input input--sm', type, step: 'any', value: rule[key] ?? '', style: { width } });
        input.addEventListener('change', () => {
          if (input.value === '') delete rule[key]; else rule[key] = type === 'number' ? Number(input.value) : input.value;
          saveRules();
        });
        return input;
      };
      const groupSelect = h('select', { class: 'select', style: { width: '170px', height: '28px' } }, h('option', { value: '' }, 'Todas'),
        groupOptions.map((g) => h('option', { value: g, selected: (rule.groups || [])[0] === g }, g)));
      groupSelect.addEventListener('change', () => { rule.groups = groupSelect.value ? [groupSelect.value] : []; saveRules(); });
      return h('tr', {}, h('td', {}, field('name', 'text', '160px')), h('td', {}, groupSelect), h('td', {}, field('min_time_between_shots')),
        h('td', {}, field('max_time_between_shots')), h('td', {}, field('damage')),
        h('td', {}, h('button', { class: 'btn btn--sm btn--ghost', onclick: () => { rules.splice(index, 1); saveRules(); } }, icon('trash'))));
    };
    const multipliers = Object.entries(p.weapon_field_multipliers || {}).flatMap(([weapon, map]) => Object.entries(map).map(([key, value]) => ({ weapon, key, value })));
    const mWeapon = h('input', { class: 'input input--sm', list: 'all-weapons-ex', placeholder: 'WEAPON_…', style: { width: '200px' } });
    const mField = h('select', { class: 'select', style: { width: '200px', height: '28px' } }, store.registry.params.filter((s) => s.editable && s.value_type !== 'flags').map((s) => h('option', { value: s.key }, s.key)));
    const mValue = h('input', { class: 'input input--sm input--num', type: 'number', step: 'any', placeholder: '×' });
    const jsonSections = [
      ['fire_rate_classifier', 'Clasificador de cadencia', 'Clasifica armas rápidas/automáticas y controla one-tap y recoil por cadencia.'],
      ['family_rules', 'Reglas por familia de nombre', 'Lista de reglas {name, contains, groups, fields, field_multipliers}.'],
      ['weapon_classification', 'Clasificación oficial / custom', 'Catálogo oficial y multiplicadores para armas personalizadas.'],
      ['baseline_repair', 'Reparación de valores rotos', 'Repara daño/red/alcance en cero o ausentes antes de aplicar.'],
      ['meta', 'Tags XML exactos (global)', 'Reemplaza hojas XML que no están en el catálogo de campos. Úsalo con cuidado.'],
    ];
    return h('div', { class: 'stack' },
      card({ title: 'Daño por cadencia (fire_rate_damage_rules)', iconName: 'zap', actions: h('button', { class: 'btn btn--sm', onclick: () => { rules.push({ name: `regla_${rules.length + 1}`, groups: [], max_time_between_shots: 0.1, damage: 10 }); saveRules(); } }, icon('plus'), 'Regla'),
        body: h('div', { class: 'stack stack--sm' },
          h('div', { class: 'small muted' }, 'Se evalúan en orden; la primera que coincide con el TimeBetweenShots efectivo del arma fija su daño. Un daño explícito por arma tiene prioridad.'),
          inherited ? callout('info', 'Estas reglas se heredan del perfil base. Al editarlas, este perfil guarda su propia lista completa (las listas no se combinan).') : null,
          rules.length ? h('table', { class: 'table table--compact' },
            h('thead', {}, h('tr', {}, h('th', {}, 'Nombre'), h('th', {}, 'Grupo'), h('th', {}, 'TBS mín.'), h('th', {}, 'TBS máx.'), h('th', {}, 'Daño'), h('th', {}))),
            h('tbody', {}, rules.map(ruleRow))) : empty('Sin reglas.')) }),
      card({ title: 'Multiplicadores exactos por arma', iconName: 'weapons', body: h('div', { class: 'stack stack--sm' },
        h('div', { class: 'small muted' }, 'Multiplican el valor ya resuelto (perfil o META) de un campo concreto. Sin “restaurar desde .bak” y sin valor base en el perfil, se acumulan al aplicar varias veces.'),
        multipliers.length ? h('table', { class: 'table table--compact' }, h('tbody', {}, multipliers.map((m) => h('tr', {},
          h('td', { class: 'mono small' }, m.weapon), h('td', { class: 'mono small' }, m.key), h('td', { class: 'num' }, `×${num(m.value)}`),
          h('td', { class: 'right' }, h('button', { class: 'btn btn--sm btn--ghost', onclick: () => applyOps([{ op: 'set_multiplier', weapon: m.weapon, key: m.key, value: null }], { quiet: true }) }, icon('trash'))))))) : empty('Sin multiplicadores.'),
        h('div', { class: 'row' }, mWeapon, mField, mValue, h('button', { class: 'btn btn--sm', onclick: () => {
          const w = mWeapon.value.trim().toUpperCase(); const v = Number(mValue.value);
          if (!w || !(v > 0)) { toast('Indica arma y multiplicador > 0.', { type: 'warn' }); return; }
          applyOps([{ op: 'set_multiplier', weapon: w, key: mField.value, value: v }], { quiet: true });
        } }, icon('plus'), 'Agregar'))) }),
      h('datalist', { id: 'all-weapons-ex' }, catalog.weapons.filter((w) => w.in_meta).map((w) => h('option', { value: w.name }))),
      ...jsonSections.map(([key, title, hint]) => jsonSectionEditor(key, title, hint)));
  }

  function jsonSectionEditor(key, title, hint) {
    const p = profile();
    const area = h('textarea', { class: 'textarea textarea--code', style: { minHeight: '160px' } });
    area.value = p[key] === undefined ? '' : JSON.stringify(p[key], null, 2);
    const inheritedValue = store.draft.resolved?.[key];
    if (p[key] === undefined && inheritedValue !== undefined) area.placeholder = `Heredado del perfil base (escribe aquí para sustituirlo):\n${JSON.stringify(inheritedValue, null, 2)}`;
    area.disabled = !store.draft.editable;
    const applyBtn = h('button', { class: 'btn btn--sm', onclick: async () => {
      if (!area.value.trim()) { if (await applyOps([{ op: 'set_section', key, value: null }], { quiet: true })) toast(`${key} eliminado del perfil.`, { type: 'info' }); return; }
      let parsed;
      try { parsed = JSON.parse(area.value); } catch (error) { toast(`JSON inválido: ${error.message}`, { type: 'err' }); return; }
      const candidate = { ...p, [key]: parsed };
      setLoading(applyBtn, true);
      try {
        const result = await api.post('/api/profiles/validate', { profile: candidate });
        if (!result.valid) { toast('El motor rechaza esta sección.', { type: 'err', detail: result.issues.filter((i) => i.severity === 'error').map((i) => i.message).join(' · ') }); return; }
        if (await applyOps([{ op: 'set_section', key, value: parsed }], { quiet: true })) toast(`${key} actualizado.`);
      } catch (error) { toastError(error); } finally { setLoading(applyBtn, false); }
    } }, 'Validar y aplicar');
    return h('details', { class: 'card' }, h('summary', { style: { cursor: 'pointer', fontWeight: 650 } }, title, ' ', h('code', {}, key), p[key] !== undefined ? badge('en el perfil', 'purple') : null),
      h('div', { class: 'stack stack--sm', style: { marginTop: '10px' } }, h('div', { class: 'small muted' }, hint, ' ', h('a', { href: `/docs/#perfiles/${key}`, target: '_blank' }, 'Referencia →')), area, h('div', {}, applyBtn)));
  }

  function stepResources() {
    const p = profile();
    const map = p.resources?.qbx_recoils || {};
    const weapon = h('input', { class: 'input input--sm', list: 'all-weapons-ex', placeholder: 'WEAPON_…', style: { width: '220px' } });
    const value = h('input', { class: 'input input--sm input--num', type: 'number', step: 0.05, min: 0, max: 10, placeholder: '0.3' });
    const qbx = store.catalog.summary.qbx_recoils;
    return h('div', { class: 'stack' },
      h('datalist', { id: 'all-weapons-ex' }, catalog.weapons.filter((w) => w.in_meta).map((w) => h('option', { value: w.name }))),
      callout(qbx ? 'info' : 'warn', qbx
        ? ['Recoil vertical de cámara por script en ', h('code', {}, qbx.path), `. Hoy tiene ${qbx.active} armas activas. El Generador edita solo las líneas de las armas indicadas y conserva el resto.`]
        : 'No se encontró qbx_recoils en este servidor: esta sección no tendrá efecto.'),
      card({ title: 'qbx_recoils', iconName: 'activity', body: h('div', { class: 'stack stack--sm' },
        Object.keys(map).length ? h('table', { class: 'table table--compact' },
          h('thead', {}, h('tr', {}, h('th', {}, 'Arma'), h('th', { class: 'num' }, 'Actual'), h('th', { class: 'num' }, 'Nuevo'), h('th', {}))),
          h('tbody', {}, Object.entries(map).map(([w, v]) => h('tr', {}, h('td', { class: 'mono small' }, w),
            h('td', { class: 'num' }, catalog.weapons.find((x) => x.name === w)?.qbx_recoil ?? '—'),
            h('td', { class: 'num' }, v === false ? 'desactivar' : v),
            h('td', { class: 'right' }, h('button', { class: 'btn btn--sm btn--ghost', onclick: () => applyOps([{ op: 'set_qbx_recoil', weapon: w, value: 'unset' }], { quiet: true }) }, icon('trash'))))))) : empty('Sin cambios en qbx_recoils.'),
        h('div', { class: 'row' }, weapon, value,
          h('button', { class: 'btn btn--sm', onclick: () => { const w = weapon.value.trim().toUpperCase(); if (!w || value.value === '') return; applyOps([{ op: 'set_qbx_recoil', weapon: w, value: Number(value.value) }], { quiet: true }); } }, icon('plus'), 'Fijar'),
          h('button', { class: 'btn btn--sm btn--ghost', onclick: () => { const w = weapon.value.trim().toUpperCase(); if (!w) return; applyOps([{ op: 'set_qbx_recoil', weapon: w, value: false }], { quiet: true }); } }, 'Desactivar entrada'))) }));
  }

  async function stepReview() {
    const container = h('div', { class: 'stack' }, loading('Validando y ejecutando el motor…'));
    try {
      const [validation, preview] = await Promise.all([
        api.post('/api/profiles/validate', { profile: profile() }),
        draftPreview().catch((error) => ({ error })),
      ]);
      const saved = JSON.parse(store.draft.savedJson);
      const diff = flatDiff(saved, profile());
      const jsonHost = h('div', {});
      const drawJson = async () => {
        if (state.jsonMode === 'resolved' && profile().profile?.extends) {
          mount(jsonHost, loading());
          try {
            const data = await api.get(`/api/profiles/${store.draft.id}/export?resolved=1`);
            mount(jsonHost, callout('info', 'Versión guardada con la herencia aplicada (los cambios sin guardar no se incluyen).'), jsonView(data.profile));
          } catch (error) { mount(jsonHost, callout('err', error.message)); }
        } else mount(jsonHost, jsonView(profile()));
      };
      const saveBtn = h('button', { class: 'btn btn--primary', disabled: !store.draft.dirty || !validation.valid, onclick: async () => {
        setLoading(saveBtn, true);
        try { const r = await saveDraft(); toast(r.changed === false ? 'Sin cambios.' : 'Perfil guardado.', { detail: 'Versión anterior en el historial.' }); } catch (error) { toastError(error, 'No se guardó: '); }
        setLoading(saveBtn, false);
      } }, icon('save'), 'Guardar perfil');
      mount(container,
        h('div', { class: 'grid grid--3' },
          card({ title: 'Validación', iconName: 'shield', body: validation.valid
            ? callout('ok', `Válido para el motor. ${validation.issues.length ? `${validation.issues.length} aviso(s).` : ''}`)
            : callout('err', 'El perfil tiene errores: corrígelos antes de guardar.') }),
          card({ title: 'Efecto en el pack', iconName: 'eye', body: preview.error ? callout('err', preview.error.message)
            : h('div', { class: 'stack stack--sm' },
              h('div', {}, h('strong', { style: { fontSize: '20px' } }, preview.summary.weapons_changed), ' armas · ', h('strong', {}, preview.summary.files_changed), ' archivos cambiarían'),
              h('div', { class: 'small muted' }, `One-tap: ${preview.summary.onetap_passed}/${preview.summary.onetap_total} · repetible: ${preview.idempotency?.idempotent === false ? 'NO' : 'sí'} · ${preview.duration_ms} ms`)) }),
          card({ title: 'Cambios sin guardar', iconName: 'history', body: h('div', { class: 'stack stack--sm' },
            h('div', {}, h('strong', { style: { fontSize: '20px' } }, diff.length), ' rutas del JSON'),
            h('div', { class: 'row' }, saveBtn, h('a', { class: 'btn', href: `#/generador?p=${store.draft.id}` }, icon('generator'), 'Generador'))) })),
        card({ title: 'Problemas y avisos', iconName: 'alert', body: issueList([...validation.issues, ...((preview && !preview.error && preview.issues) || [])], { emptyText: 'Sin avisos: todo lo declarado tiene efecto.' }) }),
        diff.length ? card({ title: 'Diferencias con la versión guardada', iconName: 'compare', body: h('table', { class: 'table table--compact' },
          h('thead', {}, h('tr', {}, h('th', {}, 'Ruta'), h('th', {}, 'Guardado'), h('th', {}, 'Borrador'))),
          h('tbody', {}, diff.slice(0, 300).map((d) => h('tr', {}, h('td', { class: 'mono small' }, d.path), h('td', { class: 'mono small muted' }, short(d.a)), h('td', { class: 'mono small', style: { color: 'var(--purple-2)' } }, short(d.b)))))) }) : null,
        card({ title: 'JSON generado', iconName: 'file', actions: segmented([{ value: 'own', label: 'Este perfil' }, ...(meta().extends ? [{ value: 'resolved', label: 'Con herencia' }] : [])], state.jsonMode, (v) => { state.jsonMode = v; drawJson(); }), body: jsonHost }));
      drawJson();
    } catch (error) {
      mount(container, callout('err', error.message));
    }
    return container;
  }

  async function draw() {
    const header = h('div', { class: 'row row--between' },
      h('div', { class: 'row' }, h('h2', {}, meta().name || store.draft.id), store.draft.legacy ? badge('legacy (se guardará como v8)', 'warn') : badge('v8', 'ok'),
        meta().extends ? badge(`hereda de ${meta().extends}`, 'blue') : null),
      h('div', { class: 'row' }, h('a', { class: 'btn btn--sm btn--ghost', href: '#/perfiles' }, 'Todos los perfiles')));
    const bodyHost = h('div', {}, loading());
    mount(host, protectedNotice(navigate, `/constructor?step=${state.step}`), header, stepper(), bodyHost);
    let body;
    switch (state.step) {
      case 'general': body = stepGeneral(); break;
      case 'modules': body = stepModules(); break;
      case 'global': body = await stepGlobal(); break;
      case 'groups': body = await stepGroups(); break;
      case 'weapons': body = stepWeapons(); break;
      case 'exceptions': body = stepExceptions(); break;
      case 'rules': body = stepRules(); break;
      case 'resources': body = stepResources(); break;
      default: body = await stepReview();
    }
    if (!isCurrent()) return;
    mount(bodyHost, h('div', { class: 'stack' }, body, nav()));
  }

  const unsubscribe = subscribe((event) => {
    if (event === 'draft' && isCurrent() && state.step !== 'review') redrawSoon();
    if (event === 'saved' && isCurrent()) draw();
  });
  let timer = null;
  function redrawSoon() { clearTimeout(timer); timer = setTimeout(() => { const y = window.scrollY; draw().then(() => window.scrollTo(0, y)); }, 60); }
  await draw();
  return () => { unsubscribe(); clearTimeout(timer); void confirmDialog; };
}

function flatDiff(a, b, prefix = '', out = []) {
  const isObj = (v) => v && typeof v === 'object' && !Array.isArray(v);
  if (isObj(a) && isObj(b)) {
    for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) {
      if (key === 'profile') continue;
      flatDiff(a[key], b[key], prefix ? `${prefix}.${key}` : key, out);
    }
    return out;
  }
  if (JSON.stringify(a) !== JSON.stringify(b)) out.push({ path: prefix, a, b });
  return out;
}

function short(value) {
  if (value === undefined) return '—';
  const text = typeof value === 'string' ? value : JSON.stringify(value);
  return text.length > 90 ? `${text.slice(0, 90)}…` : text;
}
