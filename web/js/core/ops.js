// Modificaciones del borrador: siempre en el servidor (misma lógica que la terminal).
import { api } from './api.js';
import { h } from './dom.js';
import { markDirty, openDraft, store } from './store.js';
import { callout, confirmDialog, formDialog, toast, toastError } from '../components/ui.js';

/** Aplica operaciones al borrador. Devuelve true si se aplicaron. */
export async function applyOps(ops, { quiet = false } = {}) {
  const draft = store.draft;
  if (!draft) return false;
  if (!draft.editable) {
    toast(`“${draft.id}” está protegido.`, { type: 'warn', detail: 'Crea un perfil derivado para modificarlo (Perfiles → Crear derivado).' });
    return false;
  }
  try {
    const body = { profile_id: draft.id, profile: draft.profile, ops };
    let result = await api.post('/api/profiles/ops', body);
    if (result.confirmations?.length) {
      const lines = result.confirmations.flatMap((c) => c.dormant);
      const ok = await confirmDialog({
        title: 'Activar módulo',
        confirmLabel: 'Activar y aplicar',
        message: h('div', { class: 'stack stack--sm' },
          h('p', {}, `Para que el valor tenga efecto hay que activar ${[...new Set(result.confirmations.flatMap((c) => c.modules))].map((m) => `modules.${m}`).join(', ')}.`),
          h('p', {}, `Eso también activará ${lines.length} valor(es) ya escritos que hoy no tienen efecto:`),
          h('pre', { class: 'code', style: { maxHeight: '200px' } }, lines.slice(0, 40).join('\n'))),
      });
      if (!ok) return false;
      result = await api.post('/api/profiles/ops', { ...body, confirm_dormant: true });
    }
    draft.profile = result.profile;
    if ('base' in result) draft.base = result.base;
    markDirty();
    if (result.notices?.length && !quiet) toast('Cambio aplicado al borrador.', { type: 'info', detail: result.notices.join(' · '), timeout: 7000 });
    return true;
  } catch (error) {
    toastError(error, 'No se aplicó: ');
    return false;
  }
}

/** Crea un perfil de usuario que hereda del borrador actual y lo abre. */
export async function deriveDraft(navigate, nextPath = '/constructor') {
  const draft = store.draft;
  if (!draft) return;
  const values = await formDialog({
    title: `Crear perfil derivado de ${draft.id}`,
    intro: callout('info', 'El derivado hereda todo y guarda solo tus cambios. Se crea en profiles/user/.'),
    fields: [
      { name: 'new_id', label: 'Identificador', value: `${draft.id}_mio`, hint: 'Minúsculas, números, - y _.' },
      { name: 'name', label: 'Nombre visible', value: `${draft.summary?.name || draft.id} (derivado)` },
    ],
    submitLabel: 'Crear derivado',
  });
  if (!values) return;
  try {
    await api.post(`/api/profiles/${encodeURIComponent(draft.id)}/derive`, values);
    await openDraft(values.new_id, { force: true });
    toast(`Perfil “${values.new_id}” creado.`, { detail: 'Ya puedes editarlo.' });
    navigate(`${nextPath}${nextPath.includes('?') ? '&' : '?'}p=${values.new_id}`);
  } catch (error) { toastError(error); }
}

/** Aviso para perfiles protegidos (oficiales, archivados o servidor bloqueado). */
export function protectedNotice(navigate, nextPath) {
  const draft = store.draft;
  if (!draft || draft.editable) return null;
  const tier = { official: 'oficial', legacy: 'archivado', server: 'del servidor (edición desactivada)' }[draft.tier] || 'protegido';
  return callout('warn', [h('strong', {}, `“${draft.id}” es un perfil ${tier}: solo lectura. `),
    'Para modificarlo crea un perfil derivado: hereda todo y guarda solo tus cambios. ',
    h('button', { class: 'btn btn--sm btn--primary', style: { marginLeft: '8px' }, onclick: () => deriveDraft(navigate, nextPath) }, 'Crear derivado')]);
}
