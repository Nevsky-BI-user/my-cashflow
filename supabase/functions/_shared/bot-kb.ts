// Клавіатура бота: спільна для відповідей telegram-webhook і ранкового підсумку telegram-digest
// (кожне повідомлення з нею оновлює кнопки в чаті). Кнопки шлють звичайний текст, який розуміє роутер вебхука.
export const KB_BTN = {
  balance: '💰 Баланс', chart: '📈 Графік', budget: '📊 Бюджет', week: '📅 Тиждень', month: '🔍 Місяць', today: '🧾 Витрати за сьогодні',
  income: '➕ Дохід', expense: '➖ Витрата', last: '📋 Останні', help: '❓ Допомога', app: '📱 Застосунок',
  menu: '⬅️ Головне меню', text: '✍️ Текстом', image: '📷 Зображенням', cancel: '✖ Скасувати', yes: '✅ Так, додати',
};
export const MAIN_KB = {
  keyboard: [
    [{ text: KB_BTN.balance }, { text: KB_BTN.chart }],
    [{ text: KB_BTN.budget }, { text: KB_BTN.week }],
    [{ text: KB_BTN.today }, { text: KB_BTN.last }],
    // v186 (власник): без кнопок «Допомога» і «Застосунок»; /help і /app працюють командами
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
// v186 (власник): меню команд Telegram не реєструється, telegram-setup його видаляє; команди працюють, якщо їх набрати
export const APP_URL = 'https://nevsky-bi-user.github.io/my-cashflow/';
// Кнопка «Оплачено» під нагадуванням; для погашення кредитки і списань Monobank без кнопки (v186: власник прибрав «Відкрити застосунок»)
export const paidKb = (callback: string | null) => callback
  ? { inline_keyboard: [[{ text: '✅ Оплачено', callback_data: callback }]] }
  : undefined;
