import type { Metadata } from "next";

/** Eigener Name statt des geerbten „Quiz" — derselbe wie in `kern/knowledge.py`. */
export const metadata: Metadata = {
  title: "Quiz-Statistik",
  description: "Wie du im Quiz abschneidest — je Themenfeld.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
