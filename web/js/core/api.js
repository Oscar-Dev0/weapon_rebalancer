// Cliente de la API local. Todas las llamadas llevan la clave de la sesión, que el servidor rota
// (cabecera X-WR-Token-Next). Si la sesión caduca o se bloquea, la página se vacía.
const meta = document.querySelector('meta[name="wr-token"]');
let token = meta?.content || '';
if (meta) meta.remove();
let ended = false;

/** Sesión terminada: no queda nada del panel en pantalla ni en memoria visible. */
export function endSession(message = 'Sesión caducada. Abre un enlace nuevo (python3 wr.py token).') {
  if (ended) return;
  ended = true;
  token = '';
  const box = document.createElement('p');
  box.textContent = message;
  box.style.cssText = 'font-family:system-ui;padding:40px;margin:0';
  document.title = 'Acceso denegado';
  document.body.replaceChildren(box);
  if (window.location.hash) window.history.replaceState(null, '', '/');
}

export class ApiError extends Error {
  constructor(status, payload) {
    super(payload?.message || `Error ${status}`);
    this.status = status;
    this.hint = payload?.hint || '';
    this.details = payload?.details;
    this.code = payload?.error || 'error';
  }
}

async function request(method, path, body) {
  if (ended) throw new ApiError(401, { error: 'unauthorized', message: 'Sesión terminada.' });
  const options = { method, headers: { 'X-WR-Token': token } };
  if (body !== undefined) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(path, options);
  } catch (error) {
    throw new ApiError(0, { message: 'No hay conexión con el servidor local.', hint: '¿Sigue corriendo `python3 wr.py serve`?' });
  }
  const next = response.headers.get('X-WR-Token-Next');
  if (next) token = next;
  const text = await response.text();
  let payload = null;
  try { payload = text ? JSON.parse(text) : null; } catch { payload = { message: text }; }
  if ((response.status === 401 || response.status === 403) && ['unauthorized', 'locked'].includes(payload?.error)) {
    endSession(payload.error === 'locked' ? payload.message : undefined);
  }
  if (!response.ok) throw new ApiError(response.status, payload);
  return payload;
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, body = {}) => request('POST', path, body),
  put: (path, body = {}) => request('PUT', path, body),
  del: (path) => request('DELETE', path),
};
