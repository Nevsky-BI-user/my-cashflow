'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { planPeriod } = require('../docs/redesign/forecast-model.js');

function fixture(overrides = {}) {
  return { start: '2026-10-21', end: '2026-11-06', ownCents: 280000,
    payoutCents: 5000000, mandatoryCents: 2800000, debtCents: 1600000,
    categories: [40, 20, 15, 10, 10, 5].map((weight, index) => ({ id: String(index + 1), name: 'Category ' + (index + 1), weight })),
    ...overrides };
}
function credit(overrides = {}) {
  return { requestedCents: 620000, eligibleCents: 620000, limitCents: 1000000, repaymentDate: '2026-11-06', ...overrides };
}
function assertConserved(plan) {
  assert.equal(plan.categories.reduce((sum, category) => sum + category.totalCents, 0), plan.targetCents);
  assert.equal(plan.schedule.reduce((sum, day) => sum + day.spendCents, 0), plan.targetCents);
  for (const day of plan.schedule) {
    assert.equal(day.byCategory.reduce((sum, category) => sum + category.amountCents, 0), day.spendCents);
    assert.ok(day.byCategory.every(category => Number.isSafeInteger(category.amountCents) && category.amountCents >= 0));
  }
  for (const category of plan.categories) {
    assert.equal(plan.schedule.reduce((sum, day) => sum + day.byCategory.find(item => item.id === category.id).amountCents, 0), category.totalCents);
  }
}

test('baseline uses the living budget and preserves the cash deficit', () => {
  const plan = planPeriod(fixture());
  assert.equal(plan.baseAvailableCents, 880000);
  assert.equal(plan.availableCents, 880000);
  assert.equal(plan.targetCents, 1500000);
  assert.equal(plan.gapCents, 620000);
  assert.equal(plan.days, 16);
  assert.equal(plan.averageDailyCents, 93750);
  assert.equal(plan.endingCents, -620000);
  assert.deepEqual(plan.categories.map(category => category.totalCents), [600000, 300000, 225000, 150000, 150000, 75000]);
  assert.ok(plan.schedule.every(day => day.spendCents === 93750));
  assertConserved(plan);
});

test('full and partial credit transfers retain the base and incur debt', () => {
  const full = planPeriod(fixture({ credit: credit() }));
  assert.equal(full.baseAvailableCents, 880000);
  assert.equal(full.availableCents, 1500000);
  assert.equal(full.endingCents, 0);
  assert.equal(full.newDebtCents, 620000);
  assert.equal(full.debtAtEndCents, 620000);
  assert.equal(full.schedule.reduce((sum, day) => sum + day.repaymentCents, 0), 0);
  const partial = planPeriod(fixture({ credit: credit({ requestedCents: 400000 }) }));
  assert.equal(partial.availableCents, 1280000);
  assert.equal(partial.gapCents, 220000);
  assert.equal(partial.endingCents, -220000);
});

test('credit is bounded by eligibility, limit and gap; unknown terms disable it', () => {
  for (const [terms, expected] of [[{ eligibleCents: 100000 }, 100000], [{ limitCents: 200000 }, 200000],
    [{ requestedCents: 900000, eligibleCents: 900000, limitCents: 900000 }, 620000],
    [{ eligibleCents: null }, 0], [{ limitCents: undefined }, 0], [{ repaymentDate: null }, 0], [{ repaymentDate: undefined }, 0]]) {
    assert.equal(planPeriod(fixture({ credit: credit(terms) })).transferCents, expected);
  }
  assert.equal(planPeriod(fixture({ mandatoryCents: 1000000, credit: credit() })).transferCents, 0);
});

test('repayment within the period occurs once and may reopen the gap', () => {
  const plan = planPeriod(fixture({ credit: credit({ repaymentDate: '2026-10-25' }) }));
  assert.equal(plan.schedule.filter(day => day.repaymentCents > 0).length, 1);
  assert.equal(plan.schedule.find(day => day.date === '2026-10-25').repaymentCents, 620000);
  assert.equal(plan.endingCents, -620000);
  assert.equal(plan.newDebtCents, 620000);
  assert.equal(plan.debtAtEndCents, 0);
  const startDue = planPeriod(fixture({ credit: credit({ repaymentDate: '2026-10-21' }) }));
  assert.equal(startDue.schedule[0].repaymentCents, 620000);
});

test('above-minimum, negative available and zero own cash examples', () => {
  const above = planPeriod(fixture({ mandatoryCents: 1000000 }));
  assert.equal(above.availableCents, 2680000);
  assert.equal(above.targetCents, 2680000);
  assert.equal(above.averageDailyCents, 167500);
  assert.equal(above.endingCents, 0);
  const negative = planPeriod(fixture({ payoutCents: 1000000 }));
  assert.equal(negative.availableCents, -3120000);
  assert.equal(negative.targetCents, 1500000);
  assert.equal(negative.gapCents, 4620000);
  assert.equal(negative.endingCents, -4620000);
  assert.equal(planPeriod(fixture({ ownCents: 0 })).availableCents, 600000);
});

test('calendar dates cover leap days, year boundaries and DST without local time', () => {
  for (const [start, end, days] of [['2024-02-28', '2024-03-01', 2], ['2026-12-31', '2027-01-02', 2],
    ['2026-03-28', '2026-03-30', 2], ['2026-10-24', '2026-10-26', 2], ['2024-01-01', '2025-01-01', 366]]) {
    const plan = planPeriod(fixture({ start, end }));
    assert.equal(plan.days, days);
    assert.equal(plan.schedule[0].date, start);
    assert.ok(plan.schedule.every(day => day.date < end));
  }
});

test('odd budgets conserve every row and column, normalized weights and stable id ties', () => {
  const categories = [{ id: 'b', name: 'B', weight: 0.5 }, { id: 'a', name: 'A', weight: 0.5 }, { id: 'zero', weight: 0 }];
  for (let budget = 0; budget <= 43; budget++) {
    const plan = planPeriod(fixture({ start: '2026-01-01', end: '2026-01-08', ownCents: budget,
      payoutCents: 0, mandatoryCents: 0, debtCents: 0, minCents: 0, categories }));
    assertConserved(plan);
    assert.equal(plan.endingCents, 0);
    assert.equal(Math.max(...plan.schedule.map(day => day.spendCents)) - Math.min(...plan.schedule.map(day => day.spendCents)) <= 1, true);
    const reverse = planPeriod(fixture({ start: '2026-01-01', end: '2026-01-08', ownCents: budget,
      payoutCents: 0, mandatoryCents: 0, debtCents: 0, minCents: 0, categories: categories.slice().reverse() }));
    assert.deepEqual(plan.schedule.map(day => day.byCategory.slice().sort((a, b) => a.id.localeCompare(b.id))),
      reverse.schedule.map(day => day.byCategory.slice().sort((a, b) => a.id.localeCompare(b.id))));
    if (budget % 2) assert.equal(plan.categories.find(category => category.id === 'a').totalCents, Math.ceil(budget / 2));
  }
});

test('input is not mutated and browser global exposes the same API', () => {
  const input = fixture({ credit: credit() });
  const before = JSON.stringify(input);
  const plan = planPeriod(input);
  plan.categories[0].weight = 1;
  plan.schedule[0].byCategory[0].name = 'Changed';
  assert.equal(JSON.stringify(input), before);
  const context = vm.createContext({});
  vm.runInContext(fs.readFileSync(require.resolve('../docs/redesign/forecast-model.js'), 'utf8'), context);
  assert.equal(context.CashflowForecast.planPeriod(input).availableCents, 1500000);
});

test('invalid dates, cents, weights, categories and overflow throw RangeError', () => {
  const invalid = [{ start: '2026-02-29' }, { start: '2026-13-01' }, { start: '2026-1-01' },
    { end: '2026-10-21' }, { end: '2026-10-20' }, { start: '2024-01-01', end: '2025-01-02' },
    { categories: [] }, { categories: Array.from({ length: 21 }, (_, i) => ({ id: String(i), weight: 1 })) },
    { categories: [{ id: 'a', weight: 1 }, { id: 'a', weight: 1 }] }, { categories: [{ id: '', weight: 1 }] },
    { categories: [{ id: 'a', weight: 0 }] }, { ownCents: Number.MAX_SAFE_INTEGER, payoutCents: 1 },
    { mandatoryCents: Number.MAX_SAFE_INTEGER, debtCents: 1 },
    { credit: credit({ repaymentDate: '2026-10-20' }) }, { credit: credit({ repaymentDate: 'invalid' }) }];
  for (const field of ['ownCents', 'payoutCents', 'mandatoryCents', 'debtCents', 'minCents']) {
    for (const value of [-1, 0.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1, null, '100']) invalid.push({ [field]: value });
  }
  for (const value of [-1, NaN, Infinity, 10001, 0.00001, '1']) invalid.push({ categories: [{ id: 'a', weight: value }] });
  for (const field of ['requestedCents', 'eligibleCents', 'limitCents']) invalid.push({ credit: credit({ [field]: -1 }) });
  for (const overrides of invalid) assert.throws(() => planPeriod(fixture(overrides)), RangeError);
  assert.throws(() => planPeriod(null), RangeError);
});
