// Fila de edición de un parámetro (slider + valor exacto + valores de referencia).
import { h, icon, mount } from '../core/dom.js';
import { num, same, withUnit } from '../core/format.js';
import { getField, getMultiplier, inheritedField, isNulled, scopeOp } from '../core/profile-edit.js';
import { applyOps } from '../core/ops.js';
import { store } from '../core/store.js';
import { badge, help, toast } from './ui.js';

const METHOD_VARIANT = { meta: 'purple', native: 'blue', resource: 'info', readonly: 'outline', unsupported: 'err' };

export function methodBadge(method) {
  const info = store.registry.methods[method] || { label: method };
  return h('span', { class: `badge method badge--${METHOD_VARIANT[method] || ''}`, title: info.description }, info.label);
}

export function helpFor(spec) {
  return help({
    title: spec.label,
    text: spec.description || 'Sin descripción adicional.',
    notes: [spec.notes, spec.hard_min !== null && spec.hard_min !== undefined ? `El motor recorta a ${spec.hard_min} – ${spec.hard_max}.` : ''].filter(Boolean).join(' '),
    doc: `parametros#${spec.key}`,
  });
}

/** Aplica un valor al borrador (en el servidor: activa módulos y pide confirmación si hace falta). */
export async function commitField(scope, key, value) {
  return applyOps([{ op: 'set_field', scope: scopeOp(scope), key, value }]);
}

/**
 * spec: parámetro del registro. scope: {type, name}. ref: {original, current, proposed} del arma de referencia.
 */
export function paramRow(spec, scope, ref = {}) {
  const row = h('div', { class: 'param' });
  const draw = () => {
    const profile = store.draft?.profile;
    const authored = profile ? getField(profile, scope, spec.key) : undefined;
    const isSet = authored !== undefined;
    const nulled = profile ? isNulled(profile, scope, spec.key) : false;
    const inherited = inheritedField(scope, spec.key);
    const readOnly = !spec.editable || !profile || !store.draft?.editable;
    const base = isSet ? authored : (ref.current ?? ref.original ?? spec.slider_min ?? 0);
    const multiplier = scope.type === 'weapon' && profile ? getMultiplier(profile, scope.name, spec.key) : undefined;
    row.className = `param ${isSet ? 'is-set' : ''} ${readOnly ? 'is-readonly' : ''}`;

    const notes = [];
    if (isSet && typeof authored === 'number' && spec.hard_min !== null && spec.hard_min !== undefined) {
      if (authored < spec.hard_min || authored > spec.hard_max) {
        notes.push(h('div', { class: 'param__note warn' }, `Fuera de los límites del motor: se recortará a ${Math.min(Math.max(authored, spec.hard_min), spec.hard_max)}.`));
      }
    }
    if (multiplier !== undefined) notes.push(h('div', { class: 'param__note warn' }, `Después se multiplica ×${multiplier} (weapon_field_multipliers).`));
    if (spec.value_type === 'integer' && isSet && !Number.isInteger(authored)) notes.push(h('div', { class: 'param__note warn' }, 'Este campo es entero.'));

    let control;
    if (readOnly) {
      control = h('span', { class: 'mono small muted' }, ref.current !== undefined ? String(ref.current) : '—');
    } else {
      const min = Math.min(spec.slider_min ?? 0, Number(base) || 0);
      const max = Math.max(spec.slider_max ?? 100, Number(base) || 0);
      const slider = h('input', { type: 'range', class: 'range', min, max, step: spec.step ?? 0.01, value: base, 'aria-label': spec.label });
      const input = h('input', { class: 'input input--num', type: 'number', step: spec.step ?? 'any', value: base, 'aria-label': `${spec.label} (valor exacto)` });
      const commit = async (raw) => {
        const value = spec.value_type === 'integer' ? Math.round(Number(raw)) : Number(raw);
        if (!Number.isFinite(value)) { toast('Valor inválido.', { type: 'err' }); draw(); return; }
        if (isSet && same(value, authored)) return;
        const ok = await commitField(scope, spec.key, value);
        if (!ok) draw();
      };
      slider.addEventListener('input', () => { input.value = slider.value; });
      slider.addEventListener('change', () => commit(slider.value));
      input.addEventListener('change', () => commit(input.value));
      input.addEventListener('keydown', (e) => { if (e.key === 'Enter') input.blur(); });
      const unsetTitle = nulled ? 'Volver a heredar del perfil base'
        : inherited !== undefined ? `Quitar del perfil (vuelve al heredado: ${num(inherited)})` : 'Quitar del perfil (usar el valor actual)';
      const reset = isSet || nulled ? h('button', { class: 'btn btn--ghost btn--sm', title: unsetTitle, onclick: () => {
        applyOps([{ op: 'unset_field', scope: scopeOp(scope), key: spec.key }], { quiet: true });
      } }, icon('undo')) : null;
      // Solo en derivados: null quita lo heredado (misma operación que `wr.py set … campo=inherit`).
      const noInherit = !isSet && !nulled && inherited !== undefined ? h('button', {
        class: 'btn btn--ghost btn--sm', title: `No heredar ${num(inherited)} del perfil base (escribe null)`,
        onclick: () => applyOps([{ op: 'inherit_field', scope: scopeOp(scope), key: spec.key }], { quiet: true }),
      }, 'No heredar') : null;
      control = h('div', { class: 'param__control' }, slider, input, spec.unit && spec.unit !== 'x' ? h('span', { class: 'small muted nowrap' }, spec.unit) : null, reset, noInherit);
    }

    const changed = ref.proposed !== undefined && ref.current !== undefined && !same(ref.proposed, ref.current);
    mount(row,
      h('div', { class: 'param__name' },
        h('strong', {}, spec.label, helpFor(spec)),
        h('div', { class: 'row', style: { gap: '6px' } }, methodBadge(spec.method), h('code', {}, spec.tag), isSet ? badge('en el perfil', 'purple') : null,
          nulled ? badge('no hereda', 'warn') : null,
          !isSet && !nulled && inherited !== undefined ? badge(`heredado: ${num(inherited)}`, 'blue') : null)),
      control,
      h('div', { class: 'param__values' },
        h('span', {}, h('small', {}, 'Original'), withUnit(ref.original, spec.unit)),
        h('span', {}, h('small', {}, 'Actual'), withUnit(ref.current, spec.unit)),
        h('span', { class: changed ? 'proposed' : '' }, h('small', {}, 'Propuesto'), ref.proposed === undefined ? '—' : withUnit(ref.proposed, spec.unit))),
      notes);
  };
  draw();
  row.redraw = draw;
  return row;
}

export function valueOrDash(value) {
  return value === undefined || value === null ? '—' : num(value);
}
