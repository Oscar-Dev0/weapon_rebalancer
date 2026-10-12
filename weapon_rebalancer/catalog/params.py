"""Registro de parámetros de armas con su método real de aplicación.

Cada entrada se apoya en un campo del catálogo `FIELDS` (un tag de CWeaponInfo que el
motor sabe leer y escribir). Aquí se añade lo que la interfaz necesita para no mostrar
controles ficticios: método de aplicación, si es editable, límites que el motor recorta,
unidades y una explicación en lenguaje sencillo.

Métodos de aplicación:
- ``meta``: el generador edita el tag en weapons.meta. Tiene efecto al reiniciar el
  recurso del arma (el cliente recarga el META al conectar).
- ``native``: se aplica en ejecución con natives desde un recurso Lua generado.
- ``resource``: lo controla otro recurso (ox_inventory). Se muestra, no se edita aquí.
- ``readonly``: identidad o referencias a otros archivos de datos. Solo lectura.
- ``unsupported``: no existe un mecanismo real en esta instalación. Se documenta.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ..engine.config import SAFE_BOUNDS
from ..meta.fields import FIELDS

SECTIONS: list[dict[str, str]] = [
    {'id': 'damage', 'label': 'Daño', 'icon': 'target',
     'summary': 'Daño base por impacto y multiplicadores por tipo de objetivo y zona del cuerpo.'},
    {'id': 'headshot', 'label': 'Cabeza', 'icon': 'crosshair',
     'summary': 'Multiplicadores y distancias del disparo a la cabeza. Requiere critical hits activos.'},
    {'id': 'range', 'label': 'Alcance y caída', 'icon': 'ruler',
     'summary': 'Distancia máxima y cómo baja el daño con la distancia.'},
    {'id': 'fire_rate', 'label': 'Cadencia y disparo', 'icon': 'zap',
     'summary': 'Tiempo entre disparos y velocidad de animación de disparo.'},
    {'id': 'recoil', 'label': 'Recoil y estabilidad', 'icon': 'activity',
     'summary': 'Error de puntería acumulado, recuperación y sacudida de cámara al disparar.'},
    {'id': 'accuracy', 'label': 'Precisión y dispersión', 'icon': 'aperture',
     'summary': 'Dispersión base, al apuntar y al disparar en movimiento.'},
    {'id': 'ammo', 'label': 'Munición y recarga', 'icon': 'package',
     'summary': 'Cargador y tiempos de recarga.'},
    {'id': 'projectile', 'label': 'Proyectil y perdigones', 'icon': 'share',
     'summary': 'Balas por disparo, apertura de perdigones y velocidad del proyectil.'},
    {'id': 'force', 'label': 'Fuerza de impacto', 'icon': 'wind',
     'summary': 'Empuje físico sobre peds y vehículos. No cambia el daño.'},
    {'id': 'aim', 'label': 'Asistencia de apuntado', 'icon': 'magnet',
     'summary': 'Radios de “bullet bending” (corrección de trayectoria cerca del objetivo).'},
    {'id': 'camera', 'label': 'Cámara y zoom', 'icon': 'camera',
     'summary': 'Campo de visión al apuntar y en mira telescópica.'},
    {'id': 'hud', 'label': 'Retícula', 'icon': 'circle',
     'summary': 'Tamaño de la retícula en pantalla.'},
    {'id': 'rumble', 'label': 'Vibración (mando)', 'icon': 'smartphone',
     'summary': 'Vibración del mando. Sin efecto con teclado y ratón.'},
    {'id': 'animation', 'label': 'Animación', 'icon': 'film',
     'summary': 'Pesos de respiración al apuntar y disparar.'},
    {'id': 'flags', 'label': 'Flags', 'icon': 'flag',
     'summary': 'WeaponFlags del arma (lista de palabras clave).'},
    {'id': 'identity', 'label': 'Identidad', 'icon': 'tag',
     'summary': 'Nombre, modelo, grupo y referencias. Solo lectura.'},
]

METHODS: dict[str, dict[str, str]] = {
    'meta': {'label': 'META', 'description': 'Se edita el tag en weapons.meta. Efecto al reiniciar el recurso del arma.'},
    'native': {'label': 'Native', 'description': 'Se aplica en ejecución con natives desde un recurso Lua generado.'},
    'resource': {'label': 'Recurso', 'description': 'Lo controla otro recurso (ox_inventory). Se edita allí.'},
    'readonly': {'label': 'Solo lectura', 'description': 'Identidad o referencia a otro archivo de datos.'},
    'unsupported': {'label': 'No compatible', 'description': 'No existe un mecanismo real en esta instalación.'},
}


@dataclass(frozen=True)
class ParamSpec:
    key: str
    tag: str
    label: str
    section: str
    method: str
    value_type: str            # number | integer | text | flags
    unit: str = ''
    description: str = ''
    notes: str = ''
    slider_min: float | None = None
    slider_max: float | None = None
    step: float | None = None
    hard_min: float | None = None   # el motor recorta por debajo
    hard_max: float | None = None   # el motor recorta por encima
    advanced: bool = False
    insertable: bool = False        # el motor puede crear el tag si falta
    doc: str = ''

    @property
    def editable(self) -> bool:
        return self.method == 'meta'

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data['editable'] = self.editable
        return data


# key: (label, section, value_type, unit, slider(min,max,step), descripción, notas, avanzado)
_P: dict[str, tuple[str, str, str, str, tuple[float, float, float] | None, str, str, bool]] = {
    # ---- Daño ---------------------------------------------------------------
    'damage': ('Daño base', 'damage', 'number', 'pts', (0, 200, 0.5),
               'Daño de cada impacto al torso antes de multiplicadores. En escopetas es el daño de cada perdigón.',
               'Contra jugadores se multiplica además por el modificador de red. Un jugador con 200 de vida muere al bajar de 100: tiene 100 puntos efectivos.', False),
    'network_player_damage_modifier': ('Multiplicador contra jugadores (red)', 'damage', 'number', 'x', (0, 3, 0.05),
               'Multiplica el daño que el arma hace a otros jugadores en partidas en red (FiveM).',
               'Si vale 0, el arma no hace daño a jugadores aunque el daño base sea alto.', False),
    'network_ped_damage_modifier': ('Multiplicador contra NPC (red)', 'damage', 'number', 'x', (0, 3, 0.05),
               'Multiplica el daño contra NPC en sesiones en red.', '', False),
    'hit_limbs': ('Multiplicador de extremidades', 'damage', 'number', 'x', (0, 2, 0.05),
               'Daño en brazos y piernas respecto al torso (1.0 = igual que el torso).', 'Versión local / NPC.', False),
    'network_hit_limbs': ('Multiplicador de extremidades (red)', 'damage', 'number', 'x', (0, 2, 0.05),
               'Igual que el anterior, aplicado a jugadores en red.', '', False),
    'lightly_armoured': ('Multiplicador contra blindaje ligero', 'damage', 'number', 'x', (0, 5, 0.05),
               'Daño contra peds marcados con protección ligera (por ejemplo, casco nativo).',
               'No es el chaleco/armadura del jugador. Valores muy altos (100) multiplicaban también los disparos al cuerpo en versiones viejas.', False),
    'vehicle_damage_modifier': ('Multiplicador contra vehículos', 'damage', 'number', 'x', (0, 3, 0.05),
               'Daño que el arma hace a la carrocería de los vehículos.', '', False),
    'penetration': ('Penetración', 'damage', 'number', 'ratio', (0, 2, 0.01),
               'Capacidad de la bala de atravesar materiales delgados.', 'No sustituye al multiplicador de cabeza.', True),
    'killshot_impulse_scale': ('Impulso al matar', 'damage', 'number', 'x', (0, 5, 0.1),
               'Escala del empuje físico aplicado al cuerpo en el disparo mortal.', 'Visual: no cambia el daño.', True),
    'knockdown_count': ('Impactos para derribar', 'damage', 'integer', 'impactos', (-1, 10, 1),
               'Número de impactos que hacen caer al objetivo (-1 = valor del juego).', 'Afecta sobre todo a NPC.', True),
    'damage_time': ('Tiempo de daño', 'damage', 'number', 's', (0, 5, 0.05),
               'Duración del daño continuo (armas de fuego/gas).', 'Solo armas con daño en el tiempo.', True),
    'damage_time_in_vehicle': ('Tiempo de daño en vehículo', 'damage', 'number', 's', (0, 5, 0.05),
               'Duración del daño continuo cuando el objetivo está en un vehículo.', '', True),
    'damage_time_in_vehicle_headshot': ('Tiempo de daño en vehículo (cabeza)', 'damage', 'number', 's', (0, 5, 0.05),
               'Igual que el anterior, para impactos en la cabeza.', '', True),

    # ---- Cabeza ---------------------------------------------------------------
    'headshot_player': ('Multiplicador de cabeza (local)', 'headshot', 'number', 'x', (0, 20, 0.1),
               'Multiplicador del daño en la cabeza calculado por el jugador que dispara.',
               'Contra otros jugadores manda el multiplicador de red.', False),
    'network_headshot': ('Multiplicador de cabeza contra jugadores (red)', 'headshot', 'number', 'x', (0, 20, 0.1),
               'Multiplicador del daño en la cabeza contra otros jugadores en FiveM.',
               'Solo funciona si el objetivo tiene critical hits activos (SetPedSuffersCriticalHits). Revisa Diagnóstico → Runtime.', False),
    'headshot_ai': ('Multiplicador de cabeza (NPC)', 'headshot', 'number', 'x', (0, 20, 0.1),
               'Multiplicador de cabeza en el cálculo contra NPC.', '', False),
    'min_headshot_player': ('Distancia mínima de cabeza', 'headshot', 'number', 'm', (0, 50, 0.5),
               'Por debajo de esta distancia no se aplica el multiplicador de cabeza.', '', True),
    'max_headshot_player': ('Distancia máxima de cabeza', 'headshot', 'number', 'm', (0, 600, 1),
               'Más allá de esta distancia el disparo a la cabeza cuenta como torso.', '', False),
    'min_headshot_ai': ('Distancia mínima de cabeza (NPC)', 'headshot', 'number', 'm', (0, 50, 0.5), '', '', True),
    'max_headshot_ai': ('Distancia máxima de cabeza (NPC)', 'headshot', 'number', 'm', (0, 600, 1), '', '', True),
    'recoil_accuracy_to_allow_headshot_player': ('Precisión mínima para cabeza', 'headshot', 'number', 'ratio', (0, 2, 0.01),
               'Si el error de recoil acumulado supera este valor, el disparo no cuenta como headshot.', '', True),
    'recoil_accuracy_to_allow_headshot_ai': ('Precisión mínima para cabeza (NPC)', 'headshot', 'number', 'ratio', (0, 2, 0.01), '', '', True),

    # ---- Alcance ---------------------------------------------------------------
    'weapon_range': ('Alcance máximo', 'range', 'number', 'm', (1, 1000, 1),
               'Distancia máxima a la que el arma registra impactos.', '', False),
    'falloff_min': ('Inicio de caída de daño', 'range', 'number', 'm', (0, 600, 1),
               'Hasta esta distancia el arma hace el 100 % del daño.', 'Debe ser menor que el final de caída.', False),
    'falloff_max': ('Final de caída de daño', 'range', 'number', 'm', (0, 1000, 1),
               'A partir de esta distancia el daño queda en el porcentaje mínimo.', '', False),
    'falloff_modifier': ('Daño mínimo por distancia', 'range', 'number', 'ratio', (0, 1, 0.01),
               'Fracción del daño que queda al final de la caída (0.5 = 50 %).', '1.0 desactiva la caída de daño.', False),
    'lock_on_range': ('Alcance de fijado', 'range', 'number', 'm', (0, 500, 1),
               'Distancia a la que se puede fijar objetivo (mando / asistencia).', '', True),
    'ai_sound_range': ('Alcance del sonido para NPC', 'range', 'number', 'm', (0, 500, 1),
               'Distancia a la que los NPC “oyen” el disparo.', 'Solo IA.', True),
    'ai_potential_blast_event_range': ('Alcance de evento de explosión (NPC)', 'range', 'number', 'm', (0, 500, 1), '', 'Solo IA.', True),

    # ---- Cadencia ---------------------------------------------------------------
    'time_between_shots': ('Tiempo entre disparos', 'fire_rate', 'number', 's', (0.03, 2.5, 0.005),
               'Segundos mínimos entre dos disparos. Cadencia máxima = 60 / valor (RPM).',
               'En armas semiautomáticas es el límite si se hace clic muy rápido. El motor recorta entre 0.030 y 2.5.', False),
    'anim_fire_rate_modifier': ('Velocidad de animación de disparo', 'fire_rate', 'number', 'x', (0.05, 3, 0.05),
               'Acelera o frena la animación de disparo. En armas cuya cadencia depende de la animación también cambia las RPM.', '', False),
    'cached_fire_window': ('Ventana de disparo en cola', 'fire_rate', 'number', 's', (0, 0.5, 0.005),
               'Margen en el que un clic temprano se guarda y dispara al terminar el intervalo.', '', True),
    'spin_up_time': ('Tiempo de arranque (minigun)', 'fire_rate', 'number', 's', (0, 5, 0.05), 'Solo armas con cañón giratorio.', '', True),
    'spin_time': ('Tiempo de giro', 'fire_rate', 'number', 's', (0, 5, 0.05), '', 'Solo armas con cañón giratorio.', True),
    'spin_down_time': ('Tiempo de frenado', 'fire_rate', 'number', 's', (0, 5, 0.05), '', 'Solo armas con cañón giratorio.', True),
    'alternate_wait_time': ('Espera alternada', 'fire_rate', 'number', 's', (-1, 2, 0.01),
               'Espera entre disparos de cañones alternos (-1 = no aplica).', '', True),

    # ---- Recoil ---------------------------------------------------------------
    'recoil_accuracy_max': ('Error máximo por recoil', 'recoil', 'number', 'ratio', (0, 3, 0.01),
               'Cuánto puede crecer el error de puntería al disparar seguido. Más alto = más dispersión en ráfagas.', '', False),
    'recoil_error_time': ('Error añadido por disparo', 'recoil', 'number', 's', (0, 1, 0.005),
               'Cuánto error suma cada disparo. Más alto = la puntería se degrada antes.', '', False),
    'recoil_recovery_rate': ('Recuperación del recoil', 'recoil', 'number', 'x', (0, 10, 0.05),
               'Velocidad a la que la puntería vuelve a su precisión base entre disparos.', 'Más alto = recupera antes.', False),
    'recoil_shake_amplitude': ('Sacudida de cámara', 'recoil', 'number', 'x', (0, 3, 0.01),
               'Intensidad del temblor de cámara en cada disparo (recoil visual).',
               'Es la parte visible del recoil en el META. El retroceso vertical de cámara en este servidor lo aplica qbx_recoils (sección Recurso).', False),
    'explosion_shake_amplitude': ('Sacudida por explosión', 'recoil', 'number', 'x', (0, 3, 0.01), '', 'Armas explosivas.', True),
    'min_time_between_recoil_shakes': ('Tiempo mínimo entre sacudidas', 'recoil', 'integer', 'ms', (0, 1000, 10),
               'Milisegundos mínimos entre dos sacudidas de cámara.', '', True),
    'ik_recoil_displacement': ('Retroceso visual del arma', 'recoil', 'number', 'm', (0, 0.2, 0.001),
               'Desplazamiento visual del arma en las manos al disparar (IK).', 'Solo animación: no cambia la puntería.', True),
    'ik_recoil_displacement_scope': ('Retroceso visual con mira', 'recoil', 'number', 'm', (0, 0.2, 0.001), '', 'Solo animación.', True),
    'ik_recoil_scale_backward': ('Escala de retroceso hacia atrás', 'recoil', 'number', 'x', (0, 3, 0.05), '', 'Solo animación.', True),
    'ik_recoil_scale_vertical': ('Escala de retroceso vertical (visual)', 'recoil', 'number', 'x', (0, 3, 0.05),
               'Levantamiento visual del arma en la animación.', 'Solo animación: no mueve la cámara ni la mira.', True),

    # ---- Precisión ---------------------------------------------------------------
    'accuracy_spread': ('Dispersión base', 'accuracy', 'number', '°', (0, 5, 0.01),
               'Apertura del cono de disparo. 0 = láser.', 'En escopetas conviene mantener dispersión para los perdigones.', False),
    'accurate_mode_accuracy_modifier': ('Modificador al apuntar fino', 'accuracy', 'number', 'x', (0, 3, 0.01),
               'Multiplica la dispersión en modo de apuntado preciso. Menor = más preciso.', '', False),
    'run_and_gun_accuracy_modifier': ('Modificador en movimiento', 'accuracy', 'number', 'x', (0, 5, 0.01),
               'Multiplica la dispersión al disparar corriendo sin apuntar.', '', False),
    'run_and_gun_accuracy_min_override': ('Mínimo en movimiento', 'accuracy', 'number', 'ratio', (-1, 2, 0.01),
               'Precisión mínima forzada al disparar corriendo (-1 = sin forzar).', '', True),

    # ---- Munición ---------------------------------------------------------------
    'clip_size': ('Tamaño del cargador', 'ammo', 'integer', 'balas', (1, 250, 1),
               'Balas por cargador. Un componente de cargador ampliado puede reemplazarlo.', '', False),
    'reload_time_mp': ('Tiempo de recarga (multijugador)', 'ammo', 'number', 's', (0.05, 20, 0.05),
               'Duración de la recarga en sesiones en red.', 'Si el arma tiene la flag AnimReload, la animación manda (ver velocidad de recarga).', False),
    'reload_time_sp': ('Tiempo de recarga (un jugador)', 'ammo', 'number', 's', (0.05, 20, 0.05),
               'Duración de la recarga en modo historia.', 'En FiveM manda la versión multijugador.', True),
    'vehicle_reload_time': ('Recarga en vehículo', 'ammo', 'number', 's', (0, 20, 0.05), 'Duración de la recarga dentro de un vehículo.', '', True),
    'anim_reload_rate': ('Velocidad de recarga (animación)', 'ammo', 'number', 'x', (0.05, 3, 0.05),
               'Acelera o frena la animación de recarga. Más alto = recarga más rápida.', '', False),
    'bullets_per_anim_loop': ('Balas por ciclo de animación', 'ammo', 'integer', 'balas', (1, 10, 1),
               'Balas que salen por cada ciclo de la animación de disparo.', '', True),
    'ammo_diminishing_rate': ('Consumo de munición', 'ammo', 'integer', '', (0, 10, 1), 'Ritmo de consumo de munición de armas especiales.', '', True),

    # ---- Proyectil ---------------------------------------------------------------
    'bullets_in_batch': ('Perdigones por disparo', 'projectile', 'integer', 'balas', (1, 20, 1),
               'Balas que salen en cada disparo (escopetas).', 'El daño base se aplica a cada perdigón.', False),
    'batch_spread': ('Apertura de perdigones', 'projectile', 'number', 'ratio', (0, 1, 0.005),
               'Separación entre perdigones de un mismo disparo.', '', False),
    'speed': ('Velocidad del proyectil', 'projectile', 'number', 'm/s', (0, 5000, 10), 'Velocidad de proyectiles físicos.', 'Las balas instantáneas (INSTANT_HIT) no la usan.', True),
    'bullet_direction_offset_degrees': ('Desvío de dirección', 'projectile', 'number', '°', (0, 10, 0.1), '', '', True),
    'bullet_direction_pitch_offset': ('Desvío vertical', 'projectile', 'number', '°', (-10, 10, 0.1), '', '', True),
    'bullet_direction_pitch_homing_offset': ('Desvío vertical guiado', 'projectile', 'number', '°', (-10, 10, 0.1), '', '', True),
    'vertical_launch_adjustment': ('Ajuste de lanzamiento vertical', 'projectile', 'number', '', (-5, 5, 0.05), '', 'Armas arrojadizas.', True),
    'drop_forward_velocity': ('Velocidad al soltar', 'projectile', 'number', 'm/s', (0, 10, 0.05), '', 'Armas arrojadizas.', True),

    # ---- Fuerza ---------------------------------------------------------------
    'force': ('Fuerza', 'force', 'number', '', (0, 500, 1), 'Empuje general del impacto.', 'Visual/físico: no cambia el daño.', True),
    'force_hit_ped': ('Fuerza sobre peds', 'force', 'number', '', (0, 500, 1), 'Empuje sobre personas.', '', True),
    'force_hit_vehicle': ('Fuerza sobre vehículos', 'force', 'number', '', (0, 5000, 10), '', '', True),
    'force_hit_flying_heli': ('Fuerza sobre helicópteros', 'force', 'number', '', (0, 5000, 10), '', '', True),
    'force_max_strength_mult': ('Multiplicador de fuerza máxima', 'force', 'number', 'x', (0, 5, 0.05), '', '', True),
    'force_falloff_range_start': ('Inicio de caída de fuerza', 'force', 'number', 'm', (0, 500, 1), '', '', True),
    'force_falloff_range_end': ('Final de caída de fuerza', 'force', 'number', 'm', (0, 500, 1), '', '', True),
    'force_falloff_min': ('Fuerza mínima por distancia', 'force', 'number', 'ratio', (0, 1, 0.01), '', '', True),
    'projectile_force': ('Fuerza del proyectil', 'force', 'number', '', (0, 5000, 10), '', '', True),
    'frag_impulse': ('Impulso sobre objetos', 'force', 'number', '', (0, 5000, 10), 'Empuje sobre objetos rompibles.', '', True),

    # ---- Asistencia ---------------------------------------------------------------
    'bullet_bending_near_radius': ('Corrección cercana', 'aim', 'number', 'm', (0, 2, 0.01),
               'Radio en el que la bala se “curva” hacia el objetivo a corta distancia.', 'Ayuda de apuntado del juego; afecta a todos los jugadores con esa arma.', True),
    'bullet_bending_far_radius': ('Corrección lejana', 'aim', 'number', 'm', (0, 2, 0.01), '', '', True),
    'bullet_bending_zoomed_radius': ('Corrección con zoom', 'aim', 'number', 'm', (0, 2, 0.01), '', '', True),
    'fp_bullet_bending_near_radius': ('Corrección cercana (1.ª persona)', 'aim', 'number', 'm', (0, 2, 0.01), '', '', True),
    'fp_bullet_bending_far_radius': ('Corrección lejana (1.ª persona)', 'aim', 'number', 'm', (0, 2, 0.01), '', '', True),
    'fp_bullet_bending_zoomed_radius': ('Corrección con zoom (1.ª persona)', 'aim', 'number', 'm', (0, 2, 0.01), '', '', True),

    # ---- Cámara ---------------------------------------------------------------
    'camera_fov': ('FOV de cámara', 'camera', 'number', '°', (1, 120, 0.5), '', '', True),
    'aim_fov': ('FOV al apuntar', 'camera', 'number', '°', (1, 120, 0.5), 'Campo de visión al apuntar en tercera persona.', '', True),
    'first_person_aim_fov_min': ('FOV mínimo al apuntar (1.ª persona)', 'camera', 'number', '°', (1, 120, 0.5), '', '', True),
    'first_person_aim_fov_max': ('FOV máximo al apuntar (1.ª persona)', 'camera', 'number', '°', (1, 120, 0.5), '', '', True),
    'first_person_scope_fov': ('FOV de mira (1.ª persona)', 'camera', 'number', '°', (1, 120, 0.5), '', '', True),
    'first_person_scope_attachment_fov': ('FOV de mira acoplada', 'camera', 'number', '°', (0, 120, 0.5), '', '', True),
    'zoom_factor_accurate_mode': ('Zoom al apuntar fino', 'camera', 'number', 'x', (1, 10, 0.05), '', '', True),

    # ---- Retícula ---------------------------------------------------------------
    'reticule_min_size_standing': ('Retícula mínima (de pie)', 'hud', 'number', 'x', (0, 2, 0.01), '', '', True),
    'reticule_min_size_crouched': ('Retícula mínima (agachado)', 'hud', 'number', 'x', (0, 2, 0.01), '', '', True),
    'reticule_scale': ('Escala de retícula', 'hud', 'number', 'x', (0, 2, 0.01), '', '', True),

    # ---- Vibración ---------------------------------------------------------------
    **{key: (label, 'rumble', 'number' if 'intensity' in key or 'trigger' in key else 'integer', '', (0, 1000 if 'duration' in key else 1, 1 if 'duration' in key else 0.01), '', 'Solo mando.', True)
       for key, label in {
           'initial_rumble_duration': 'Vibración inicial (duración)',
           'initial_rumble_intensity': 'Vibración inicial (intensidad)',
           'initial_rumble_trigger': 'Vibración inicial (gatillo)',
           'rumble_duration': 'Vibración (duración)',
           'rumble_intensity': 'Vibración (intensidad)',
           'rumble_trigger': 'Vibración (gatillo)',
           'rumble_damage_intensity': 'Vibración al recibir daño',
           'initial_rumble_duration_fps': 'Vibración inicial 1.ª persona (duración)',
           'initial_rumble_intensity_fps': 'Vibración inicial 1.ª persona (intensidad)',
           'rumble_duration_fps': 'Vibración 1.ª persona (duración)',
           'rumble_intensity_fps': 'Vibración 1.ª persona (intensidad)',
       }.items()},

    # ---- Animación ---------------------------------------------------------------
    'aiming_breathing_weight': ('Respiración al apuntar', 'animation', 'number', 'x', (0, 2, 0.05), 'Balanceo visual del arma al apuntar.', '', True),
    'firing_breathing_weight': ('Respiración al disparar', 'animation', 'number', 'x', (0, 2, 0.05), '', '', True),
}

# Campos que existen en el META pero no deben editarse desde el panel.
_READONLY: dict[str, tuple[str, str, str]] = {
    'name': ('Nombre interno', 'identity', 'Identificador WEAPON_* que usan inventario y natives (hash = joaat del nombre).'),
    'model': ('Modelo', 'identity', 'Modelo 3D del arma (archivo .ydr en stream/).'),
    'audio': ('Audio', 'identity', 'Entrada de audio del arma.'),
    'slot': ('Slot', 'identity', 'Slot interno de la rueda de armas.'),
    'damage_type': ('Tipo de daño', 'identity', 'BULLET, MELEE, EXPLOSIVE... Cambiarlo altera cómo el juego procesa el impacto.'),
    'fire_type': ('Tipo de disparo', 'identity', 'INSTANT_HIT, PROJECTILE, MELEE... Determina si se usa Damage o el AmmoInfo.'),
    'wheel_slot': ('Posición en la rueda', 'identity', ''),
    'group': ('Grupo', 'identity', 'Categoría del arma (GROUP_PISTOL, GROUP_RIFLE...). Los perfiles la usan para reglas por categoría.'),
    'ammo_info': ('Tipo de munición (META)', 'identity', 'Referencia a la munición del juego; ox_inventory usa su propio ammoname.'),
    'aiming_info': ('Aiming info', 'identity', 'Referencia a la configuración de apuntado.'),
    'pickup_hash': ('Pickup', 'identity', ''),
    'mp_pickup_hash': ('Pickup MP', 'identity', ''),
    'human_name_hash': ('Nombre visible (GXT)', 'identity', ''),
    'stat_name': ('Estadística', 'identity', ''),
    'firing_pattern': ('Patrón de disparo', 'fire_rate', 'Patrón de ráfagas de la IA. No controla el disparo del jugador.'),
    'nm_shot_tuning_set': ('Reacción física (NM)', 'animation', 'Reacción de Euphoria al recibir el disparo.'),
    'movement_mode_conditional_idle': ('Idle de movimiento', 'animation', ''),
    'default_camera_hash': ('Cámara por defecto', 'camera', 'Nombre de cámara definido en otro archivo de datos.'),
    'aim_camera_hash': ('Cámara al apuntar', 'camera', ''),
    'fire_camera_hash': ('Cámara al disparar', 'camera', ''),
    'cover_camera_hash': ('Cámara en cobertura', 'camera', ''),
    'cover_ready_camera_hash': ('Cámara lista en cobertura', 'camera', ''),
    'run_and_gun_camera_hash': ('Cámara corriendo', 'camera', ''),
    'recoil_shake_hash': ('Tipo de sacudida', 'recoil', 'Nombre de la sacudida de cámara; la intensidad se ajusta con “Sacudida de cámara”.'),
    'recoil_shake_hash_fp': ('Tipo de sacudida (1.ª persona)', 'recoil', ''),
    'accuracy_offset_shake_hash': ('Sacudida de precisión', 'recoil', ''),
    'reticule_style_hash': ('Estilo de retícula', 'hud', ''),
    'first_person_reticule_style_hash': ('Estilo de retícula (1.ª persona)', 'hud', ''),
}


def _build() -> dict[str, ParamSpec]:
    registry: dict[str, ParamSpec] = {}
    for key, meta_field in FIELDS.items():
        bounds = SAFE_BOUNDS.get(key)
        hard_min, hard_max = (bounds if bounds else (None, None))
        if key == 'weapon_flags':
            registry[key] = ParamSpec(
                key=key, tag=meta_field.xml_tag, label='WeaponFlags', section='flags', method='meta',
                value_type='flags', description='Lista de flags del arma. Se editan agregando o quitando flags concretas; las demás se conservan.',
                notes='Algunas flags (Automatic, OnlyFireOneShotPerTriggerPress) cambian el comportamiento del gatillo: pruébalas en el juego.',
                insertable=True, doc='editor#flags',
            )
            continue
        if key in _READONLY:
            label, section, description = _READONLY[key]
            registry[key] = ParamSpec(
                key=key, tag=meta_field.xml_tag, label=label, section=section, method='readonly',
                value_type='text', description=description, advanced=section != 'identity',
                doc=f'editor#{section}',
            )
            continue
        if key not in _P:
            raise RuntimeError(f'Parámetro sin documentar en el registro: {key}')
        label, section, value_type, unit, slider, description, notes, advanced = _P[key]
        registry[key] = ParamSpec(
            key=key, tag=meta_field.xml_tag, label=label, section=section, method='meta',
            value_type=value_type, unit=unit, description=description, notes=notes,
            slider_min=slider[0] if slider else None, slider_max=slider[1] if slider else None,
            step=slider[2] if slider else None, hard_min=hard_min, hard_max=hard_max,
            advanced=advanced, insertable=meta_field.safe_insert, doc=f'editor#{section}',
        )
    return registry


PARAMS: dict[str, ParamSpec] = _build()

# Datos que vienen de ox_inventory: se muestran, pero se editan en ese recurso.
RESOURCE_PARAMS: list[dict[str, str]] = [
    {'key': 'ox.label', 'label': 'Etiqueta', 'method': 'resource', 'description': 'Nombre visible en el inventario (data/weapons.lua).'},
    {'key': 'ox.weight', 'label': 'Peso', 'method': 'resource', 'description': 'Peso en gramos dentro del inventario.'},
    {'key': 'ox.durability', 'label': 'Desgaste por disparo', 'method': 'resource', 'description': 'Durabilidad que pierde el arma con cada disparo (ox_inventory).'},
    {'key': 'ox.ammoname', 'label': 'Munición del inventario', 'method': 'resource', 'description': 'Ítem de munición que consume en ox_inventory.'},
    {'key': 'qbx.recoil', 'label': 'Recoil vertical de cámara (qbx_recoils)', 'method': 'resource', 'editable': True,
     'description': 'qbx_smallresources/qbx_recoils sube la cámara al disparar según un valor por arma ([hash] = valor). '
                    'Se configura en el perfil (sección resources.qbx_recoils) y lo escribe el Generador con respaldo. '
                    'Las armas sin entrada no tienen recoil vertical por script.'},
]

# Parámetros que se aplican en ejecución desde los recursos generados.
NATIVE_PARAMS: list[dict[str, str]] = [
    {'key': 'runtime.critical_hits', 'label': 'Critical hits', 'method': 'native',
     'description': 'SetPedSuffersCriticalHits(ped, true). Sin esto los multiplicadores de cabeza no se aplican. Lo instala os_headshot_guard.'},
    {'key': 'runtime.damage_guard', 'label': 'Guard de daño esperado', 'method': 'native',
     'description': 'SetWeaponDamageModifier para forzar el daño del META si otro recurso lo altera. Lo genera el Generador (opcional).'},
]

# Lo que se suele pedir y no tiene un mecanismo real: se documenta en lugar de fingir.
UNSUPPORTED_PARAMS: list[dict[str, str]] = [
    {'key': 'recoil.camera_horizontal', 'label': 'Recoil de cámara horizontal',
     'method': 'unsupported',
     'description': 'CWeaponInfo no tiene recoil de cámara por ejes y qbx_recoils solo mueve la cámara en vertical. '
                    'Un recoil horizontal necesitaría un script cliente nuevo (SetGameplayCamRelativeHeading); no está implementado.'},
    {'key': 'fire.burst_player', 'label': 'Modo ráfaga del jugador', 'method': 'unsupported',
     'description': 'FiringPattern solo controla a la IA. El jugador no tiene un modo ráfaga configurable por META.'},
    {'key': 'damage.material', 'label': 'Daño por material', 'method': 'unsupported',
     'description': 'No hay multiplicadores de daño por material en CWeaponInfo; solo Penetration.'},
    {'key': 'damage.per_bone', 'label': 'Daño por hueso concreto', 'method': 'unsupported',
     'description': 'El META solo distingue cabeza, extremidades y resto del cuerpo.'},
]


def registry_payload() -> dict[str, Any]:
    from ..profile_store.schema import MODULE_PRESET_KEYS, MODULE_VALUES, effective_modules, module_for_field

    params = []
    for spec in PARAMS.values():
        data = spec.to_dict()
        data['modules'] = module_for_field(spec.key)
        data['preset_modules'] = [m for m, keys in MODULE_PRESET_KEYS.items() if spec.key in keys]
        params.append(data)
    from ..meta.weapon_flags import KNOWN_WEAPON_FLAGS

    return {
        'known_flags': list(KNOWN_WEAPON_FLAGS),
        'module_values': MODULE_VALUES,
        'module_defaults': effective_modules({}),
        'sections': SECTIONS,
        'methods': METHODS,
        'params': params,
        'resource': RESOURCE_PARAMS,
        'native': NATIVE_PARAMS,
        'unsupported': UNSUPPORTED_PARAMS,
    }


def editable_keys() -> set[str]:
    return {key for key, spec in PARAMS.items() if spec.editable and spec.value_type in {'number', 'integer'}}
