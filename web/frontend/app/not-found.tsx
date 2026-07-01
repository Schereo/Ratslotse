import Link from "next/link";
import { Button } from "@/components/ui";
import { Mascot } from "@/components/mascot";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-waves px-4 text-center">
      <Mascot pose="confused" bob className="h-36 w-36" />
      <p className="mt-4 font-display text-6xl font-bold tracking-tight text-primary">404</p>
      <h1 className="mt-3 text-xl font-semibold text-foreground">Da hat sich Lotti verflogen.</h1>
      <p className="mt-2 max-w-sm text-sm leading-relaxed text-muted-foreground">
        Diese Seite gibt es nicht (mehr) — hier ist nur offenes Wasser. Zurück auf Kurs?
      </p>
      <Link href="/" className="mt-6 inline-block">
        <Button>Zur Startseite</Button>
      </Link>
    </div>
  );
}
