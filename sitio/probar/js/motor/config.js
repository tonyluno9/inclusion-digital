// Los mismos valores que app/config.py (la app de escritorio). Si cambian allá, cámbialos aquí:
// el traductor solo reconoce bien si las señas se cortan y preparan igual que al entrenar.
export const FEATURE_VERSION = 4;
export const SEQUENCE_LENGTH = 30;

export const SEGMENT_START_FRAMES = 3;
export const SEGMENT_END_FRAMES = 8;
export const SEGMENT_MIN_FRAMES = 10;
export const SEGMENT_MAX_FRAMES = 120;
export const SEGMENT_CONTEXT_FRAMES = 15;
export const RESTING_HAND_MARGIN = 1.5;

export const AVATAR_PREROLL_FRAMES = 15;
export const HANDS_MODES = ['dos', 'derecha', 'izquierda'];
export const MIN_HAND_COVERAGE = 0.5;

export const FRAMING_WINDOW = 30;
export const FRAMING_MIN_SEEN = 0.3;

export const MIN_CONFIDENCE = 0.6;
export const SILENCE_SECONDS = 2.5;
export const SUBTITLE_HISTORY = 5;

// Cámara: lo mismo que pide la app (CAMERA_WIDTH × CAMERA_HEIGHT)
export const CAMERA_WIDTH = 1280;
export const CAMERA_HEIGHT = 720;
export const POSE_MODEL = 'full';      // ?pose=lite en la dirección usa el modelo rápido

// Oración natural con Claude: en una página estática no se puede sin exponer una clave, así que
// las palabras se unen tal cual (como la app sin ANTHROPIC_API_KEY). Si algún día hay un
// servidor propio (proxy) que guarde la clave, pon aquí su dirección: recibirá
// POST {"palabras": [...]} y deberá responder {"oracion": "..."}. Nunca pongas una clave aquí.
export const URL_ORACION = null;

export const DISPLAY_NAMES = { adios: 'adiós', 'buenos dias': 'buenos días', denada: 'de nada', perdon: 'perdón' };
export const displayName = (label) => DISPLAY_NAMES[label] ?? label;
