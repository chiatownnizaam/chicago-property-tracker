/**
 * Mortgage affordability math.
 *
 * Standard amortization formula:
 *   M = P * (r(1+r)^n) / ((1+r)^n - 1)
 *
 * P = principal (loan amount)
 * r = monthly interest rate (annual / 12)
 * n = number of payments (term in months)
 *
 * Income required uses the 28% front-end DTI rule:
 *   monthly_PITI / monthly_income <= 0.28
 *   monthly_income >= monthly_PITI / 0.28
 *   annual_income >= monthly_income * 12
 *
 * Defaults pick reasonable Cook County values:
 *   - 20% down payment
 *   - 30-year fixed term
 *   - Property tax: 2.0% of price annually (Cook County average for residential)
 *   - Insurance: 0.5% of price annually
 */

const DEFAULTS = {
  down_payment_pct: 0.20,
  term_years: 30,
  property_tax_rate: 0.020,
  insurance_rate: 0.005,
  hoa_monthly: 0,
};

export function monthlyPI(principal, annualRate, termYears) {
  if (!principal || annualRate == null) return null;
  const r = annualRate / 100 / 12;
  const n = termYears * 12;
  if (r === 0) return principal / n;
  return (principal * (r * Math.pow(1 + r, n))) / (Math.pow(1 + r, n) - 1);
}

export function computeAffordability(price, mortgageRatePct, opts = {}) {
  const o = { ...DEFAULTS, ...opts };
  if (!price || mortgageRatePct == null) return null;

  const down = price * o.down_payment_pct;
  const principal = price - down;
  const pi = monthlyPI(principal, mortgageRatePct, o.term_years);
  const taxMonthly = (price * o.property_tax_rate) / 12;
  const insMonthly = (price * o.insurance_rate) / 12;
  const piti = pi + taxMonthly + insMonthly + (o.hoa_monthly || 0);

  // 28% DTI rule (front-end)
  const incomeMonthly = piti / 0.28;
  const incomeAnnual = incomeMonthly * 12;

  return {
    price,
    down_payment: Math.round(down),
    loan_amount: Math.round(principal),
    rate_pct: mortgageRatePct,
    term_years: o.term_years,
    monthly_pi: Math.round(pi),
    monthly_tax: Math.round(taxMonthly),
    monthly_insurance: Math.round(insMonthly),
    monthly_hoa: Math.round(o.hoa_monthly || 0),
    monthly_piti: Math.round(piti),
    income_required_annual: Math.round(incomeAnnual),
  };
}

export function fmtMoney(n) {
  if (n == null) return "—";
  return `$${Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}
