// Звіт бота картинкою (v234, власник 17.11.2026: «сітки немає», «тотал не виділено»): таблиці <pre>, зареєстровані preTable,
// стають однією картинкою (bot-table-svg.ts), решта тексту йде підписом. Чиста функція: надсилання й PNG у відправника.
import { tableSpecOf, type TableSpec } from './bot-table.ts';
import { tablesSvg } from './bot-table-svg.ts';

export type RichReport = { svg: string; caption: string };

// null: таблиць немає, невідома таблиця або підпис задовгий; тоді відправник шле звичайний текст
export function richReport(html: string, maxCaption = 1024): RichReport | null {
  const specs: TableSpec[] = [];
  let unknown = false;
  const rest = html.replace(/<pre>[\s\S]*?<\/pre>/g, (m) => {
    const sp = tableSpecOf(m);
    if (sp) specs.push(sp); else unknown = true;
    return '\u0000';
  });
  if (!specs.length || unknown) return null;
  const caption = rest.split('\n').filter((l) => l !== '\u0000').map((l) => l.replace(/\u0000/g, '')).join('\n').replace(/\n{3,}/g, '\n\n').trim();
  // Довжину підпису Telegram рахує за видимим текстом; HTML-сутності й теги не входять
  const visible = caption.replace(/<[^>]+>/g, '').replace(/&(amp|lt|gt|quot);/g, '_');
  if (Array.from(visible).length > maxCaption) return null;
  return { svg: tablesSvg(specs), caption };
}
