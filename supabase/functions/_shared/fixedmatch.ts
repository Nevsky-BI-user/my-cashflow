// Детерміноване зіставлення назви та конкретного зобовʼязання, без вгадування суми.
export type FixedMatchRow = {id:number|string;name:string;period?:string;month_of_year?:number;day_of_month?:number;weekday?:number;active?:boolean;type?:string;end_date?:string|null};
const norm=(s:unknown)=>String(s??'').normalize('NFKC').toLowerCase().replace(/[^\p{L}\p{N}]+/gu,' ').trim();
const words=(s:unknown)=>' '+norm(s)+' ';
const claude=(s:unknown)=>/(?:^| )(?:claude|клод|anthropic)(?: |$)/u.test(norm(s));
export function fixedNameMatches(name:string,description:string):boolean {
  const n=norm(name),d=norm(description);
  if(!n||!d||['підписка','subscription','оплата','платіж'].includes(n))return false;
  if(claude(n)&&claude(d))return true;
  if(['інтернет','internet'].includes(n)&&/(?:^| )(?:інтернет|internet) (?:магазин|store|shop)(?: |$)/u.test(d))return false;
  return words(d).includes(words(n));
}
const day=(s:string)=>new Date(s+'T00:00:00Z');
const iso=(d:Date)=>d.toISOString().slice(0,10);
export function fixedOccurrence(f:FixedMatchRow,reference:string):string|null {
  if(!/^\d{4}-\d{2}-\d{2}$/.test(reference)||!Number.isFinite(day(reference).getTime())||iso(day(reference))!==reference||f.active===false||f.type==='income')return null;
  const d=day(reference),y=d.getUTCFullYear(),m=d.getUTCMonth()+1;
  if(f.period==='year'&&Number(f.month_of_year)!==m)return null;
  if(f.period==='week'){
    const w=Number(f.weekday);if(!Number.isInteger(w)||w<1||w>7)return null;
    d.setUTCDate(d.getUTCDate()-(d.getUTCDay()+6)%7+w-1);
  }else{
    const v=Number(f.day_of_month);if(!Number.isInteger(v)||v<1||v>31)return null;
    d.setUTCDate(Math.min(v,new Date(Date.UTC(y,m,0)).getUTCDate()));
  }
  const due=iso(d);return f.end_date&&due>f.end_date.slice(0,10)?null:due;
}
export function fixedOccurrenceKey(f:FixedMatchRow,date:string):string {
  if(f.period!=='week')return String(f.id)+'|'+date.slice(0,7);
  const d=day(date);d.setUTCDate(d.getUTCDate()-(d.getUTCDay()+6)%7);return String(f.id)+'|W'+iso(d);
}
export function fixedCandidates(fixed:FixedMatchRow[],description:string,date:string,paid:Set<string>=new Set()) {
  // Період, явно названий людиною, обирається кнопкою: не вгадуємо майбутній місяць.
  if(/(?:наперед|авансом|наступн|дострок|prepay|next month|за (?:січ|лют|берез|квіт|трав|черв|лип|серп|верес|жовт|листоп|груд))/iu.test(description))return [];
  if(/(?:^|\s)(?:за|на)\s+(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?)(?=$|\s|[.,;])/iu.test(description))return [];
  const hits=fixed.filter(f=>fixedNameMatches(f.name,description)).flatMap(f=>{
    const due=fixedOccurrence(f,date);return due?[{...f,due}]:[];
  });
  // Оплачений збіг не усуває неоднозначність назви іншого платежу.
  return hits.length===1&&paid.has(fixedOccurrenceKey(hits[0],hits[0].due))?[]:hits;
}
