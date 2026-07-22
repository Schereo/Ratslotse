"use client";

import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export const Sheet = DialogPrimitive.Root;
export const SheetTrigger = DialogPrimitive.Trigger;
export const SheetClose = DialogPrimitive.Close;

const SIDE_CLASSES = {
  // RL-F10: Der Drawer liegt VOR der Topbar — er braucht die Safe-Area selbst,
  // sonst beginnt sein Inhalt hinter Uhr/Dynamic Island. Auf Geräten ohne
  // Notch ist env() schlicht 0. Scrollbar für kleine Höhen (SE, Landscape).
  left: "inset-y-0 left-0 h-full w-64 overflow-y-auto border-r pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)] data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left",
  // Bottom-Sheet (mobile Filter): rundet oben ab, respektiert die Home-Indicator-Zone.
  bottom:
    "inset-x-0 bottom-0 max-h-[85dvh] w-full overflow-y-auto rounded-t-2xl border-t pb-[env(safe-area-inset-bottom)] data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom",
} as const;

export const SheetContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & { side?: keyof typeof SIDE_CLASSES }
>(({ className, children, side = "left", ...props }, ref) => (
  <DialogPrimitive.Portal>
    <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        // iOS-artige Drawer-Kurve (ease-drawer) statt ease-in-out; Exit bewusst
        // schneller als der Eintritt. Das lose "transition" davor war wirkungslos
        // (die Bewegung kommt aus animate-in/out) und ist raus.
        "fixed z-50 flex flex-col border-border bg-card shadow-lg ease-drawer data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:duration-200 data-[state=open]:duration-300",
        SIDE_CLASSES[side],
        className,
      )}
      {...props}
    >
      {children}
      <DialogPrimitive.Close
        className={cn(
          "absolute right-3 rounded-md p-1 text-muted-foreground opacity-70 transition-opacity hover:opacity-100 focus:outline-none",
          // Nur der links oben liegende Drawer braucht die Notch-Safe-Area; beim
          // Bottom-Sheet würde sie den X-Knopf über den ersten Filter schieben.
          side === "left" ? "top-[calc(0.75rem+env(safe-area-inset-top))]" : "top-3",
        )}
      >
        <X className="h-5 w-5" />
        <span className="sr-only">Schließen</span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
));
SheetContent.displayName = "SheetContent";

export const SheetTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title ref={ref} className={cn("sr-only", className)} {...props} />
));
SheetTitle.displayName = "SheetTitle";
