// Die erste Bürgerportal-Iteration wird ausschließlich auf dev/feature gebaut.
// Im Produktions-Build bleiben Route, Navigation und Sitemap unsichtbar.
export const PROBLEME_FREI = process.env.NEXT_PUBLIC_RATSLOTSE_ENV === "dev";
