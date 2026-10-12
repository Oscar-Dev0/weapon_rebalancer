import { api } from '../core/api.js';
import { h, icon, mount, setLoading } from '../core/dom.js';
import { date } from '../core/format.js';
import { loadCatalog, loadStatus, store } from '../core/store.js';
import { badge, callout, card, empty, help, issueList, jsonView, loading, toast, toastError } from '../components/ui.js';

export async function render({ root, setTitle, isCurrent }) {
  setTitle('Configuración', 'Rutas del servidor, perfil activo y registro de cambios');
  const [{ workspace, errors }, { profiles }] = await Promise.all([api.get('/api/workspace'), api.get('/api/profiles')]);
  const form = {};
  const text = (key, label, hint, value = workspace[key]) => {
    const input = h('input', { class: 'input mono', value: value || '', spellcheck: 'false' });
    form[key] = input;
    return h('div', { class: 'field' }, h('label', {}, label, ' ', help({ title: label, text: hint, doc: 'instalacion/rutas' })), input);
  };
  const list = (key, label, hint) => {
    const area = h('textarea', { class: 'textarea mono', style: { minHeight: '70px' } });
    area.value = (workspace[key] || []).join('\n');
    form[key] = area;
    return h('div', { class: 'field' }, h('label', {}, label, ' ', help({ title: label, text: hint, doc: 'instalacion/rutas' })), area, h('span', { class: 'hint' }, 'Una ruta por línea.'));
  };
  const active = h('select', { class: 'select' }, profiles.map((p) => h('option', { value: p.id, selected: p.id === workspace.active_profile }, p.id)));
  form.active_profile = active;
  const serverEditable = h('input', { type: 'checkbox', checked: workspace.server_profiles_editable !== false });
  form.server_profiles_editable = serverEditable;

  const errorsHost = h('div', {}, errors.length ? issueList(errors.map((message) => ({ severity: 'error', message }))) : callout('ok', 'Todas las rutas son válidas.'));
  const saveBtn = h('button', { class: 'btn btn--primary', onclick: async () => {
    const body = {};
    for (const [key, input] of Object.entries(form)) {
      if (input.type === 'checkbox') body[key] = input.checked;
      else body[key] = ['pack_roots', 'reference_roots'].includes(key) ? input.value.split('\n').map((v) => v.trim()).filter(Boolean) : input.value.trim();
    }
    setLoading(saveBtn, true);
    try {
      await api.put('/api/workspace', body);
      await Promise.all([loadStatus(), loadCatalog(true)]);
      mount(errorsHost, callout('ok', 'Configuración guardada y catálogo reescaneado.'));
      toast('Configuración guardada.');
    } catch (error) {
      mount(errorsHost, issueList((error.details || [error.message]).map((message) => ({ severity: 'error', message }))));
      toastError(error);
    }
    setLoading(saveBtn, false);
  } }, icon('save'), 'Guardar');
  const detectBtn = h('button', { class: 'btn', onclick: async () => {
    try {
      const { detected } = await api.get('/api/workspace/detect');
      for (const key of ['server_root', 'ox_inventory_dir', 'qbx_recoils_file']) if (form[key] && detected[key]) form[key].value = detected[key];
      if (detected.pack_roots?.length) form.pack_roots.value = detected.pack_roots.join('\n');
      toast('Rutas detectadas. Revisa y guarda.', { type: 'info' });
    } catch (error) { toastError(error); }
  } }, icon('search'), 'Detectar automáticamente');

  const logsHost = h('div', {}, loading());
  mount(root,
    h('div', { class: 'grid grid--side' },
      card({ title: 'Rutas', iconName: 'folder', actions: h('div', { class: 'row' }, detectBtn, saveBtn), body: h('div', { class: 'stack' },
        errorsHost,
        text('server_root', 'Carpeta del servidor', 'Raíz del servidor FiveM (la que contiene resources/). Todas las demás rutas deben estar dentro.'),
        list('pack_roots', 'Packs de armas', 'Carpetas que contienen los weapons.meta. El generador solo escribe dentro de ellas.'),
        text('ox_inventory_dir', 'ox_inventory', 'Carpeta del recurso ox_inventory (con data/weapons.lua). Solo se lee.'),
        text('qbx_recoils_file', 'qbx_recoils/config.lua', 'Config del recoil vertical por script. Vacío = no usar.'),
        text('runtime_audit_root', 'Carpeta para auditar scripts', 'Por defecto resources/ completo.'),
        list('reference_roots', 'Packs de referencia (opcional)', 'META originales de GTA V usados por baseline_repair. Nunca se escriben.'),
        h('div', { class: 'field' }, h('label', {}, 'Perfil activo'), active, h('span', { class: 'hint' }, 'Es el que se compara con el pack en el Dashboard y el Diagnóstico.')),
        h('div', { class: 'field' }, h('label', { class: 'row', style: { gap: '8px' } }, serverEditable, 'Permitir editar perfiles del servidor', ' ',
          help({ title: 'Perfiles del servidor', text: 'Si está desactivado, flow_custom (profiles/server/) queda en solo lectura, igual que los oficiales. Cada guardado deja la versión anterior en el historial.', doc: 'perfiles/niveles' })))) }),
      h('div', { class: 'stack' },
        card({ title: 'Servidor del panel', iconName: 'shield', body: h('dl', { class: 'kv' },
          h('dt', {}, 'Escucha'), h('dd', { class: 'mono' }, `${workspace.server.host}:${workspace.server.port}`),
          h('dt', {}, 'Versión'), h('dd', {}, store.status.version),
          h('dt', {}, 'Sesión'), h('dd', {}, 'Token por arranque + cabecera X-WR-Token'),
          h('dt', {}, 'Datos'), h('dd', { class: 'mono small' }, 'data/ (workspace, historial, backups, logs)')) }),
        card({ title: 'Seguridad', iconName: 'shield', body: h('ul', { class: 'small', style: { margin: 0, paddingLeft: '18px', lineHeight: 1.8 } },
          h('li', {}, 'Solo escucha en 127.0.0.1 salvo que uses --host.'),
          h('li', {}, 'Escrituras limitadas a los packs, qbx_recoils, profiles/ y data/.'),
          h('li', {}, 'Escritura atómica y respaldo previo de cada archivo.'),
          h('li', {}, 'Nada se aplica al servidor sin escribir APLICAR.')) }))),
    card({ title: 'Registro de cambios aplicados', iconName: 'history', body: logsHost }));

  try {
    const { entries } = await api.get('/api/logs?stream=changes');
    if (!isCurrent()) return;
    mount(logsHost, entries.length ? h('table', { class: 'table table--compact' },
      h('thead', {}, h('tr', {}, h('th', {}, 'Fecha'), h('th', {}, 'Evento'), h('th', {}, 'Detalle'))),
      h('tbody', {}, entries.slice().reverse().map((e) => h('tr', {}, h('td', { class: 'nowrap' }, date(e.ts)), h('td', {}, badge(e.event, 'purple')),
        h('td', {}, h('details', {}, h('summary', { class: 'small' }, `${e.profile || ''} ${e.tx || ''} ${e.files ? `· ${e.files} archivos` : ''}`), jsonView(e))))))) : empty('Sin cambios registrados.', 'history'));
  } catch (error) { mount(logsHost, callout('err', error.message)); }
}
