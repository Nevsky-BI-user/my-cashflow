(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.CashflowForecast = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const DAY = 86400000;
  const MAX = BigInt(Number.MAX_SAFE_INTEGER);

  function cents(value, label) {
    if (!Number.isSafeInteger(value) || value < 0) throw new RangeError(label + ' must be safe nonnegative integer cents');
    return value;
  }

  function safe(value, label) {
    if (value > MAX || value < -MAX) throw new RangeError(label + ' exceeds safe integer cents');
    return Number(value);
  }

  function date(value, label) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new RangeError(label + ' must be YYYY-MM-DD');
    const time = Date.parse(value + 'T00:00:00.000Z');
    if (!Number.isFinite(time) || new Date(time).toISOString().slice(0, 10) !== value) throw new RangeError(label + ' must be a valid calendar date');
    return time;
  }

  // Найбільші залишки; рівні залишки розвʼязуємо за id, незалежно від порядку входу.
  function allocate(total, units, categories) {
    const sum = units.reduce((acc, unit) => acc + unit, 0n);
    if (total === 0) return units.map(() => 0);
    const rows = units.map((unit, index) => {
      const product = BigInt(total) * unit;
      return { index, amount: Number(product / sum), remainder: product % sum };
    });
    let left = total - rows.reduce((acc, row) => acc + row.amount, 0);
    rows.sort((a, b) => a.remainder === b.remainder
      ? (categories[a.index].id < categories[b.index].id ? -1 : 1)
      : (a.remainder > b.remainder ? -1 : 1));
    for (let i = 0; i < left; i++) rows[i].amount++;
    const result = units.map(() => 0);
    rows.forEach(row => { result[row.index] = row.amount; });
    return result;
  }

  // Прототип касового плану після резервування: без фактичних банківських проводок.
  // Ваги: 0..10000, максимум 4 десяткові знаки; сума не мусить дорівнювати 100.
  function planPeriod(input) {
    if (!input || typeof input !== 'object') throw new RangeError('planPeriod input is required');
    const startTime = date(input.start, 'start');
    const endTime = date(input.end, 'end');
    const days = (endTime - startTime) / DAY;
    if (days < 1 || days > 366) throw new RangeError('period must contain 1..366 calendar days, end exclusive');
    const own = cents(input.ownCents, 'ownCents');
    const payout = cents(input.payoutCents, 'payoutCents');
    const mandatory = cents(input.mandatoryCents, 'mandatoryCents');
    const debt = cents(input.debtCents, 'debtCents');
    const minimum = cents(input.minCents === undefined ? 1500000 : input.minCents, 'minCents');
    if (!Array.isArray(input.categories) || input.categories.length < 1 || input.categories.length > 20) throw new RangeError('categories must contain 1..20 entries');
    const ids = new Set();
    const categories = input.categories.map(category => {
      if (!category || typeof category.id !== 'string' || !category.id.trim() || ids.has(category.id)) throw new RangeError('category ids must be unique nonempty strings');
      ids.add(category.id);
      const weight = category.weight;
      if (!Number.isFinite(weight) || weight < 0 || weight > 10000 || Math.abs(weight * 10000 - Math.round(weight * 10000)) > 0.000001) throw new RangeError('weight must be 0..10000 with at most 4 decimal places');
      return { id: category.id, name: category.name, weight };
    });
    const units = categories.map(category => BigInt(Math.round(category.weight * 10000)));
    if (units.every(unit => unit === 0n)) throw new RangeError('category weights must have a positive sum');
    // Контроль також проміжних грошових сум, а не лише кінцевого залишку.
    const incoming = safe(BigInt(own) + BigInt(payout), 'incoming');
    const reserved = safe(BigInt(mandatory) + BigInt(debt), 'reserved');
    const baseAvailableCents = safe(BigInt(incoming) - BigInt(reserved), 'baseAvailableCents');
    const targetCents = Math.max(minimum, baseAvailableCents);
    const initialGap = safe(BigInt(targetCents) - BigInt(baseAvailableCents), 'initialGap');
    let transferCents = 0;
    let repaymentDate = null;
    if (input.credit !== undefined && input.credit !== null) {
      const credit = input.credit;
      if (typeof credit !== 'object') throw new RangeError('credit must be an object');
      const requested = cents(credit.requestedCents, 'requestedCents');
      const eligible = credit.eligibleCents == null ? null : cents(credit.eligibleCents, 'eligibleCents');
      const limit = credit.limitCents == null ? null : cents(credit.limitCents, 'limitCents');
      if (credit.repaymentDate != null) {
        if (date(credit.repaymentDate, 'repaymentDate') < startTime) throw new RangeError('repaymentDate must be on or after start');
        repaymentDate = credit.repaymentDate;
      }
      if (eligible !== null && limit !== null && repaymentDate !== null) transferCents = Math.min(requested, eligible, limit, initialGap);
    }
    const availableCents = safe(BigInt(baseAvailableCents) + BigInt(transferCents), 'availableCents');
    const gapCents = safe(BigInt(Math.max(0, minimum)) - BigInt(Math.min(minimum, availableCents)), 'gapCents');
    const totals = allocate(targetCents, units, categories);
    const remaining = totals.slice();
    let cash = availableCents;
    let debtAtEndCents = transferCents;
    const quotient = Math.floor(targetCents / days);
    const extra = targetCents % days;
    const schedule = Array.from({ length: days }, (_, day) => {
      const dayDate = new Date(startTime + day * DAY).toISOString().slice(0, 10);
      const spendCents = quotient + (day < extra ? 1 : 0);
      const amounts = day === days - 1 ? remaining.slice() : allocate(spendCents, remaining.map(BigInt), categories);
      amounts.forEach((amount, index) => { remaining[index] -= amount; });
      const repaymentCents = dayDate === repaymentDate ? transferCents : 0;
      debtAtEndCents -= repaymentCents;
      cash = safe(BigInt(cash) - BigInt(spendCents) - BigInt(repaymentCents), 'remainingCents');
      return { date: dayDate, spendCents, repaymentCents, remainingCents: cash,
        byCategory: categories.map((category, index) => ({ id: category.id, name: category.name, amountCents: amounts[index] })) };
    });
    return { days, start: input.start, end: input.end, baseAvailableCents, availableCents, targetCents,
      gapCents, transferCents, newDebtCents: transferCents, debtAtEndCents, repaymentDate,
      averageDailyCents: targetCents / days, endingCents: cash,
      categories: categories.map((category, index) => ({ ...category, totalCents: totals[index] })), schedule };
  }

  return { planPeriod };
});
