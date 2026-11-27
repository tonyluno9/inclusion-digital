// Puntos de seguimiento que flotan sobre la portada y se conectan cerca del cursor,
// como los puntos que MediaPipe encuentra en las manos.
const COLORES = ['46,196,182', '58,134,200', '58,134,200', '124,92,255', '255,200,87'];

export function iniciarHeroe(canvas, quieto) {
  if (!canvas) return;
  const c = canvas.getContext('2d');
  let w = 0; let h = 0; let dpr = 1; let puntos = [];
  const cursor = { x: -1e4, y: -1e4, activo: false };
  let visible = true; let corriendo = false;

  function medir() {
    const r = canvas.getBoundingClientRect();
    dpr = Math.min(devicePixelRatio || 1, 2);
    w = r.width; h = r.height;
    canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
    const n = Math.round(Math.min(90, (w * h) / 16000));
    puntos = Array.from({ length: n }, () => {
      // Más densos a la derecha, donde está la ilustración
      const x = w * (0.35 + 0.65 * Math.sqrt(Math.random()));
      return {
        x, y: Math.random() * h, vx: (Math.random() - 0.5) * 0.12, vy: (Math.random() - 0.5) * 0.12,
        r: 0.8 + Math.random() * 1.6, col: COLORES[(Math.random() * COLORES.length) | 0], fase: Math.random() * 6.28,
      };
    });
    if (quieto) dibujar(0);
  }

  function dibujar(t) {
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, w, h);
    const radioCursor = 170;
    for (const p of puntos) {
      if (!quieto) {
        p.x += p.vx; p.y += p.vy;
        if (p.x < w * 0.25) p.vx += 0.004;
        if (p.x > w + 10) p.x = w * 0.3;
        if (p.y < -10) p.y = h + 10;
        if (p.y > h + 10) p.y = -10;
        if (cursor.activo) {
          const dx = p.x - cursor.x; const dy = p.y - cursor.y; const d2 = dx * dx + dy * dy;
          if (d2 < radioCursor * radioCursor) { const f = 0.012 * (1 - Math.sqrt(d2) / radioCursor); p.vx += dx * f * 0.02; p.vy += dy * f * 0.02; }
        }
        p.vx *= 0.995; p.vy *= 0.995;
      }
    }
    // Líneas entre puntos cercanos al cursor
    if (cursor.activo) {
      const cerca = puntos.filter((p) => (p.x - cursor.x) ** 2 + (p.y - cursor.y) ** 2 < radioCursor * radioCursor);
      c.lineWidth = 1;
      for (let i = 0; i < cerca.length; i++) {
        for (let j = i + 1; j < cerca.length; j++) {
          const a = cerca[i]; const b = cerca[j];
          const d = Math.hypot(a.x - b.x, a.y - b.y);
          if (d < 120) {
            c.strokeStyle = `rgba(58,134,200,${0.35 * (1 - d / 120)})`;
            c.beginPath(); c.moveTo(a.x, a.y); c.lineTo(b.x, b.y); c.stroke();
          }
        }
      }
    }
    for (const p of puntos) {
      const brillo = 0.35 + 0.35 * Math.sin(t / 1400 + p.fase);
      c.fillStyle = `rgba(${p.col},${brillo})`;
      c.beginPath(); c.arc(p.x, p.y, p.r, 0, 6.283); c.fill();
    }
  }

  function bucle(t) {
    if (!visible || document.hidden) { corriendo = false; return; }
    dibujar(t);
    requestAnimationFrame(bucle);
  }
  function arrancar() { if (!corriendo && !quieto) { corriendo = true; requestAnimationFrame(bucle); } }

  new ResizeObserver(medir).observe(canvas);
  new IntersectionObserver((e) => { visible = e[0].isIntersecting; if (visible) arrancar(); }).observe(canvas);
  document.addEventListener('visibilitychange', arrancar);
  const heroe = canvas.closest('section');
  heroe.addEventListener('pointermove', (e) => {
    const r = canvas.getBoundingClientRect();
    cursor.x = e.clientX - r.left; cursor.y = e.clientY - r.top; cursor.activo = e.pointerType === 'mouse';
  });
  heroe.addEventListener('pointerleave', () => { cursor.activo = false; });
  medir();
  arrancar();
}
