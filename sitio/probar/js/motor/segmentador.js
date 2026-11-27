// Port de app/modules/segmenter.py: corta el flujo de la cámara en señas (manos arriba -> abajo).
import {
  HANDS_SIZE, RAW_FRAME_SIZE, bodyReferencePose, dropRestingHands, handsPresent, poseValid, prepareSequence,
} from './landmarks.js';

export class SignSegmenter {
  constructor(length, startFrames, endFrames, minFrames, maxFrames, contextFrames = 15, restingMargin = 1.5) {
    Object.assign(this, { length, startFrames, endFrames, minFrames, maxFrames, contextFrames, restingMargin });
    this._idle = [];
    this._body = null;
    this.reset();
  }

  reset() {
    this.frames = [];
    this.active = false;
    this._absent = 0;
    this._waitRelease = false;   // tras un corte forzado, esperar a que bajen las manos
    this.lastDiscarded = false;  // la última seña terminó pero era muy corta
  }

  get captured() { return this.active ? this.frames.length : 0; }

  get bodyVisible() { return this._body !== null; }

  _reference(raw) {
    if (this._body !== null) return this._body;
    if (poseValid(raw)) return Float32Array.from(raw.subarray ? raw.subarray(HANDS_SIZE, RAW_FRAME_SIZE) : raw.slice(HANDS_SIZE, RAW_FRAME_SIZE));
    return null;
  }

  /** Agrega un frame. Cuando termina una seña devuelve la secuencia preparada; si no, null. */
  update(raw) {
    const frame = dropRestingHands(raw, this._reference(raw), this.restingMargin);
    const present = handsPresent(frame);

    if (!present && poseValid(frame)) {
      this._idle.push(frame);
      if (this._idle.length > this.contextFrames) this._idle.shift();
      this._body = bodyReferencePose(this._idle);
    }

    if (this._waitRelease) {
      if (!present) this._waitRelease = false;
      return null;
    }

    if (!this.active) {
      this.frames = present ? [...this.frames, frame] : [];
      if (this.frames.length >= this.startFrames) this.active = true;
      return null;
    }

    this.frames.push(frame);
    this._absent = present ? 0 : this._absent + 1;
    const forzado = this.frames.length >= this.maxFrames && present;
    if (this._absent >= this.endFrames || forzado) {
      const frames = this.frames;
      this.reset();
      this._waitRelease = forzado;
      const out = prepareSequence(frames, this.length, this.minFrames, this._body);
      this.lastDiscarded = out === null;
      return out;
    }
    return null;
  }
}
