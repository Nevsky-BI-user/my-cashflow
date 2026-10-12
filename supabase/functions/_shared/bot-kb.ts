// Постійна клавіатура бота: спільна для відповідей telegram-webhook і ранкового підсумку telegram-digest
// (кожне повідомлення з нею оновлює кнопки в чаті). Кнопки шлють звичайний текст, який розуміє роутер вебхука.
export const KB_BTN = { balance: '💰 Баланс', chart: '📈 Графік', budget: '📊 Бюджет', week: '📅 Тиждень', month: '🔍 Місяць' };
export const MAIN_KB = {
  keyboard: [
    [{ text: KB_BTN.balance }, { text: KB_BTN.chart }],
    [{ text: KB_BTN.budget }, { text: KB_BTN.week }],
    [{ text: KB_BTN.month }],
  ],
  resize_keyboard: true,
  is_persistent: true,
};
export const APP_URL = 'https://nevsky-bi-user.github.io/my-cashflow/';
// Кнопка «Оплачено» під нагадуванням; для погашення кредитки і списань Monobank замість неї посилання на застосунок
export const paidKb = (callback: string | null) => callback
  ? { inline_keyboard: [[{ text: '✅ Оплачено', callback_data: callback }]] }
  : { inline_keyboard: [[{ text: '📱 Відкрити застосунок', url: APP_URL }]] };
