// Постійна клавіатура бота: спільна для відповідей telegram-webhook і ранкового підсумку telegram-digest
// (кожне повідомлення з нею оновлює кнопки в чаті). Кнопки шлють звичайний текст, який розуміє роутер вебхука.
export const KB_BTN = {
  balance: '💰 Баланс', chart: '📈 Графік', budget: '📊 Бюджет', week: '📅 Тиждень', month: '🔍 Місяць',
  income: '➕ Дохід', expense: '➖ Витрата', last: '📋 Останні', help: '❓ Допомога', app: '📱 Застосунок',
  menu: '⬅️ Головне меню', text: '✍️ Текстом', image: '📷 Зображенням', cancel: '✖ Скасувати', yes: '✅ Так, додати',
};
export const MAIN_KB = {
  keyboard: [
    [{ text: KB_BTN.income }, { text: KB_BTN.expense }],
    [{ text: KB_BTN.balance }, { text: KB_BTN.chart }],
    [{ text: KB_BTN.budget }, { text: KB_BTN.week }],
    [{ text: KB_BTN.month }, { text: KB_BTN.last }],
    [{ text: KB_BTN.help }, { text: KB_BTN.app }],
    [{ text: KB_BTN.menu }, { text: KB_BTN.cancel }],
  ],
  resize_keyboard: true,
  is_persistent: true,
};
// Вибір способу введення; під час очікування тексту чи зображення лишаємо вихід із кроку.
export const ENTRY_KB = {
  keyboard: [
    [{ text: KB_BTN.text }, { text: KB_BTN.image }],
    [{ text: KB_BTN.menu }, { text: KB_BTN.cancel }],
  ],
  resize_keyboard: true,
  is_persistent: true,
};
export const ENTRY_INPUT_KB = {
  keyboard: [[{ text: KB_BTN.menu }, { text: KB_BTN.cancel }]],
  resize_keyboard: true,
  is_persistent: true,
};
// Єдиний каталог команд для реєстрації меню Telegram.
export const BOT_COMMANDS = [
  { command: 'menu', description: 'Відкрити головне меню' },
  { command: 'income', description: 'Додати дохід текстом або із зображення' },
  { command: 'expense', description: 'Додати витрату текстом або із зображення' },
  { command: 'balance', description: 'Поточний баланс і фінансовий стан' },
  { command: 'chart', description: 'Графік балансу та прогноз' },
  { command: 'budget', description: 'Бюджет поточного періоду' },
  { command: 'week', description: 'Баланс і заплановані події тижня' },
  { command: 'month', description: 'Порівняння витрат із минулим місяцем' },
  { command: 'last', description: 'Останні 5 записів' },
  { command: 'app', description: 'Відкрити застосунок' },
  { command: 'help', description: 'Як користуватися ботом' },
  { command: 'cancel', description: 'Скасувати поточне введення' },
  { command: 'yes', description: 'Підтвердити додавання операції' },
  { command: 'no', description: 'Відхилити додавання операції' },
  { command: 'start', description: 'Привʼязати акаунт: /start <код>' },
];
export const APP_URL = 'https://nevsky-bi-user.github.io/my-cashflow/';
// Кнопка «Оплачено» під нагадуванням; для погашення кредитки і списань Monobank замість неї посилання на застосунок
export const paidKb = (callback: string | null) => callback
  ? { inline_keyboard: [[{ text: '✅ Оплачено', callback_data: callback }]] }
  : { inline_keyboard: [[{ text: '📱 Відкрити застосунок', url: APP_URL }]] };
