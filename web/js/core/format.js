// Formato de números, unidades y etiquetas.

export function num(value, digits = 2) {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value !== 'number') return String(value);
  if (!Number.isFinite(value)) return '—';
  const fixed = Math.abs(value) >= 1000 ? value.toFixed(0) : Number(value.toFixed(digits)).toString();
  return fixed;
}

export function withUnit(value, unit, digits = 2) {
  const text = num(value, digits);
  if (text === '—' || !unit || unit === 'x' || unit === 'ratio') return unit === 'x' && text !== '—' ? `×${text}` : text;
  return `${text} ${unit}`;
}

export function pct(value, digits = 0) {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(digits)} %`;
}

export function seconds(value) {
  if (value === null || value === undefined) return '—';
  return value < 10 ? `${value.toFixed(2)} s` : `${value.toFixed(1)} s`;
}

export function rpm(value) {
  return value ? `${Math.round(value)} RPM` : '—';
}

export function date(value) {
  if (!value) return '—';
  const d = typeof value === 'number' ? new Date(value * 1000) : new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString('es', { dateStyle: 'short', timeStyle: 'short' });
}

export const SEVERITY = {
  error: { label: 'Error', badge: 'err' },
  warning: { label: 'Aviso', badge: 'warn' },
  info: { label: 'Info', badge: 'info' },
  ok: { label: 'Correcto', badge: 'ok' },
};

export function same(a, b) {
  if (typeof a === 'number' && typeof b === 'number') return Math.abs(a - b) <= 1e-6 * Math.max(1, Math.abs(a));
  return JSON.stringify(a) === JSON.stringify(b);
}

export function plural(count, one, many) {
  return `${count} ${count === 1 ? one : many}`;
}
