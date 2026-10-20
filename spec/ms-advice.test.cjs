const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const html = fs.readFileSync(require('node:path').join(__dirname, '..', 'index.html'), 'utf8');
const source = html.match(/^function msAdviceEligible\([^\n]+/m);
assert.ok(source, 'Фільтр поради про поріг рахунку існує');
const eligible = vm.runInNewContext(`${source[0]}; msAdviceEligible`);

test('порада Ощаду не пропонує погашення кредиту Привату', () => {
  const oschad = { bank: 'oschad' };
  const fixed = [
    { id: 1, bank: 'privat' },
    { id: 2, bank: 'oschad' },
    { id: 3 },
  ];
  const credits = [{ id: 4, source: 'privat' }];
  const payment = (id, name = 'Платіж') => ({ id, name, kind: 'mandatory', funding: 'cash' });

  assert.equal(eligible(payment('fixed:1:2026-10'), oschad, fixed, credits), false);
  assert.equal(eligible(payment('installment:4:2026-10'), oschad, fixed, credits), false);
  assert.equal(eligible(payment('fixed:3:2026-10', 'Погашення кредиту Привату'), oschad, fixed, credits), false);
  assert.equal(eligible(payment('fixed:2:2026-10'), oschad, fixed, credits), true);
  assert.equal(eligible(payment('fixed:3:2026-10'), oschad, fixed, credits), true);
});
