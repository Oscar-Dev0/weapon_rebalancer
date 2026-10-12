import { h, icon, mount } from '../core/dom.js';

export async function render({ root, params, setTitle }) {
  setTitle('Documentación', 'Guías integradas: también se abren sin el panel desde docs/index.html');
  const page = params.get('d') || '';
  const frame = h('iframe', { class: 'docs-frame', src: `/docs/${page ? `#${page}` : ''}`, title: 'Documentación de Weapon Rebalancer' });
  mount(root,
    h('div', { class: 'row' },
      ['inicio', 'primeros-pasos', 'editor', 'perfiles-oficiales', 'perfiles', 'balanceo', 'fivem', 'terminal', 'solucion-problemas', 'desarrollo'].map((slug) => h('a', {
        class: 'chip', href: `#/documentacion?d=${slug}`,
      }, slug.replaceAll('-', ' '))),
      h('a', { class: 'btn btn--sm btn--ghost', href: `/docs/${page ? `#${page}` : ''}`, target: '_blank', rel: 'noopener' }, icon('external'), 'Abrir en otra pestaña')),
    frame);
}
