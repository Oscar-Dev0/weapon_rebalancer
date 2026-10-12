// Estado compartido del panel: estado del servidor, registro de parámetros,
// catálogo en caché y el borrador del perfil que se está editando.
import { api } from './api.js';

const listeners = new Set();

export const store = {
  status: null,
  registry: null,          // { sections, methods, params:[], ... }
  params: new Map(),       // key -> spec
  catalog: null,           // { summary, weapons: [] }
  draft: null,             // { id, profile, sha, dirty, savedJson }
  preview: null,           // última vista previa del borrador { key, data }
};

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function emit(event, payload) {
  for (const fn of listeners) fn(event, payload);
}

export async function loadStatus() {
  store.status = await api.get('/api/status');
  emit('status', store.status);
  return store.status;
}

export async function loadRegistry() {
  if (store.registry) return store.registry;
  store.registry = await api.get('/api/params');
  store.params = new Map(store.registry.params.map((p) => [p.key, p]));
  return store.registry;
}

export async function loadCatalog(force = false) {
  if (store.catalog && !force) return store.catalog;
  store.catalog = await api.get(`/api/catalog${force ? '?refresh=1' : ''}`);
  emit('catalog', store.catalog);
  return store.catalog;
}

export function catalogWeapon(name) {
  return store.catalog?.weapons.find((w) => w.name === name) || null;
}

// ---- borrador de perfil ---------------------------------------------------------
export async function openDraft(id, { force = false } = {}) {
  if (store.draft && store.draft.id === id && !force) return store.draft;
  if (store.draft?.dirty && store.draft.id !== id && !force) {
    const ok = window.confirm(`Hay cambios sin guardar en “${store.draft.id}”. ¿Descartarlos y abrir “${id}”?`);
    if (!ok) return store.draft;
  }
  const data = await api.get(`/api/profiles/${encodeURIComponent(id)}`);
  store.draft = {
    id,
    profile: data.profile,
    resolved: data.resolved,
    base: data.base,
    sha: data.sha,
    dirty: false,
    savedJson: JSON.stringify(data.profile),
    legacy: data.legacy,
    tier: data.tier,
    editable: data.editable,
    summary: data.summary,
    validation: data.validation,
    children: data.children,
  };
  store.preview = null;
  emit('draft', store.draft);
  return store.draft;
}

export function markDirty() {
  if (!store.draft) return;
  store.draft.dirty = JSON.stringify(store.draft.profile) !== store.draft.savedJson;
  store.preview = null;
  emit('draft', store.draft);
}

export async function saveDraft(note = '') {
  const draft = store.draft;
  if (!draft) return null;
  const result = await api.put(`/api/profiles/${encodeURIComponent(draft.id)}`, { profile: draft.profile, sha: draft.sha, note });
  await openDraft(draft.id, { force: true });
  emit('saved', result);
  return result;
}

export function discardDraft() {
  if (!store.draft) return;
  store.draft.profile = JSON.parse(store.draft.savedJson);
  store.draft.dirty = false;
  store.preview = null;
  emit('draft', store.draft);
}

export async function draftPreview(force = false) {
  const draft = store.draft;
  if (!draft) return null;
  const key = JSON.stringify(draft.profile);
  if (!force && store.preview?.key === key) return store.preview.data;
  const data = await api.post('/api/preview', { profile_id: draft.id, profile: draft.profile });
  store.preview = { key, data };
  emit('preview', data);
  return data;
}

window.addEventListener('beforeunload', (event) => {
  if (store.draft?.dirty) {
    event.preventDefault();
    event.returnValue = '';
  }
});
