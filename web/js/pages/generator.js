import { api } from '../core/api.js';
import { h, icon, mount, setLoading } from '../core/dom.js';
import { date, num } from '../core/format.js';
import { loadCatalog, loadStatus, store } from '../core/store.js';
import {
  badge, callout, card, dataTable, diffView, empty, help, issueList, kpi, loading, modal, tabs, toast, toastError, typedConfirm,
} from '../components/ui.js';

export async function render({ root, params, setTitle, isCurrent }) {
  setTitle('Generador', 'Vista previa, validación y aplicación controlada al servidor');
  const profiles = (await api.get('/api/profiles')).profiles;
  const state = { profile: params.get('p') || store.status.active_profile, plan: null, tab: 'weapons', useDraft: false };
  const planHost = h('div', { class: 'stack' });
  const txHost = h('div', {}, loading());
  const select = h('select', { class: 'select', style: { width: '260px' } }, profiles.map((p) => h('option', { value: p.id, selected: p.id === state.profile }, p.id)));
  select.addEventListener('change', () => { state.profile = select.value; });
  const draftCheck = h('input', { type: 'checkbox' });
  draftCheck.addEventListener('change', () => { state.useDraft = draftCheck.checked; });
  const planBtn = h('button', { class: 'btn btn--primary', onclick: () => makePlan() }, icon('eye'), 'Generar vista previa');

  async function makePlan() {
    setLoading(planBtn, true);
    mount(planHost, loading('Ejecutando el motor sobre una copia en memoria… (no se escribe nada)'));
    try {
      const body = { profile_id: state.profile };
      if (state.useDraft && store.draft?.id === state.profile) body.profile = store.draft.profile;
      state.plan = await api.post('/api/generator/plan', body);
      if (isCurrent()) drawPlan();
    } catch (error) {
      mount(planHost, h('div', { class: 'stack' }, callout('err', [h('strong', {}, 'No se pudo generar el plan. '), error.message]),
        Array.isArray(error.details) ? issueList(error.details) : null));
    }
    setLoading(planBtn, false);
  }

  function drawPlan() {
    const plan = state.plan;
    const s = plan.summary;
    const changed = Object.values(plan.weapons).filter((w) => Object.keys(w.changes || {}).length);
    const blocking = plan.blocking || [];
    const applyBtn = h('button', { class: 'btn btn--blue', disabled: !s.files_to_write || blocking.length > 0, onclick: () => apply() }, icon('generator'), `Aplicar ${s.files_to_write} archivo(s)`);
    const weaponRows = changed.map((w) => ({ ...w, count: Object.keys(w.changes).length }));
    const tabBody = h('div', {});
    const drawTab = () => {
      if (state.tab === 'weapons') {
        mount(tabBody, dataTable({
          rows: weaponRows, pageSize: 40, initialSort: { key: 'weapon' },
          columns: [
            { key: 'weapon', label: 'Arma', render: (w) => h('div', { class: 'weapon-cell' }, h('strong', {}, w.weapon), h('small', {}, w.group)) },
            { key: 'count', label: 'Campos', num: true },
            { key: 'changes', label: 'Cambios', sortable: false, render: (w) => h('div', { class: 'small mono' }, Object.entries(w.changes).slice(0, 6).map(([k, v]) => h('div', {},
              `${k}: `, h('span', { class: 'muted' }, fmt(v.current)), ' → ', h('span', { style: { color: 'var(--purple-2)' } }, fmt(v.proposed)))),
              Object.keys(w.changes).length > 6 ? h('div', { class: 'muted' }, `… y ${Object.keys(w.changes).length - 6} más`) : null) },
            { key: 'onetap', label: 'One-tap', sortable: false, render: (w) => (w.onetap ? badge(w.onetap.ready ? 'OK' : 'falla', w.onetap.ready ? 'ok' : 'err') : '—') },
          ],
          emptyText: 'Ninguna arma cambia.',
        }));
      } else if (state.tab === 'files') {
        mount(tabBody, plan.files_detail.length ? h('table', { class: 'table table--compact' },
          h('thead', {}, h('tr', {}, h('th', {}, 'Archivo'), h('th', {}, 'Tipo'), h('th', { class: 'num' }, 'Líneas'), h('th', {}))),
          h('tbody', {}, plan.files_detail.map((f) => {
            const info = plan.files.find((x) => x.path === f.path);
            return h('tr', {}, h('td', { class: 'mono small' }, shortPath(f.path)), h('td', {}, badge(f.kind === 'meta' ? 'weapons.meta' : 'qbx_recoils', f.kind === 'meta' ? 'purple' : 'info')),
              h('td', { class: 'num' }, info ? h('span', {}, h('span', { class: 'delta-up' }, `+${info.added}`), ' ', h('span', { class: 'delta-down' }, `−${info.removed}`)) : '—'),
              h('td', { class: 'right' }, h('button', { class: 'btn btn--sm', onclick: () => showDiff(plan.plan_hash, f.path) }, 'Ver diff')));
          }))) : empty('No hay archivos que escribir.'));
      } else if (state.tab === 'issues') {
        mount(tabBody, h('div', { class: 'stack' },
          issueList([...(plan.structural_issues || []), ...plan.issues], { emptyText: 'Todo lo declarado tiene efecto.' }),
          plan.engine_warnings?.length ? card({ title: 'Avisos del motor', body: h('pre', { class: 'code' }, plan.engine_warnings.join('\n')) }) : null));
      } else {
        mount(tabBody, plan.qbx_recoils?.length ? h('pre', { class: 'code' }, plan.qbx_recoils.join('\n')) : empty('El perfil no cambia qbx_recoils.'));
      }
    };
    mount(planHost,
      blocking.length ? callout('err', [h('strong', {}, 'Bloqueos: '), 'estos archivos no se pueden escribir con seguridad.', issueList(blocking.map((b) => ({ severity: 'error', message: `${shortPath(b.path)}: ${b.message}` })))]) : null,
      s.files_to_write === 0 && !blocking.length ? callout('ok', [h('strong', {}, 'Nada que aplicar. '), 'El servidor ya coincide con este perfil.']) : null,
      h('div', { class: 'grid grid--4' },
        kpi(s.files_to_write, 'Archivos a escribir', { variant: 'purple' }),
        kpi(changed.length, 'Armas que cambian', { variant: 'blue', hint: `${s.weapons_skipped} omitidas por el perfil` }),
        kpi(`${s.onetap_passed}/${s.onetap_total}`, 'Auditoría one-tap', { variant: s.onetap_failed ? 'err' : 'ok' }),
        kpi(plan.idempotency?.idempotent === false ? 'No' : 'Sí', 'Resultado repetible', { variant: plan.idempotency?.idempotent === false ? 'warn' : 'ok', hint: 'Aplicarlo dos veces da lo mismo' })),
      card({ title: 'Plan', iconName: 'generator', actions: h('div', { class: 'row' },
        h('span', { class: 'mono small muted', title: 'Identificador del plan: si un archivo cambia antes de aplicar, se rechaza.' }, plan.plan_hash.slice(0, 12)), applyBtn),
      body: h('div', {},
        tabs([
          { id: 'weapons', label: 'Armas', count: changed.length },
          { id: 'files', label: 'Archivos', count: plan.files_detail.length },
          { id: 'issues', label: 'Avisos', count: (plan.structural_issues || []).length + plan.issues.length, countVariant: plan.issues.some((i) => i.severity === 'warning') ? 'warn' : '' },
          { id: 'qbx', label: 'qbx_recoils', count: plan.qbx_recoils?.length || 0 },
        ], state.tab, (id) => { state.tab = id; drawPlan(); }),
        tabBody) }));
    drawTab();
  }

  async function apply() {
    const s = state.plan.summary;
    const word = await typedConfirm({
      title: 'Aplicar al servidor',
      confirmLabel: 'Aplicar ahora',
      message: h('div', { class: 'stack stack--sm' },
        h('p', {}, `Se escribirán ${s.files_to_write} archivo(s) del servidor de pruebas.`),
        h('ul', { class: 'small', style: { margin: 0, paddingLeft: '18px' } },
          h('li', {}, 'Antes de escribir se copia cada archivo a data/backups/ (se puede revertir desde aquí).'),
          h('li', {}, 'Si un archivo cambió desde la vista previa, no se aplica nada.'),
          h('li', {}, 'Para que el juego cargue los cambios hay que reiniciar los recursos de armas (y qbx_smallresources si cambia qbx_recoils).'))),
    });
    if (!word) return;
    try {
      const result = await api.post('/api/generator/apply', { plan_hash: state.plan.plan_hash, confirm: word });
      if (result.applied) {
        toast(`Aplicado: ${result.files} archivo(s), ${result.weapons} arma(s).`, { detail: `Transacción ${result.transaction}`, timeout: 8000 });
      } else toast(result.message, { type: 'info' });
      state.plan = null;
      mount(planHost, callout('ok', ['Cambios aplicados. Reinicia los recursos afectados en txAdmin o con ', h('code', {}, 'ensure'), '. Puedes revertir desde el historial de abajo.']));
      await Promise.all([loadCatalog(true), loadStatus()]);
      loadTransactions();
    } catch (error) {
      toastError(error, 'No se aplicó: ');
    }
  }

  async function loadTransactions() {
    try {
      const { transactions } = await api.get('/api/generator/transactions');
      if (!isCurrent()) return;
      mount(txHost, transactions.length ? h('table', { class: 'table table--compact' },
        h('thead', {}, h('tr', {}, h('th', {}, 'Fecha'), h('th', {}, 'Perfil'), h('th', { class: 'num' }, 'Archivos'), h('th', {}, 'Estado'), h('th', {}))),
        h('tbody', {}, transactions.map((t) => h('tr', {},
          h('td', {}, date(t.created_at)), h('td', {}, t.profile || '—'), h('td', { class: 'num' }, t.files),
          h('td', {}, badge({ applied: 'aplicado', rolled_back: 'revertido', failed_rolled_back: 'falló (revertido)' }[t.status] || t.status, t.status === 'applied' ? 'ok' : t.status === 'rolled_back' ? 'outline' : 'err')),
          h('td', { class: 'right' }, t.status === 'applied' ? h('button', { class: 'btn btn--sm btn--danger', onclick: () => rollbackTx(t) }, icon('undo'), 'Revertir') : null))))) : empty('Todavía no se aplicó nada desde el panel.', 'history'));
    } catch (error) { mount(txHost, callout('err', error.message)); }
  }

  async function rollbackTx(t) {
    const word = await typedConfirm({ title: `Revertir ${t.id}`, confirmLabel: 'Revertir',
      message: h('p', {}, `Se restauran los ${t.files} archivo(s) tal como estaban antes de aplicar. Si alguno cambió después, no se revierte nada.`) });
    if (!word) return;
    try {
      await api.post('/api/generator/rollback', { id: t.id, confirm: word });
      toast('Transacción revertida.', { detail: 'Reinicia los recursos afectados.' });
      await loadCatalog(true);
      loadTransactions();
    } catch (error) { toastError(error, 'No se revirtió: '); }
  }

  const guardCard = guardSection(state);
  mount(root,
    callout('info', ['El Generador nunca escribe sin tu confirmación. Flujo: ', h('strong', {}, 'vista previa → revisar → escribir APLICAR'), '. Solo toca archivos dentro de los packs configurados (y qbx_recoils si el perfil lo pide).']),
    card({ title: 'Perfil a generar', iconName: 'profiles', body: h('div', { class: 'row' }, select,
      h('label', { class: 'check' }, draftCheck, 'Usar los cambios sin guardar del borrador'),
      help({ title: 'Borrador', text: 'Si estás editando este perfil y no lo guardaste, puedes generar con el borrador. Lo recomendable es guardar primero para que el historial refleje lo aplicado.' }),
      planBtn) }),
    planHost,
    card({ title: 'Historial de aplicaciones', iconName: 'history', body: txHost }),
    guardCard);
  loadTransactions();
  if (params.get('p')) makePlan();
}

function guardSection(state) {
  const dest = h('input', { class: 'input', value: store.status.workspace.guard_destination || `${store.status.workspace.server_root}/resources/[scripting]/[OS]/os_weapon_damage_guard`, spellcheck: 'false' });
  const source = h('select', { class: 'select', style: { width: '220px' } }, h('option', { value: 'current' }, 'Daño actual del META'), h('option', { value: 'proposed' }, 'Daño propuesto por el perfil'));
  const btn = h('button', { class: 'btn', onclick: async () => {
    const word = await typedConfirm({ title: 'Generar os_weapon_damage_guard', confirmLabel: 'Generar',
      message: h('div', { class: 'stack stack--sm' }, h('p', {}, 'Crea un recurso Lua que fija el daño esperado con SetWeaponDamageModifier. Solo hace falta si otro recurso altera el daño en ejecución (ver Diagnóstico).'),
        h('p', { class: 'small muted' }, 'No reemplaza carpetas que no haya generado esta herramienta. Si ya existe una generada, se respalda antes.')) });
    if (!word) return;
    setLoading(btn, true);
    try {
      const result = await api.post('/api/generator/guard', { destination: dest.value.trim(), source: source.value, profile_id: state.profile, confirm: word });
      toast(`Guard generado con ${result.weapons} armas.`, { detail: `${result.destination}${result.backup ? ` · respaldo: ${result.backup}` : ''}. Agrega “ensure” en server.cfg.`, timeout: 9000 });
    } catch (error) { toastError(error); }
    setLoading(btn, false);
  } }, 'Generar guard');
  return h('details', { class: 'card' }, h('summary', { style: { cursor: 'pointer', fontWeight: 650 } }, 'Avanzado: guard de daño en ejecución (opcional)'),
    h('div', { class: 'stack', style: { marginTop: '12px' } },
      callout('warn', 'Mecanismo “Native”: un recurso cliente reaplica SetWeaponDamageModifier cada 250 ms. Úsalo solo si el Diagnóstico muestra scripts que cambian el daño. No es necesario para que el META funcione.'),
      h('div', { class: 'field' }, h('label', {}, 'Carpeta destino (dentro de resources/)'), dest),
      h('div', { class: 'row' }, source, btn)));
}

async function showDiff(planHash, path) {
  const body = h('div', {}, loading());
  modal({ title: shortPath(path), body, wide: true });
  try {
    const data = await api.get(`/api/generator/plan/${planHash}/diff?path=${encodeURIComponent(path)}`);
    mount(body, diffView(data.diff || '(sin diferencias)'));
  } catch (error) { mount(body, callout('err', error.message)); }
}

function shortPath(path) {
  const root = store.status?.workspace?.server_root;
  return root && path.startsWith(root) ? path.slice(root.length + 1) : path;
}

function fmt(value) {
  if (Array.isArray(value)) return value.length > 4 ? `${value.slice(0, 4).join(' ')} …` : value.join(' ');
  return num(value, 4);
}
