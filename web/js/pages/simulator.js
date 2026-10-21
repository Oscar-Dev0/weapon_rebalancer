import { api } from '../core/api.js';
import { h, icon, mount, setLoading } from '../core/dom.js';
import { num, pct, rpm, seconds } from '../core/format.js';
import { loadCatalog, store } from '../core/store.js';
import { badge, callout, card, empty, help, lineChart, loading, segmented, seriesColor, toastError } from '../components/ui.js';

const SOURCES = [
  { value: 'original', label: 'Original (.bak)' },
  { value: 'current', label: 'Actual' },
  { value: 'proposed', label: 'Propuesto' },
];

export async function render({ root, params, setTitle, isCurrent }) {
  setTitle('Simulador', 'Estimaciones teóricas de daño, cadencia, DPS y TTK');
  const catalog = await loadCatalog();
  const profiles = (await api.get('/api/profiles')).profiles;
  const weapons = catalog.weapons.filter((w) => w.in_meta && !w.internal);
  const first = params.get('w') || 'WEAPON_PISTOL';
  const state = {
    profile: params.get('p') || store.draft?.id || store.status.active_profile,
    series: params.get('w')
      ? [{ name: first, source: 'original' }, { name: first, source: 'current' }, { name: first, source: 'proposed' }]
      : [{ name: 'WEAPON_PISTOL', source: 'current' }, { name: 'WEAPON_CARBINERIFLE', source: 'current' }],
    assumptions: { target: 'player', zone: 'torso', distance: 15, health: 100, armour: 0, armour_absorption: 1, armour_protects_head: true, critical_hits: true, pellet_hit_ratio: 1, include_reload: true },
    chart: 'damage',
    result: null,
  };
  const seriesHost = h('div', { class: 'stack stack--sm' });
  const resultHost = h('div', { class: 'stack' });
  const runBtn = h('button', { class: 'btn btn--primary', onclick: () => run() }, icon('play'), 'Calcular');
  const datalist = h('datalist', { id: 'sim-weapons' }, weapons.map((w) => h('option', { value: w.name }, w.label)));
  const profileSelect = h('select', { class: 'select' }, profiles.map((p) => h('option', { value: p.id, selected: p.id === state.profile }, p.id)));
  profileSelect.addEventListener('change', () => { state.profile = profileSelect.value; });

  function drawSeries() {
    mount(seriesHost, state.series.map((s, index) => {
      const input = h('input', { class: 'input input--sm', list: 'sim-weapons', value: s.name, style: { width: '230px' } });
      input.addEventListener('change', () => { s.name = input.value.trim().toUpperCase(); });
      const source = h('select', { class: 'select', style: { width: '160px', height: '28px' } }, SOURCES.map((o) => h('option', { value: o.value, selected: o.value === s.source }, o.label)));
      source.addEventListener('change', () => { s.source = source.value; });
      return h('div', { class: 'row' }, h('span', { style: { width: '12px', height: '12px', borderRadius: '3px', background: seriesColor(index) } }), input, source,
        h('button', { class: 'btn btn--sm btn--ghost', disabled: state.series.length < 2, onclick: () => { state.series.splice(index, 1); drawSeries(); } }, icon('x')));
    }), state.series.length < 8 ? h('button', { class: 'btn btn--sm', onclick: () => { state.series.push({ name: 'WEAPON_SMG', source: 'current' }); drawSeries(); } }, icon('plus'), 'Añadir serie') : null);
  }

  function assumptionField(key, label, hint, attrs = {}) {
    const input = h('input', { class: 'input input--sm input--num', type: 'number', value: state.assumptions[key], ...attrs });
    input.addEventListener('change', () => { state.assumptions[key] = Number(input.value); });
    return h('div', { class: 'field' }, h('label', {}, label, ' ', help({ title: label, text: hint, doc: 'balanceo/supuestos' })), input);
  }
  function assumptionCheck(key, label, hint) {
    const input = h('input', { type: 'checkbox', checked: state.assumptions[key] });
    input.addEventListener('change', () => { state.assumptions[key] = input.checked; });
    return h('label', { class: 'check', title: hint }, input, label);
  }

  async function run() {
    setLoading(runBtn, true);
    mount(resultHost, loading('Calculando…'));
    try {
      const body = { weapons: state.series, profile_id: state.profile, assumptions: state.assumptions, series: true };
      // Si el perfil elegido es el borrador con cambios sin guardar, se simula el borrador.
      if (store.draft?.id === state.profile && store.draft.dirty) body.profile = store.draft.profile;
      state.result = await api.post('/api/simulate', body);
      if (isCurrent()) drawResult();
    } catch (error) {
      mount(resultHost, callout('err', [error.message, error.hint ? h('div', { class: 'small' }, error.hint) : null]));
      toastError(error);
    }
    setLoading(runBtn, false);
  }

  function label(r) {
    const w = weapons.find((x) => x.name === r.name);
    return `${w?.label || r.name} · ${SOURCES.find((s) => s.value === r.source)?.label}`;
  }

  function drawResult() {
    const results = state.result.results;
    const table = h('table', { class: 'table' },
      h('thead', {}, h('tr', {}, ['Serie', 'Daño/disparo', 'Disparos', 'TTK', 'DPS', 'DPS c/recarga', 'RPM', 'Cargador'].map((t, i) => h('th', { class: i ? 'num' : '' }, t)))),
      h('tbody', {}, results.map((item, index) => {
        const r = item.result;
        const d = item.delta || {};
        const delta = (value, key, invert = false) => (index && d[key] !== null && d[key] !== undefined && Math.abs(d[key]) > 0.05
          ? h('div', { class: `small ${(d[key] > 0) !== invert ? 'delta-up' : 'delta-down'}` }, pct(d[key])) : null);
        return h('tr', {},
          h('td', {}, h('span', { style: { display: 'inline-block', width: '10px', height: '10px', borderRadius: '3px', background: seriesColor(index), marginRight: '8px' } }), label(item),
            r.damage.note ? h('div', { class: 'small muted' }, r.damage.note) : null,
            r.damage.out_of_range ? badge('fuera de alcance', 'warn') : null),
          h('td', { class: 'num' }, num(r.damage.per_shot), delta(0, 'per_shot')),
          h('td', { class: 'num' }, r.shots_to_kill ?? '—', delta(0, 'shots_to_kill', true)),
          h('td', { class: 'num' }, seconds(r.ttk), r.reloads ? h('div', { class: 'small muted' }, `${r.reloads} recarga(s)`) : null, delta(0, 'ttk', true)),
          h('td', { class: 'num' }, num(r.dps, 1), delta(0, 'dps')),
          h('td', { class: 'num' }, num(r.dps_sustained, 1)),
          h('td', { class: 'num' }, rpm(r.rpm), delta(0, 'rpm')),
          h('td', { class: 'num' }, r.clip_size ?? '—'));
      })));
    const chartHost = h('div', {});
    const drawChart = () => {
      const zone = state.assumptions.zone;
      if (state.chart === 'damage') {
        mount(chartHost, lineChart({
          xLabel: 'distancia (m)', yLabel: `daño por disparo (${zone})`,
          series: results.map((item, i) => ({ label: label(item), color: seriesColor(i), points: item.series.rows.map((row) => [row.distance, row[zone]]) })),
        }));
      } else {
        mount(chartHost, lineChart({
          xLabel: 'distancia (m)', yLabel: 'TTK (s)', formatY: (v) => v.toFixed(2),
          series: results.map((item, i) => ({ label: label(item), color: seriesColor(i), points: item.series.rows.map((row) => [row.distance, row.ttk]) })),
        }));
      }
    };
    mount(resultHost,
      callout('purple', [h('strong', {}, 'Cálculo teórico. '), state.result.disclaimer, ' Modelo: daño × modificador de objetivo × zona × caída lineal × perdigones; el blindaje absorbe según los supuestos.']),
      card({ title: 'Resultados', iconName: 'simulator', body: h('div', { class: 'table-wrap' }, table) }),
      card({ title: 'Por distancia', iconName: 'ruler', actions: segmented([{ value: 'damage', label: 'Daño' }, { value: 'ttk', label: 'TTK' }], state.chart, (v) => { state.chart = v; drawChart(); }), body: chartHost }));
    drawChart();
  }

  const zone = segmented([{ value: 'torso', label: 'Torso' }, { value: 'head', label: 'Cabeza' }, { value: 'limbs', label: 'Extremidades' }], state.assumptions.zone, (v) => { state.assumptions.zone = v; });
  const target = segmented([{ value: 'player', label: 'Jugador' }, { value: 'npc', label: 'NPC' }], state.assumptions.target, (v) => { state.assumptions.target = v; });

  mount(root, datalist,
    h('div', { class: 'grid grid--side' },
      h('div', { class: 'stack' },
        card({ title: 'Series a comparar', iconName: 'compare', actions: runBtn, body: h('div', { class: 'stack' },
          h('div', { class: 'row' }, h('span', { class: 'label' }, 'Perfil para “Propuesto”'), profileSelect,
            help({ title: 'Propuesto', text: 'Valores que produciría el perfil elegido al aplicarse sobre el pack (se calcula con el motor real).' })),
          seriesHost) }),
        resultHost),
      card({ title: 'Supuestos', iconName: 'settings', body: h('div', { class: 'stack' },
        h('div', { class: 'field' }, h('label', {}, 'Objetivo'), target),
        h('div', { class: 'field' }, h('label', {}, 'Zona de impacto'), zone),
        h('div', { class: 'grid grid--2' },
          assumptionField('distance', 'Distancia (m)', 'Distancia del disparo para la tabla. Las gráficas recorren todo el alcance.', { min: 0, step: 1 }),
          assumptionField('health', 'Vida efectiva', 'Un jugador de FiveM tiene 200 de vida y muere al bajar de 100: 100 puntos efectivos.', { min: 1, step: 1 }),
          assumptionField('armour', 'Blindaje', 'Puntos de chaleco (0–100 en GTA).', { min: 0, step: 1 }),
          assumptionField('armour_absorption', 'Absorción del blindaje', 'Fracción del daño que absorbe el chaleco mientras dura (supuesto: 1 = todo).', { min: 0, max: 1, step: 0.05 }),
          assumptionField('pellet_hit_ratio', 'Perdigones que impactan', 'Fracción de perdigones que aciertan (escopetas).', { min: 0, max: 1, step: 0.05 })),
        assumptionCheck('critical_hits', 'Critical hits activos (cabeza)', 'Si un script los apaga, la cabeza cuenta como torso.'),
        assumptionCheck('armour_protects_head', 'El blindaje protege la cabeza', 'Así funciona en el juego: el chaleco absorbe primero también en la cabeza (salvo ArmourPenetrating).'),
        assumptionCheck('include_reload', 'Incluir recargas en el TTK', 'Suma el tiempo de recarga si hacen falta más balas que el cargador.'),
        callout('info', 'Los supuestos solo afectan al cálculo. No cambian nada del perfil ni del servidor.')) })));
  drawSeries();
  run();
  void empty;
}
