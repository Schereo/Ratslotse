import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function formatDate(iso: string): string {
  const parts = iso?.split("-");
  if (parts?.length === 3) return `${parts[2]}.${parts[1]}.${parts[0]}`;
  return iso || "";
}
