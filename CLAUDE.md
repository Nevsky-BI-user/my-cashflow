# Сімейний Кешфлоу — PWA on GitHub Pages

## Проєкт

PWA-додаток "Сімейний Кешфлоу" — управління фінансами сімʼї.
Хостинг: GitHub Pages (автодеплой при push у `master`).
Репозиторій: `my-cashflow` (GitHub, гілка `master`, root `/`).

## Структура файлів

```
/
├── index.html        — весь додаток (HTML + CSS + inline JS з React)
├── manifest.json     — PWA-маніфест
├── sw.js             — Service Worker (кешування, офлайн)
├── icon-192.svg      — PWA-іконка 192×192
├── icon-512.svg      — PWA-іконка 512×512
├── .gitignore
├── CLAUDE.md         — цей файл
```

## Технічний стек

- React 18 через CDN (`cdnjs.cloudflare.com/ajax/libs/react/18.3.1`)
- ReactDOM 18 через CDN
- Чистий HTML/CSS/JS — без npm, без збірки, без бандлера
- Single-file архітектура — весь код і `index.html`
- Темна тема (dark only), CSS-змінні
- Мова інтерфейсу: українська

## Service Worker — механізм оновлення

### Поточна стратегія

Файл `sw.js` використовує **дві стратегії**:

1. **Network First** для локальних файлів (`index.html`, іконки, маніфест):
   - Є інтернет → завантажує з мережі, кешує, віддає
   - Немає інтернету → віддає з кеш
2. **Cache First з мережевим fallback** для CDN/esm.sh (React та інші бібліотеки):
   - Є в кеші → віддає з кеш
   - Нема → завантажує, кешує, віддає

### Версія кеш

Задається константою `CACHE` в першому рядку `sw.js`:

```js
const CACHE = 'cashflow-v2';
```

### Як працює оновлення

```
git push origin master
       ↓
GitHub Pages оновлює файли (30с — 2хв)
       ↓
Користувач відкриває додаток / браузер перевіряє sw.js (кожні ≤24 год)
       ↓
Браузер бачить що sw.js змінився (нова версія CACHE)
       ↓
install: створює НОВИЙ кеш (cashflow-v3), завантажує ASSETS з мережі
       ↓
skipWaiting(): активує новий SW одразу
       ↓
activate: видаляє ВСІ старі кеші (cashflow-v2 тощо)
       ↓
clients.claim(): бере контроль над відкритими вкладками
       ↓
controllerchange → сторінка автоматично перезавантажується
       ↓
Користувач бачить нову версію одразу
```

### Масив кешованих файлів

```js
const ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './icon-192.svg',
  './icon-512.svg',
];
```

Якщо додаєш новий локальний файл — додай його в `ASSETS`.
CDN-залежності НЕ додавати в `ASSETS` — вони кешуються окремо через fetch-обробник.

## Правила при внесенні змін

### ОБОВ'ЯЗКОВО при КОЖНОМУ коміті:

1. **Інкрементувати версію кеш** у `sw.js`:
   ```js
   // Було:
   const CACHE = 'cashflow-v2';
   // Стало:
   const CACHE = 'cashflow-v3';
   ```
   Без цього користувачі з встановленим PWA не отримають оновлення.
   Навіть якщо зміни тільки в `index.html` — все одно інкрементувати.

2. **Зберігати single-file архітектуру** — HTML, CSS, JS в `index.html`.

3. **Не видаляти і не перейменовувати** `sw.js`, `manifest.json`, іконки.

4. **Коміт-повідомлення** — описове:
   ```
   feat: додано графік витрат по категоріях
   fix: неправильний розрахунок балансу
   style: оновлено відступи карток
   ```

### Git workflow

```bash
# 1. Внести зміни в index.html (або інші файли)
# 2. Інкрементувати CACHE у sw.js
# 3. Коміт і пуш:
git add -A
git commit -m "feat: опис змін"
git push origin master
```

Гілка: тільки `master`. GitHub Pages: `master` branch, root `/`.

## Заборони

- Не комітити без інкременту `CACHE` у `sw.js`
- Не видаляти `skipWaiting()` і `self.clients.claim()` з SW — без них оновлення не застосується до закриття всіх вкладок
- Не додавати CDN-URL у масив `ASSETS` — вони кешуються через окремий fetch-обробник
- Не виносити CSS/JS з `index.html` в окремі файли без додавання їх у `ASSETS`
- Не змінювати URL іконок у `manifest.json` без відповідної зміни імен файлів

## Перевірка оновлення після push

В браузері (DevTools → Application):
1. **Service Workers** — `Status: activated and is running`, нова версія
2. **Cache Storage** — тільки новий `CACHE` (напр. `cashflow-v3`), старих нема
3. **Manifest** — Identity відповідає `manifest.json`

Примусове оновлення:
- Десктоп: `Ctrl+Shift+R`
- Мобільний PWA: закрити → відкрити. Якщо не допомогло — видалити з Home Screen → додати знову
