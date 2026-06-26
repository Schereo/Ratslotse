"use client";

import { useEffect, useRef } from "react";

// Lightweight animated particle network for the landing hero — drifting brand-coloured
// dots that link up when close (the web of connected decisions, topics and people).
// Pure canvas, no three.js; respects prefers-reduced-motion and pauses when offscreen.
export function HeroCanvas() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const parent = canvas?.parentElement;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !parent || !ctx) return;

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let w = 0, h = 0, raf = 0, running = false;
    type P = { x: number; y: number; vx: number; vy: number };
    let pts: P[] = [];

    const brand = () => {
      const v = getComputedStyle(document.documentElement).getPropertyValue("--primary").trim();
      return v ? `hsl(${v})` : "#2563eb";
    };
    let color = brand();

    const resize = () => {
      const r = parent.getBoundingClientRect();
      w = r.width; h = r.height;
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
      canvas.style.width = `${w}px`; canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.max(18, Math.min(70, Math.floor((w * h) / 15000)));
      pts = Array.from({ length: count }, () => ({
        x: Math.random() * w, y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.3, vy: (Math.random() - 0.5) * 0.3,
      }));
      color = brand();
    };

    const render = () => {
      ctx.clearRect(0, 0, w, h);
      ctx.strokeStyle = color;
      for (let i = 0; i < pts.length; i++) {
        const a = pts[i];
        for (let j = i + 1; j < pts.length; j++) {
          const b = pts[j];
          const dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy;
          if (d2 < 130 * 130) {
            ctx.globalAlpha = (1 - Math.sqrt(d2) / 130) * 0.2;
            ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
          }
        }
      }
      ctx.globalAlpha = 0.55; ctx.fillStyle = color;
      for (const p of pts) { ctx.beginPath(); ctx.arc(p.x, p.y, 1.6, 0, Math.PI * 2); ctx.fill(); }
      ctx.globalAlpha = 1;
    };

    const step = () => {
      for (const p of pts) {
        p.x += p.vx; p.y += p.vy;
        if (p.x <= 0 || p.x >= w) p.vx *= -1;
        if (p.y <= 0 || p.y >= h) p.vy *= -1;
      }
      render();
      if (running) raf = requestAnimationFrame(step);
    };
    const start = () => { if (!running && !reduce) { running = true; raf = requestAnimationFrame(step); } };
    const stop = () => { running = false; cancelAnimationFrame(raf); raf = 0; };

    resize();
    if (reduce) render(); else start();

    const onResize = () => resize();
    window.addEventListener("resize", onResize);
    const io = new IntersectionObserver(([e]) => (e.isIntersecting ? start() : stop()));
    io.observe(canvas);
    const mo = new MutationObserver(() => { color = brand(); });
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });

    return () => { stop(); window.removeEventListener("resize", onResize); io.disconnect(); mo.disconnect(); };
  }, []);

  return <canvas ref={ref} className="pointer-events-none absolute inset-0 h-full w-full opacity-70" aria-hidden />;
}
