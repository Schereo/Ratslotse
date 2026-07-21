import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  // Konkrete Transition-Properties statt transition-all; Press-Feedback
  // (active:scale 0.97) mit starker ease-out-Kurve bei 150 ms.
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-[color,background-color,border-color,opacity,transform] duration-150 ease-out-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 active:scale-[0.97] disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-primary text-primary-foreground shadow-sm shadow-primary/25 hover:bg-primary/90",
        secondary: "border border-input bg-card text-foreground hover:bg-accent",
        danger: "bg-destructive text-destructive-foreground hover:bg-destructive/90 shadow-sm",
        ghost: "text-foreground hover:bg-accent",
        // RL-101: DIE eine Signal-Handlung pro Screen (Registrieren, „Frag den
        // Rat", Neues Thema …) — Orange-Fill gibt es nur hier + bei „neu"-Badges.
        signal: "bg-signal text-signal-foreground shadow-[0_8px_22px_-10px_hsl(19_92%_45%/0.6)] hover:opacity-[0.92]",
      },
      size: {
        sm: "h-8 px-3",
        md: "h-10 px-4 py-2",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp className={cn(buttonVariants({ variant, size }), className)} ref={ref} {...props} />;
  },
);
Button.displayName = "Button";
