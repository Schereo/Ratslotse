"use client";

import { createContext, useContext, useLayoutEffect, useRef, useState, type ComponentPropsWithoutRef, type ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { Card } from "@/components/ui";
import { cn } from "@/lib/utils";

export type WidgetSize = "normal" | "wide";
export type WidgetDetail = "compact" | "standard" | "expanded";
const DetailContext = createContext<WidgetDetail>("compact");

/** Inhalt folgt der tatsächlich verfügbaren Breite, auch bei großer Schrift.
 * Eine im Raster breite Karte bleibt auf dem Telefon deshalb kompakt. */
export const useWidgetDetail = () => useContext(DetailContext);

export function HeuteWidgetGrid({ className, children, ...props }: ComponentPropsWithoutRef<"div">) {
  return <div {...props} className={cn("@container/widgets", className)}>
    <div className="grid grid-cols-1 items-start gap-4 @3xl/widgets:grid-cols-2">{children}</div>
  </div>;
}

type Props = Omit<ComponentPropsWithoutRef<"section">, "id" | "title" | "children"> & {
  id: string;
  title: string;
  icon: LucideIcon;
  size?: WidgetSize;
  meta?: ReactNode;
  children: ReactNode | ((detail: WidgetDetail) => ReactNode);
  footer?: ReactNode;
};

/** Ein gemeinsamer Kopf und ein Innenraster für ALLE Heute-Widgets.
 * Größe ist eine Layout-Vorgabe; der Detailgrad kommt aus der Inhaltsbreite.
 * Inhalte dürfen Einträge ergänzen oder verkürzen, nie nur Schrift schrumpfen. */
export function HeuteWidget({ id, title, icon: Icon, size = "normal", meta, children, footer, className, ...props }: Props) {
  const content = useRef<HTMLDivElement>(null);
  const [detail, setDetail] = useState<WidgetDetail>("compact");
  useLayoutEffect(() => {
    const el = content.current;
    if (!el) return;
    const measure = () => {
      const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
      const style = getComputedStyle(el);
      const width = (el.getBoundingClientRect().width - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight)) / rem;
      setDetail(width >= 56.25 ? "expanded" : width >= 28 ? "standard" : "compact");
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return <section {...props} aria-labelledby={`${id}-title`} data-heute-widget={id} data-widget-size={size} data-widget-detail={detail}
    className={cn("min-w-0", size === "wide" && "@3xl/widgets:col-span-2", className)}>
    <Card className="overflow-hidden">
      <DetailContext.Provider value={detail}>
        <header className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border/60 px-4 py-3">
          <div className="flex min-w-0 flex-1 basis-48 items-start gap-2.5">
            <Icon className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden />
            <h2 id={`${id}-title`} tabIndex={-1} className="min-w-0 font-display text-base font-bold leading-6 text-foreground [overflow-wrap:anywhere]">{title}</h2>
          </div>
          {meta && <div className="ml-auto min-w-0 text-meta text-muted-foreground">{meta}</div>}
        </header>
        <div ref={content} className="px-4 py-3 text-hinweis [overflow-wrap:anywhere]">
          {typeof children === "function" ? children(detail) : children}
        </div>
        {footer && <footer className="border-t border-border/60 px-4 py-2">{footer}</footer>}
      </DetailContext.Provider>
    </Card>
  </section>;
}
