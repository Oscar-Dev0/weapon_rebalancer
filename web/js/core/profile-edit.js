// Lectura del perfil en edición. Las MODIFICACIONES no se hacen aquí: pasan por el servidor
// (core/ops.js → POST /api/profiles/ops), la misma lógica que usa la terminal (profile_store/edit.py).
import { store } from './store.js';

const SCOPE_META = new Set(['fields', 'meta', 'weapon_flags', 'headshot', '_comment', '_documentation']);

function container(profile, scope) {
  if (scope.type === 'defaults') return profile.defaults;
  const key = scope.type === 'group' ? 'groups' : 'weapons';
  return profile[key]?.[scope.name];
}

export function scopeLabel(scope) {
  if (scope.type === 'defaults') return 'Global (todas las armas procesadas)';
  if (scope.type === 'group') return `Categoría ${scope.name}`;
  return scope.name;
}

export function getField(profile, scope, key) {
  const target = container(profile, scope);
  if (!target) return undefined;
  if (target.fields && key in target.fields) return target.fields[key] ?? undefined;
  if (!SCOPE_META.has(key) && key in target) return target[key] ?? undefined;
  return undefined;
}

/** true si el perfil escribe null en ese campo: deja de usar lo heredado del perfil base. */
export function isNulled(profile, scope, key) {
  const fields = container(profile, scope)?.fields;
  return !!fields && key in fields && fields[key] === null;
}

/** Valor que el campo hereda del perfil base (undefined si no hereda nada). */
export function inheritedField(scope, key) {
  return store.draft?.base ? getField(store.draft.base, scope, key) : undefined;
}

/** Módulo efectivo: el del borrador, el heredado de la base o el valor por defecto del motor. */
export function effectiveModule(profile, module) {
  return profile.modules?.[module] ?? store.draft?.resolved?.modules?.[module] ?? store.registry?.module_defaults?.[module];
}

export function getHeadshot(profile, scope) {
  if (scope.type === 'defaults') return profile.headshot || {};
  return container(profile, scope)?.headshot || {};
}

export function getFlags(profile, scope) {
  const target = scope.type === 'defaults' ? profile : container(profile, scope);
  const flags = target?.weapon_flags || {};
  return { add: [...(flags.add || [])], remove: [...(flags.remove || [])] };
}

export function getMultiplier(profile, weapon, key) {
  return profile.weapon_field_multipliers?.[weapon]?.[key] ?? undefined;
}

export function inList(profile, list, weapon) {
  return (profile[list] || []).map((w) => String(w).toUpperCase()).includes(weapon);
}

export function getQbxRecoil(profile, weapon) {
  const map = profile.resources?.qbx_recoils;
  if (!map || !(weapon in map)) return undefined;
  return map[weapon];
}

export function countOverrides(profile, weapon) {
  const target = container(profile, { type: 'weapon', name: weapon });
  let count = 0;
  if (target) {
    count += Object.keys(target.fields || {}).length;
    count += Object.keys(target).filter((k) => !SCOPE_META.has(k)).length;
    if (target.headshot) count += 1;
    if (target.weapon_flags) count += 1;
  }
  if (profile.weapon_field_multipliers?.[weapon]) count += Object.keys(profile.weapon_field_multipliers[weapon]).length;
  if (getQbxRecoil(profile, weapon) !== undefined) count += 1;
  return count;
}

/** Ámbito en el formato que entiende el servidor: WEAPON_X, GROUP_X o global. */
export function scopeOp(scope) {
  return scope.type === 'defaults' ? 'global' : scope.name;
}
