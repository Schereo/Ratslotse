// Sofort-Feedback beim Seitenwechsel (Design 29a, P3): Next zeigt diese Datei,
// solange das Bündel der Route lädt. Ohne sie blieb beim ersten Aufruf einer
// Seite der alte Inhalt stehen — es sah aus, als sei der Tipp verpufft.
import { DetailSkeleton } from "@/components/ui";

export default function Loading() {
  return (
    <div>
      <DetailSkeleton />
    </div>
  );
}
