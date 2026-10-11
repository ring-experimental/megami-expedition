/**
 * 공방: two recruited monsters → one. A listed pair fuses into a new species (both consumed);
 * any other pair is an inheritance — the base keeps its body and learns one of the material's skills.
 */
export interface FusionRecipe { a: string; b: string; result: string }

export const FUSIONS: FusionRecipe[] = [];

export function fusionResult(a: string, b: string) {
  return FUSIONS.find((f) => (f.a === a && f.b === b) || (f.a === b && f.b === a))?.result ?? null;
}

/** Inherited skills a monster can hold on top of its own. */
export const MAX_INHERITED = 2;
