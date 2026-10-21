import { monthPayouts, payoutBudget } from './budget.ts';
// Порада лише з фактичних власних коштів у день виплати; прогнозну зарплату не додаємо.
export function repaymentAdvice(data:any,projection:any,sourceId:number|string,today:string){
 const base={date:today,sourceId,availableCents:0,items:[] as {accountId:number|string;name:string;amountCents:number}[],reason:null as string|null};
 const cfg=data.salary;if(!cfg)return {...base,reason:'no_salary_config'};
 const [y,m]=today.split('-').map(Number);
 const payouts=[];for(let k=-1;k<=1;k++){const d=new Date(Date.UTC(y,m-1+k,1));payouts.push(...monthPayouts(cfg,d.getUTCFullYear(),d.getUTCMonth()+1));}
 if(!payouts.some(p=>p.date===today&&p.amount>0))return {...base,reason:'not_payout_day'};
 const accounts=projection.snapshot.accounts||[],source=accounts.find((a:any)=>String(a.id)===String(sourceId));
 if(!source||source.active===false)return {...base,reason:'source_unavailable'};
 const targets=accounts.filter((a:any)=>a.active!==false&&a.kind==='credit'&&String(a.id)!==String(sourceId)&&a.debtCents>0).sort((a:any,b:any)=>String(a.debt_month||'').localeCompare(String(b.debt_month||''))||String(a.id).localeCompare(String(b.id)));
 const debt=targets.reduce((n:number,a:any)=>n+a.debtCents,0),own=Math.max(0,Number(projection.snapshot.positiveOwnCents)||0);
 const current=(projection.periods||[]).find((p:any)=>p.basis==='current'),end=current?.end||projection.currentPeriod?.end||today;
 const cashObligations=(projection.events||[]).filter((e:any)=>e.date>=today&&e.date<end&&(e.kind==='fee'||(e.kind==='mandatory'&&e.creditEligible!==true&&e.funding!=='credit')));
 const reserve=cashObligations.reduce((n:number,e:any)=>n+Math.max(0,Number(e.amountCents)||0),0);
 const manual=cfg.budget_manual==null||cfg.budget_manual===''?null:Math.max(0,Math.round(Number(cfg.budget_manual)*100));
 const monthly=projection.currentPeriod?.monthlyBudget;
 const periodBudget=monthly?.covered?Math.max(0,projection.currentPeriod.remainingTargetCents):manual;
 const plan=payoutBudget(own,reserve,debt,0,true,periodBudget);
 // Призначені цьому банку платежі мають лишитися на картці-джерелі.
 const sourceReserve=cashObligations.filter((e:any)=>{
  if(e.date<today||e.date>=end)return false;
  if(e.kind==='fee')return e.accountId==null||String(e.accountId)===String(sourceId);
  if(e.kind!=='mandatory')return false;
  const id=String(e.occurrenceId||e.id||'').match(/^(fixed|installment):([^:]+):/);
  const item=id?(id[1]==='fixed'?data.fixed||[]:data.credits||[]).find((r:any)=>String(r.id)===id[2]):null;
  const bank=item&&(item.bank||item.source||item.src);
  return !bank||!source.bank||bank===source.bank;
 }).reduce((n:number,e:any)=>n+Math.max(0,Number(e.amountCents)||0),0);
 let left=Math.min(Math.max(0,(Number(source.balanceCents)||0)-sourceReserve),plan.repayCents);base.availableCents=left;
 for(const a of targets){const n=Math.min(left,a.debtCents);if(n>0)base.items.push({accountId:a.id,name:a.name,amountCents:n});left-=n;}
 return base;
}

export function repaymentAdviceText(advice:ReturnType<typeof repaymentAdvice>){
 if(advice.reason)return '';
 const money=(n:number)=>new Intl.NumberFormat('uk-UA',{maximumFractionDigits:2}).format(n/100)+' ₴';
 return advice.items.length?'На погашення кредиток після обовʼязкових платежів і бюджету: '+money(advice.availableCents)+'\n'+advice.items.map(i=>'· '+i.name+': '+money(i.amountCents)).join('\n'):'Після резерву обовʼязкових платежів і бюджету вільних власних коштів для погашення немає.';
}
