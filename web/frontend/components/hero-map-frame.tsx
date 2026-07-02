"use client";

import { useState } from "react";
import { HeroCanvas } from "@/components/hero-canvas";
import { HeroMap } from "@/components/hero-map";

// Framed 3D Oldenburg map for the landing hero (client island). Falls back to the
// particle network if the map tiles fail to load.
export function HeroMapFrame() {
  const [failed, setFailed] = useState(false);
  return (
    <div className="relative aspect-[4/3] overflow-hidden rounded-2xl border border-border bg-muted shadow-xl">
      {failed ? <HeroCanvas /> : <HeroMap onError={() => setFailed(true)} className="absolute inset-0 h-full w-full" />}
    </div>
  );
}
