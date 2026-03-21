export const defaultPlanCode = "standard";
export const defaultPlanLabel = "Standard";
export const defaultSeatLimit = 3;
export const trialDays = 7;
export const monthlyPriceUsd = 2;

export function pricingSummary(): string {
  return `${trialDays}-day free trial, then $${monthlyPriceUsd}/month`;
}

export function trialEndsAt(createdAt: string): Date {
  return new Date(new Date(createdAt).getTime() + trialDays * 24 * 60 * 60 * 1000);
}
