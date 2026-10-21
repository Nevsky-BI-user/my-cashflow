import { monthPayouts } from './budget.ts';
// Сусідній номінальний місяць може мати виплату останнього дня поточного.
export function nearbyPayouts(cfg:any,date:string){
 if(!cfg)return [];
 const [y,m]=date.split('-').map(Number),all=[];
 for(let k=-1;k<=1;k++){const d=new Date(Date.UTC(y,m-1+k,1));all.push(...monthPayouts(cfg,d.getUTCFullYear(),d.getUTCMonth()+1));}
 return [...new Map(all.filter(p=>p.amount>0).map(p=>[p.kind+'|'+p.date,p])).values()];
}
export function salaryChoices(cfg:any,accounts:any[],today:string){
 if(!cfg||!/^\d{4}-\d{2}-\d{2}$/.test(today))return [];
 const payouts=nearbyPayouts(cfg,today).filter(p=>p.date<=today).sort((a,b)=>b.date.localeCompare(a.date));
 const latest=payouts[0]?.date;if(!latest)return [];
 return payouts.filter(p=>p.date===latest).flatMap(payout=>accounts.filter(a=>a.active!==false&&a.is_salary===true).map(a=>({accountId:a.id,accountName:a.name,kind:payout.kind,date:payout.date,amount:payout.amount,mono:!!a.mono_account_id})));
}
export function salaryOccurrence(cfg:any,accounts:any[],today:string,kind:string,date:string,accountId:string|number){
 if(!cfg||!/^\d{4}-\d{2}-\d{2}$/.test(date)||date>today)return null;
 const p=nearbyPayouts(cfg,date).find(p=>p.date===date&&p.kind===kind),a=accounts.find(a=>a.active!==false&&a.is_salary===true&&String(a.id)===String(accountId));
 return p&&a?{accountId:a.id,accountName:a.name,kind:p.kind,date:p.date,amount:p.amount,mono:!!a.mono_account_id}:null;
}
