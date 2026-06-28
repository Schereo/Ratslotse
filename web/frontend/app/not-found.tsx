import Link from "next/link";
import { Card, Button } from "@/components/ui";
import { BrandMark } from "@/components/brand";

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm p-8 text-center">
        <div className="flex items-center justify-center gap-3">
          <BrandMark />
          <span className="text-2xl font-bold tracking-tight text-foreground">404</span>
        </div>
        <h1 className="mt-4 text-lg font-semibold text-foreground">Seite nicht gefunden</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Diese Seite gibt es nicht (mehr). Vielleicht hilft die Startseite weiter.
        </p>
        <Link href="/" className="mt-6 inline-block w-full">
          <Button className="w-full">Zur Startseite</Button>
        </Link>
      </Card>
    </div>
  );
}
