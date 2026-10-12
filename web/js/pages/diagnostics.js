import { api } from '../core/api.js';
import { h, icon, mount, setLoading } from '../core/dom.js';
import { date } from '../core/format.js';
import { badge, callout, card, issueList, kpi, loading, segmented, toastError } from '../components/ui.js';

export async function render({ root, setTitle, isCurrent }) {
  setTitle('Diagnóstico', 'Problemas de rutas, inventario, packs, perfiles y scripts en ejecución');
  const state = { severity: 'all', data: null };
  const host = h('div', { class: 'stack' }, loading('Analizando…'));
  const runtimeBtn = h('button', { class: 'btn', onclick: () => load(true, true) }, icon('refresh'), 'Auditar scripts (runtime)');
  const refreshBtn = h('button', { class: 'btn btn--ghost', onclick: () => load(false, !!state.data?.sections.find((s) => s.id === 'runtime')) }, icon('refresh'), 'Actualizar');
  const filter = segmented([
    { value: 'all', label: 'Todo' }, { value: 'error', label: 'Errores' }, { value: 'warning', label: 'Avisos' }, { value: 'info', label: 'Info' },
  ], state.severity, (v) => { state.severity = v; draw(); });

  async function load(refreshRuntime = false, includeRuntime = false) {
    setLoading(runtimeBtn, includeRuntime);
    mount(host, loading(includeRuntime ? 'Recorriendo los scripts de resources/ (≈ 8 s la primera vez)…' : 'Analizando…'));
    try {
      state.data = await api.get(`/api/diagnostics?runtime=${includeRuntime ? 1 : 0}&refresh_runtime=${refreshRuntime ? 1 : 0}`);
      if (isCurrent()) draw();
    } catch (error) {
      mount(host, callout('err', error.message));
      toastError(error);
    }
    setLoading(runtimeBtn, false);
  }

  function draw() {
    const data = state.data;
    const keep = (issue) => state.severity === 'all' || issue.severity === state.severity;
    const runtime = data.sections.find((s) => s.id === 'runtime');
    mount(host,
      h('div', { class: 'grid grid--4' },
        kpi(data.totals.error, 'Errores', { variant: data.totals.error ? 'err' : 'ok' }),
        kpi(data.totals.warning, 'Avisos', { variant: data.totals.warning ? 'warn' : 'ok' }),
        kpi(data.totals.info, 'Informativos', { variant: 'blue' }),
        kpi(runtime ? `${runtime.runtime.files_scanned}` : '—', 'Scripts auditados', { hint: runtime ? `${date(runtime.runtime.scanned_at)} · ${runtime.runtime.duration_ms} ms` : 'Pulsa “Auditar scripts” para revisar Lua/JS/C#' })),
      !runtime ? callout('info', ['La auditoría runtime busca scripts que apagan critical hits, cancelan el daño o restauran vida/armadura. ',
        'Es estática: los recursos cifrados (escrow) no se pueden leer.']) : null,
      data.sections.map((section) => {
        const issues = section.issues.filter(keep);
        const counts = { error: 0, warning: 0, info: 0 };
        for (const issue of section.issues) if (issue.severity in counts) counts[issue.severity] += 1;
        return card({
          title: section.title, iconName: { workspace: 'settings', catalog: 'weapons', profiles: 'profiles', active: 'star', runtime: 'activity' }[section.id] || 'info',
          actions: h('div', { class: 'row', style: { gap: '4px' } },
            counts.error ? badge(`${counts.error} errores`, 'err') : null, counts.warning ? badge(`${counts.warning} avisos`, 'warn') : null,
            counts.info ? badge(`${counts.info} info`, 'info') : null, !section.issues.length ? badge('sin problemas', 'ok') : null),
          body: section.id === 'active' && section.issues.some((i) => i.severity === 'ok')
            ? h('div', { class: 'stack stack--sm' }, callout('ok', section.issues.find((i) => i.severity === 'ok').message), issueList(issues.filter((i) => i.severity !== 'ok'), { emptyText: 'Sin avisos para este filtro.' }))
            : issueList(issues, { emptyText: section.issues.length ? 'Sin problemas para este filtro.' : 'Sin problemas.' }),
        });
      }));
  }

  mount(root, h('div', { class: 'row row--between' }, filter, h('div', { class: 'row' }, refreshBtn, runtimeBtn)), host);
  await load(false, false);
}
