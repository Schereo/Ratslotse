import { CardListSkeleton, Skeleton } from "@/components/ui";

export default function Loading() {
  return (
    <div className="mx-auto max-w-5xl">
      <Skeleton className="h-7 w-36" />
      <Skeleton className="mt-2 h-3.5 w-80" />
      <div className="mt-6"><CardListSkeleton rows={4} /></div>
    </div>
  );
}
