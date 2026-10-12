// Cliente de la API local. Todas las llamadas llevan el token de sesión.
const token = document.querySelector('meta[name="wr-token"]')?.content || '';

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
  const text = await response.text();
  let payload = null;
  try { payload = text ? JSON.parse(text) : null; } catch { payload = { message: text }; }
  if (!response.ok) throw new ApiError(response.status, payload);
  return payload;
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, body = {}) => request('POST', path, body),
  put: (path, body = {}) => request('PUT', path, body),
  del: (path) => request('DELETE', path),
};
