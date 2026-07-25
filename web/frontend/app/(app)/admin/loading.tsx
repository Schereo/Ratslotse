// Sofort-Feedback beim Seitenwechsel (Design 29a, P3): Next zeigt diese Datei,
// solange das Bündel der Route lädt. Ohne sie blieb beim ersten Aufruf einer
// Seite der alte Inhalt stehen — es sah aus, als sei der Tipp verpufft.
import { Skeleton, TableSkeleton } from "@/components/ui";

export default function Loading() {
  return (
    <div>
      <Skeleton className="h-7 w-28" />
      <Skeleton className="mt-2 h-3.5 w-64" />
      <div className="mt-6"><TableSkeleton rows={6} cols={4} /></div>
    </div>
  );
}
