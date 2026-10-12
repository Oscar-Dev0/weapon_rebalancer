import { api } from '../core/api.js';
import { h, icon, mount } from '../core/dom.js';
import { date, plural } from '../core/format.js';
import { loadStatus, store } from '../core/store.js';
import { badge, barList, callout, card, issueList, kpi, loading, toastError } from '../components/ui.js';

export async function render({ root, setTitle, isCurrent }) {
  setTitle('Dashboard', 'Resumen del armamento, perfiles y estado de generación');
  const status = await loadStatus();
  const c = status.catalog;

  const activeCard = h('div', {}, loading('Comparando el perfil activo con el pack…'));
  const issuesCard = h('div', {}, loading('Reuniendo diagnóstico…'));

  mount(root,
    h('div', { class: 'grid grid--4' },
      kpi(c.weapons, 'Armas detectadas', { variant: 'purple', hint: `${c.official} oficiales · ${c.custom} personalizadas` }),
      kpi(c.definitions, 'Definiciones CWeaponInfo', { variant: 'blue', hint: `${c.meta_files} archivos .meta en ${status.workspace.pack_roots.length} pack(s)` }),
      kpi(c.modified_vs_original, 'Modificadas frente al .bak', { hint: 'Armas cuyo META difiere de su respaldo original' }),
      kpi(status.profiles, 'Perfiles', { hint: `Activo: ${status.active_profile}` }),
    ),
    h('div', { class: 'grid grid--4' },
      kpi(c.ox_only, 'En ox_inventory sin META', { variant: c.ox_only ? 'warn' : 'ok', hint: 'Ítems sin modelo ni stats en los packs' }),
      kpi(c.duplicates, 'Definiciones duplicadas', { variant: c.duplicates ? 'warn' : 'ok', hint: 'Gana la última que carga FiveM' }),
      kpi(c.with_script_recoil, 'Con recoil por script', { hint: 'Entradas activas en qbx_recoils' }),
      kpi(c.issues.error, 'Errores', { variant: c.issues.error ? 'err' : 'ok', hint: `${c.issues.warning} avisos · ${c.issues.info} informativos` }),
    ),
    h('div', { class: 'grid grid--side' },
      h('div', { class: 'stack' },
        card({ title: `Perfil activo: ${status.active_profile}`, iconName: 'star', className: 'card--accent',
          actions: h('a', { class: 'btn btn--sm', href: '#/generador' }, icon('generator'), 'Ir al Generador'), body: activeCard }),
        card({ title: 'Problemas principales', iconName: 'diagnostics',
          actions: h('a', { class: 'btn btn--sm btn--ghost', href: '#/diagnostico' }, 'Ver todo'), body: issuesCard }),
      ),
      h('div', { class: 'stack' },
        card({ title: 'Armas por categoría', iconName: 'layers', body: barList(
          Object.entries(c.categories).sort((a, b) => b[1] - a[1]).map(([label, value]) => ({ label, value }))) }),
        card({ title: 'Fuentes', iconName: 'folder', body: h('dl', { class: 'kv' },
          h('dt', {}, 'ox_inventory'), h('dd', {}, c.ox ? `${c.ox.weapons} armas · ${c.ox.components} componentes · ${c.ox.ammo} municiones` : 'no configurado'),
          h('dt', {}, 'qbx_recoils'), h('dd', {}, c.qbx_recoils ? `${c.qbx_recoils.active} activas · ${c.qbx_recoils.disabled} comentadas` : 'no encontrado'),
          h('dt', {}, 'Escaneo'), h('dd', {}, `${c.duration_ms} ms · ${date(c.built_at)}`),
          h('dt', {}, 'Último cambio'), h('dd', {}, status.last_transaction
            ? h('span', {}, `${date(status.last_transaction.created_at)} · ${status.last_transaction.profile} `, badge(status.last_transaction.status, status.last_transaction.status === 'applied' ? 'ok' : ''))
            : 'Ninguno desde el panel'),
        ) }),
        card({ title: 'Primeros pasos', iconName: 'docs', body: h('ol', { class: 'small', style: { margin: 0, paddingLeft: '18px', lineHeight: '1.9' } },
          h('li', {}, h('a', { href: '#/configuracion' }, 'Revisa las rutas'), ' (servidor, pack, ox_inventory).'),
          h('li', {}, h('a', { href: '#/armamento' }, 'Explora el armamento'), ' y sus problemas.'),
          h('li', {}, h('a', { href: '#/perfiles' }, 'Crea o abre un perfil'), '.'),
          h('li', {}, h('a', { href: '#/editor' }, 'Ajusta armas'), ' o usa el ', h('a', { href: '#/constructor' }, 'Constructor'), '.'),
          h('li', {}, h('a', { href: '#/simulador' }, 'Compara en el Simulador'), '.'),
          h('li', {}, h('a', { href: '#/generador' }, 'Genera, revisa y aplica'), ' con respaldo.'),
        ) }),
      ),
    ),
  );

  try {
    const preview = await api.post('/api/preview', { profile_id: status.active_profile });
    if (!isCurrent()) return;
    const s = preview.summary;
    const warnings = preview.issues.filter((i) => i.severity === 'warning' || i.severity === 'error');
    mount(activeCard, h('div', { class: 'stack' },
      s.files_changed
        ? callout('warn', [h('strong', {}, 'El pack no coincide con el perfil activo. '),
          `Aplicarlo cambiaría ${plural(s.files_changed, 'archivo', 'archivos')} y ${plural(s.weapons_changed, 'arma', 'armas')}.`])
        : callout('ok', [h('strong', {}, 'Sincronizado. '), 'El pack coincide exactamente con el perfil activo: aplicarlo no cambiaría ningún archivo.']),
      h('div', { class: 'grid grid--3' },
        h('div', { class: 'kpi' }, h('span', { class: 'kpi__value' }, s.weapon_blocks), h('span', { class: 'kpi__label' }, 'Bloques evaluados')),
        h('div', { class: 'kpi' }, h('span', { class: 'kpi__value' }, `${s.onetap_passed}/${s.onetap_total}`), h('span', { class: 'kpi__label' }, 'Auditoría one-tap correcta')),
        h('div', { class: 'kpi' }, h('span', { class: 'kpi__value' }, preview.idempotency?.idempotent === false ? 'No' : 'Sí'), h('span', { class: 'kpi__label' }, 'Resultado repetible')),
      ),
      warnings.length ? h('div', {}, h('div', { class: 'label', style: { marginBottom: '6px' } }, 'Avisos del perfil'), issueList(warnings.slice(0, 4))) : null,
    ));
  } catch (error) {
    if (isCurrent()) mount(activeCard, callout('err', error.message));
  }

  try {
    const diagnostics = await api.get('/api/diagnostics?runtime=0');
    if (!isCurrent()) return;
    const top = diagnostics.sections.flatMap((s) => s.issues).filter((i) => i.severity === 'error' || i.severity === 'warning').slice(0, 6);
    mount(issuesCard, issueList(top, { emptyText: 'No hay errores ni avisos.' }));
  } catch (error) {
    if (isCurrent()) { mount(issuesCard, callout('err', error.message)); toastError(error); }
  }
  void store;
}
