// Die erste Bürgerportal-Iteration wird ausschließlich für app-feature gebaut.
// Weder Dev noch Produktion setzen diesen eigenen Build-Schalter.
export const PROBLEME_FREI = process.env.NEXT_PUBLIC_BUERGERPORTAL === "1";
