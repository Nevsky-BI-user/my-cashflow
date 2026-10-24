// Чисті правила ручного вибору зобовʼязання; архів доступний тільки для минулих дат.
import { fixedOccurrence, fixedOccurrenceKey } from './fixedmatch.ts';
export type PaymentKind = 'f' | 'c' | 'a';
export function paymentDates(kind:PaymentKind,item:any,reference:string,today:string,paid:Set<string>):string[] {
  const dates:string[]=[];
  if(kind==='c'){
    const first=Number(item.start_year)*12+Number(item.start_month),count=Number(item.total_payments),day=Number(item.payment_day);
    if(!Number.isInteger(first)||!Number.isInteger(count)||count<1||count>1200||!Number.isInteger(day)||day<1||day>31)return dates;
    for(let i=0;i<count;i++){
      const k=first+i,y=Math.floor(k/12),m=k%12;
      const due=`${y}-${String(m+1).padStart(2,'0')}-${String(Math.min(day,new Date(Date.UTC(y,m+1,0)).getUTCDate())).padStart(2,'0')}`;
      if(!paid.has(String(item.id)+'|'+due.slice(0,7)))dates.push(due);
    }
  }else{
    if(kind==='a'&&item.active!==false||kind==='f'&&item.active===false)return dates;
    const year=Number(reference.slice(0,4)),seen=new Set<string>(),start=new Date(Date.UTC(year-1,0,1)),end=new Date(Date.UTC(year+3,0,1));
    // Попередній рік доступний для простроченої оплати; ще два роки — для оплати наперед.
    for(let i=0;i<1462;i++){
      const d=new Date(start);d.setUTCDate(d.getUTCDate()+i);
      if(d>=end)break;
      const due=fixedOccurrence({...item,active:true},d.toISOString().slice(0,10));
      if(!due||due<start.toISOString().slice(0,10)||due>=end.toISOString().slice(0,10)||kind==='a'&&due>today)continue;
      const key=fixedOccurrenceKey(item,due);
      if(!seen.has(key)&&!paid.has(key)){seen.add(key);dates.push(due);}
    }
  }
  // Найближчий період показуємо першим; за однакової відстані — минулий.
  const referenceTime=new Date(reference.slice(0,10)+'T00:00:00Z').getTime();
  return dates.sort((a,b)=>Math.abs(new Date(a+'T00:00:00Z').getTime()-referenceTime)-Math.abs(new Date(b+'T00:00:00Z').getTime()-referenceTime)||a.localeCompare(b));
}
export function paymentPage<T>(items:T[],page:number,size=8):{items:T[];page:number;pages:number}{
  const pages=Math.max(1,Math.ceil(items.length/size)),safe=Math.max(0,Math.min(Number.isSafeInteger(page)?page:0,pages-1));
  return {items:items.slice(safe*size,(safe+1)*size),page:safe,pages};
}
