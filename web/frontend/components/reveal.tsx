"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

// Fade-in-up the first time the element scrolls into view. Renders visible immediately
// when reduced motion is preferred.
export function Reveal({ children, className, delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setShown(true); return; }
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setShown(true); io.disconnect(); } },
      { threshold: 0.15 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      style={{ transitionDelay: `${delay}ms` }}
      // 500 ms mit starker Kurve statt 700 ms Standard-ease-out: gleiche Ruhe,
      // weniger Zähigkeit. Nur die zwei Properties, die sich wirklich ändern.
      className={cn("transition-[opacity,transform] duration-500 ease-out-strong", shown ? "translate-y-0 opacity-100" : "translate-y-5 opacity-0", className)}
    >
      {children}
    </div>
  );
}
