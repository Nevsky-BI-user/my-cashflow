// Клавіатура бота: спільна для відповідей telegram-webhook і ранкового підсумку telegram-digest
// (кожне повідомлення з нею оновлює кнопки в чаті). Кнопки шлють звичайний текст, який розуміє роутер вебхука.
export const KB_BTN = {
  balance: '💰 Баланс', chart: '📈 Графік', budget: '📊 Бюджет', week: '📅 Тиждень', month: '🔍 Місяць', today: '🧾 Витрати за сьогодні',
  income: '➕ Дохід', expense: '➖ Витрата', last: '📋 Останні', help: '❓ Допомога', app: '📱 Застосунок',
  menu: '⬅️ Головне меню', text: '✍️ Текстом', image: '📷 Зображенням', cancel: '✖ Скасувати', yes: '✅ Так, додати',
  // v215: розділи колишнього статусу «Баланс» окремими кнопками
  cards: '💳 Картки', installments: '📆 Розстрочки', payments: '⏰ Платежі', operations: '🗂 Операції',
};
export const MAIN_KB = {
  keyboard: [
    [{ text: KB_BTN.balance }, { text: KB_BTN.chart }],
    [{ text: KB_BTN.budget }, { text: KB_BTN.payments }],
    [{ text: KB_BTN.cards }, { text: KB_BTN.installments }],
    [{ text: KB_BTN.operations }],
    // v186 (власник): без кнопок «Допомога» і «Застосунок»; /help і /app працюють командами
    // v215 (власник): без «Тиждень», «Витрати за сьогодні», «Останні»; їхні тексти й /week, /today, /last працюють
  ],
  resize_keyboard: true,
  // v186 (власник: «меню з кнопками чомусь зникає, а має відображатись постійно»): клавіатура не згортається після натискання
  is_persistent: true,
  one_time_keyboard: false,
  input_field_placeholder: 'Сума й опис або фото операції',
};
// Вибір способу введення для сумісності з командами попереднього сценарію.
export const ENTRY_KB = {
  keyboard: [
    [{ text: KB_BTN.text }, { text: KB_BTN.image }],
  ],
  resize_keyboard: true,
  is_persistent: false,
  one_time_keyboard: true,
  input_field_placeholder: 'Сума й опис або фото операції',
};
export const ENTRY_INPUT_KB = MAIN_KB;
// v215 (власник: «з ПК кнопок не бачу і викликати їх не можу, крім як через команди»): меню команд «/» знову реєструється
// в telegram-setup (до v215 видалялось за рішенням v186), щоб розділи можна було викликати і без клавіатури
export const BOT_COMMANDS = [
  { command: 'balance', description: 'Бюджет і баланс' },
  { command: 'cards', description: 'Картки' },
  { command: 'installments', description: 'Розстрочки' },
  { command: 'payments', description: 'Найближчі платежі' },
  { command: 'operations', description: 'Останні операції' },
  { command: 'budget', description: 'Бюджет періоду' },
  { command: 'chart', description: 'Графік балансу' },
  { command: 'menu', description: 'Показати кнопки' },
  { command: 'help', description: 'Допомога' },
];
export const APP_URL = 'https://nevsky-bi-user.github.io/my-cashflow/';
// Кнопка «Оплачено» під нагадуванням; для погашення кредитки і списань Monobank без кнопки (v186: власник прибрав «Відкрити застосунок»)
export const paidKb = (callback: string | null) => callback
  ? { inline_keyboard: [[{ text: '✅ Оплачено', callback_data: callback }]] }
  : undefined;
