// Sofort-Feedback beim Seitenwechsel (Design 29a, P3): Next zeigt diese Datei,
// solange das Bündel der Route lädt. Ohne sie blieb beim ersten Aufruf einer
// Seite der alte Inhalt stehen — es sah aus, als sei der Tipp verpufft.
import { CardListSkeleton, Skeleton } from "@/components/ui";

export default function Loading() {
  return (
    <div>
      <Skeleton className="h-7 w-48" />
      <Skeleton className="mt-2 h-3.5 w-72" />
      <div className="mt-6"><CardListSkeleton rows={3} /></div>
    </div>
  );
}
