// Arranque del panel: navegación, barra superior y enrutado por hash.
import { h, icon, mount } from './core/dom.js';
import { discardDraft, loadRegistry, loadStatus, saveDraft, store, subscribe } from './core/store.js';
import { confirmDialog, loading, toast, toastError } from './components/ui.js';

const ROUTES = [
  { path: '/', label: 'Dashboard', icon: 'dashboard', group: 'General', module: './pages/dashboard.js' },
  { path: '/armamento', label: 'Armamento', icon: 'weapons', group: 'General', module: './pages/weapons.js' },
  { path: '/editor', label: 'Editor', icon: 'editor', group: 'Balanceo', module: './pages/editor.js' },
  { path: '/perfiles', label: 'Perfiles', icon: 'profiles', group: 'Balanceo', module: './pages/profiles.js' },
  { path: '/constructor', label: 'Constructor', icon: 'builder', group: 'Balanceo', module: './pages/builder.js' },
  { path: '/simulador', label: 'Simulador', icon: 'simulator', group: 'Balanceo', module: './pages/simulator.js' },
  { path: '/generador', label: 'Generador', icon: 'generator', group: 'Servidor', module: './pages/generator.js' },
  { path: '/diagnostico', label: 'Diagnóstico', icon: 'diagnostics', group: 'Servidor', module: './pages/diagnostics.js' },
  { path: '/documentacion', label: 'Documentación', icon: 'docs', group: 'Ayuda', module: './pages/docs.js' },
  { path: '/configuracion', label: 'Configuración', icon: 'settings', group: 'Ayuda', module: './pages/settings.js' },
];

const content = document.getElementById('content');
let cleanup = null;
let renderToken = 0;

function parseHash() {
  const raw = location.hash.replace(/^#/, '') || '/';
  const [path, query = ''] = raw.split('?');
  return { path: path || '/', params: new URLSearchParams(query) };
}

export function navigate(path) {
  location.hash = `#${path}`;
}

function setTitle(title, subtitle = '') {
  document.getElementById('page-title').textContent = title;
  document.getElementById('page-subtitle').textContent = subtitle;
  document.title = `${title} · Weapon Rebalancer`;
}

function renderNav(activePath) {
  const nav = document.getElementById('nav');
  const groups = [...new Set(ROUTES.map((r) => r.group))];
  mount(nav, groups.map((group) => [
    h('div', { class: 'nav__label' }, group),
    ROUTES.filter((r) => r.group === group).map((route) => h('a', {
      href: `#${route.path}`, class: route.path === activePath ? 'active' : '',
      onclick: () => document.getElementById('sidebar').classList.remove('open'),
    }, icon(route.icon), route.label, route.path === '/diagnostico' && store.status
      ? h('span', { class: 'count' }, String(store.status.catalog.issues.error + store.status.catalog.issues.warning)) : null)),
  ]));
}

function renderTopSlots() {
  const draftSlot = document.getElementById('draft-slot');
  const profileSlot = document.getElementById('profile-slot');
  const draft = store.draft;
  if (draft?.dirty) {
    const saveButton = h('button', { class: 'btn btn--sm btn--primary', onclick: async () => {
      saveButton.classList.add('is-loading');
      try {
        const result = await saveDraft();
        toast(result?.changed === false ? 'No había cambios que guardar.' : `Perfil “${draft.id}” guardado.`,
          { detail: 'La versión anterior quedó en el historial.' });
      } catch (error) { toastError(error, 'No se guardó: '); }
      saveButton.classList.remove('is-loading');
    } }, icon('save'), 'Guardar');
    mount(draftSlot, h('div', { class: 'draft-bar' }, h('span', { class: 'dot' }), `Cambios sin guardar en ${draft.id}`,
      h('a', { class: 'btn btn--sm btn--ghost', href: `#/constructor?p=${draft.id}&step=review` }, 'Revisar'),
      h('button', { class: 'btn btn--sm btn--ghost', onclick: async () => {
        if (await confirmDialog({ title: 'Descartar cambios', message: `Se perderán los cambios sin guardar de “${draft.id}”.`, confirmLabel: 'Descartar', danger: true })) {
          discardDraft();
          toast('Cambios descartados.', { type: 'info' });
          route();
        }
      } }, 'Descartar'),
      saveButton));
  } else {
    mount(draftSlot);
  }
  const active = store.status?.active_profile;
  mount(profileSlot, active ? h('a', { class: 'badge badge--purple', href: '#/perfiles', title: 'Perfil activo' }, icon('star'), active) : null);
}

async function route() {
  const { path, params } = parseHash();
  const found = ROUTES.find((r) => r.path === path) || ROUTES[0];
  renderNav(found.path);
  renderTopSlots();
  if (cleanup) { try { cleanup(); } catch { /* noop */ } cleanup = null; }
  const token = ++renderToken;
  mount(content, loading());
  setTitle(found.label);
  try {
    const module = await import(found.module);
    if (token !== renderToken) return;
    const root = h('div', { class: 'stack' });
    mount(content, root);
    cleanup = await module.render({ root, params, setTitle, navigate, isCurrent: () => token === renderToken }) || null;
  } catch (error) {
    if (token !== renderToken) return;
    mount(content, h('div', { class: 'callout callout--err' }, icon('alert'),
      h('div', {}, h('strong', {}, 'No se pudo cargar esta sección. '), error.message || String(error),
        error.hint ? h('div', { class: 'small' }, error.hint) : null)));
    console.error(error);
  }
}

async function boot() {
  document.getElementById('brand-mark').append(icon('logo', 'icon--lg'));
  document.getElementById('menu-button').append(icon('menu'));
  document.getElementById('menu-button').addEventListener('click', () => document.getElementById('sidebar').classList.toggle('open'));
  try {
    await Promise.all([loadStatus(), loadRegistry()]);
    document.getElementById('brand-version').textContent = `v${store.status.version} · FiveM · ox_inventory`;
  } catch (error) {
    mount(content, h('div', { class: 'callout callout--err' }, icon('alert'), h('div', {}, error.message, error.hint ? h('div', { class: 'small' }, error.hint) : null)));
    return;
  }
  subscribe((event) => { if (['draft', 'saved', 'status'].includes(event)) renderTopSlots(); });
  window.addEventListener('hashchange', route);
  route();
}

boot();
