import { useEffect, useRef, type CSSProperties } from "react";

/* NetworkField — the SUMA "psi-link" animated backdrop: a drifting node graph
   with energy pulses travelling along the links. Ported from the SUMA design
   system (components/motion/NetworkField). Sizes to its container; respects
   prefers-reduced-motion (renders a single static frame). */
interface Node { x: number; y: number; vx: number; vy: number; r: number; flash: number; }
interface Pulse { a: number; b: number; t: number; sp: number; col: string; }

export function NetworkField({
  density = 24, speed = 1, fade = true, style,
}: { density?: number; speed?: number; fade?: boolean; style?: CSSProperties }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const parent = canvas.parentElement;
    if (!ctx || !parent) return;

    const cs = getComputedStyle(canvas);
    const cyan = (cs.getPropertyValue("--accent") || "#2ee6ff").trim() || "#2ee6ff";
    const gold = (cs.getPropertyValue("--highlight") || "#ffcf6b").trim() || "#ffcf6b";
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    let W = 0, H = 0, nodes: Node[] = [], pulses: Pulse[] = [], raf = 0, t0 = 0, nextSpawn = 0;
    const linkDist = () => Math.min(W, H) * 0.34;

    function build() {
      const n = Math.max(6, Math.round(density * Math.sqrt((W * H) / 240000)));
      nodes = Array.from({ length: n }, () => ({
        x: Math.random() * W, y: Math.random() * H,
        vx: (Math.random() - 0.5) * 0.18 * speed, vy: (Math.random() - 0.5) * 0.18 * speed,
        r: Math.random() < 0.18 ? 2.6 : 1.6, flash: 0,
      }));
    }
    function resize() {
      W = parent!.clientWidth; H = parent!.clientHeight;
      canvas!.width = Math.round(W * dpr); canvas!.height = Math.round(H * dpr);
      canvas!.style.width = W + "px"; canvas!.style.height = H + "px";
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      build();
    }
    function edgesOf(i: number): number[] {
      const out: number[] = [], d = linkDist();
      for (let j = 0; j < nodes.length; j++) {
        if (j === i) continue;
        if (Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y) < d) out.push(j);
      }
      return out;
    }
    function spawn() {
      const a = Math.floor(Math.random() * nodes.length);
      const e = edgesOf(a);
      if (!e.length) return;
      const b = e[Math.floor(Math.random() * e.length)];
      pulses.push({ a, b, t: 0, sp: (0.006 + Math.random() * 0.006) * speed, col: Math.random() < 0.34 ? gold : cyan });
    }
    function draw() {
      ctx!.clearRect(0, 0, W, H);
      const d = linkDist();
      ctx!.lineWidth = 1;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dist = Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y);
          if (dist < d) {
            const o = (1 - dist / d) * 0.22;
            ctx!.strokeStyle = `color-mix(in srgb, ${cyan} ${Math.round(o * 100)}%, transparent)`;
            ctx!.beginPath(); ctx!.moveTo(nodes[i].x, nodes[i].y); ctx!.lineTo(nodes[j].x, nodes[j].y); ctx!.stroke();
          }
        }
      }
      for (const pl of pulses) {
        const a = nodes[pl.a], b = nodes[pl.b];
        const tail = Math.max(0, pl.t - 0.16);
        const hx = a.x + (b.x - a.x) * pl.t, hy = a.y + (b.y - a.y) * pl.t;
        const tx = a.x + (b.x - a.x) * tail, ty = a.y + (b.y - a.y) * tail;
        const g = ctx!.createLinearGradient(tx, ty, hx, hy);
        g.addColorStop(0, "transparent"); g.addColorStop(1, pl.col);
        ctx!.strokeStyle = g; ctx!.lineWidth = 2;
        ctx!.beginPath(); ctx!.moveTo(tx, ty); ctx!.lineTo(hx, hy); ctx!.stroke();
        ctx!.fillStyle = pl.col; ctx!.shadowColor = pl.col; ctx!.shadowBlur = 12;
        ctx!.beginPath(); ctx!.arc(hx, hy, 2.4, 0, Math.PI * 2); ctx!.fill(); ctx!.shadowBlur = 0;
      }
      for (const p of nodes) {
        const c = p.flash > 0.02 ? gold : cyan;
        ctx!.fillStyle = c; ctx!.shadowColor = c; ctx!.shadowBlur = 6 + p.flash * 14;
        ctx!.beginPath(); ctx!.arc(p.x, p.y, p.r + p.flash * 1.8, 0, Math.PI * 2); ctx!.fill();
      }
      ctx!.shadowBlur = 0;
    }
    function frame(now: number) {
      const dt = t0 ? Math.min(40, now - t0) : 16; t0 = now;
      for (const p of nodes) {
        p.x += p.vx * dt * 0.06; p.y += p.vy * dt * 0.06;
        if (p.x < 0 || p.x > W) p.vx *= -1;
        if (p.y < 0 || p.y > H) p.vy *= -1;
        p.x = Math.max(0, Math.min(W, p.x)); p.y = Math.max(0, Math.min(H, p.y));
        p.flash = Math.max(0, p.flash - dt * 0.0025);
      }
      if (now > nextSpawn && pulses.length < 14) { spawn(); nextSpawn = now + (240 + Math.random() * 520) / speed; }
      for (let i = pulses.length - 1; i >= 0; i--) {
        pulses[i].t += pulses[i].sp * dt;
        if (pulses[i].t >= 1) { nodes[pulses[i].b].flash = 1; pulses.splice(i, 1); }
      }
      draw();
      raf = requestAnimationFrame(frame);
    }

    resize();
    const ro = new ResizeObserver(resize); ro.observe(parent);
    if (reduce) { draw(); }
    else { raf = requestAnimationFrame(frame); }
    return () => { cancelAnimationFrame(raf); ro.disconnect(); };
  }, [density, speed]);

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none", ...style }} aria-hidden>
      <canvas ref={ref} style={{ display: "block", width: "100%", height: "100%" }} />
      {fade && (
        <div style={{
          position: "absolute", inset: 0, pointerEvents: "none",
          background: "radial-gradient(120% 90% at 50% 40%, transparent 55%, var(--bg-deep, #0b1322) 100%)",
        }} />
      )}
    </div>
  );
}
