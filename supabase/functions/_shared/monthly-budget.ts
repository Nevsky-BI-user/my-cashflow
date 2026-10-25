// Єдина сума змінного бюджету: збережений місячний план і точні цілі копійки.
export function monthlyPeriodBudget(rows:any[],start:string,end:string,options:{legacyTargetCents?:number;legacyAllocations?:Record<string,number>;categories?:any[]}={}){
 const savingsCategoryIds=(options.categories||[]).filter(c=>!c.is_income&&!c.isIncome&&c.type!=='income'&&(String(c.id)==='savings'||String(c.name||'').normalize('NFKC').trim().toLocaleLowerCase('uk-UA')==='заощадження')).map(c=>String(c.id));
 const saving=new Set(savingsCategoryIds),debtCategoryIds=(options.categories||[]).filter(c=>['debt_card','debt_installment'].includes(c.budget_role)).map(c=>String(c.id)),debt=new Set(debtCategoryIds);
 const parse=(s:string)=>new Date(s+'T00:00:00Z'),iso=(d:Date)=>d.toISOString().slice(0,10),days=(a:string,b:string)=>Math.round((+parse(b)-+parse(a))/86400000);
 const valid=(n:any)=>{const v=Number(n);if(!Number.isSafeInteger(v)||v<0)throw new RangeError('Invalid monthly budget cents');return v;};
 const prefix=(n:number,a:number,b:number,d:number)=>Number(BigInt(n)*BigInt(b)/BigInt(d)-BigInt(n)*BigInt(a)/BigInt(d));
 const saved=(rows||[]).slice().sort((a,b)=>String(a.month_start).localeCompare(String(b.month_start))),totals=new Map<string,number>(),segments:any[]=[];
 const span=days(start,end);if(span<0||!Number.isFinite(span))throw new RangeError('Invalid budget period');
 let cursor=start,unallocatedCents=0,covered=false;
 while(cursor<end){
  const dt=parse(cursor),month=cursor.slice(0,7)+'-01',next=iso(new Date(Date.UTC(dt.getUTCFullYear(),dt.getUTCMonth()+1,1))),stop=next<end?next:end,D=days(month,next),a=days(month,cursor),b=days(month,stop);
  const row=saved.filter(r=>String(r.month_start)<=month).pop();let allocation:Record<string,number>,unallocated:number,sourceMonth:string|null=null,estimated=false;
  if(row){covered=true;sourceMonth=String(row.month_start);estimated=sourceMonth!==month;
   const mandatory=(row.mandatory_items||[]).reduce((n:number,x:any)=>n+valid(x.amount_cents),0),pool=Math.max(0,valid(row.total_cents)-mandatory);
   allocation=Object.fromEntries(Object.entries(row.allocations||{}).map(([id,n])=>[id,valid(n)]));const used=Object.values(allocation).reduce((n,v)=>n+v,0);if(used>pool)throw new RangeError('Monthly allocation exceeds variable pool');
   unallocated=prefix(pool-used,a,b,D);allocation=Object.fromEntries(Object.entries(allocation).map(([id,n])=>[id,prefix(n,a,b,D)]));
  }else{
   const total=valid(options.legacyTargetCents||0),raw=options.legacyAllocations||{},used=Object.values(raw).reduce((n,v)=>n+valid(v),0);
   if(used>total)throw new RangeError('Legacy allocation exceeds target');
   allocation=Object.fromEntries(Object.entries(raw).map(([id,n])=>[id,prefix(valid(n),days(start,cursor),days(start,stop),span)]));unallocated=prefix(total-used,days(start,cursor),days(start,stop),span);
  }
  const categories=Object.entries(allocation).sort(([a],[b])=>a.localeCompare(b)).map(([id,totalCents])=>({id,totalCents}));
  categories.forEach(c=>totals.set(c.id,(totals.get(c.id)||0)+c.totalCents));unallocatedCents+=unallocated;
  const savingsTargetCents=row?categories.filter(c=>saving.has(c.id)).reduce((n,c)=>n+c.totalCents,0):0,debtBudgetTargetCents=row?categories.filter(c=>debt.has(c.id)).reduce((n,c)=>n+c.totalCents,0):0,targetCents=categories.reduce((n,c)=>n+c.totalCents,0)+unallocated;
  segments.push({start:cursor,end:stop,month,sourceMonth,estimated,legacy:!row,targetCents,savingsTargetCents,debtBudgetTargetCents,spendableTargetCents:targetCents-savingsTargetCents-debtBudgetTargetCents,categories,unallocatedCents:unallocated});cursor=stop;
 }
 const categories=[...totals].sort(([a],[b])=>a.localeCompare(b)).map(([id,totalCents])=>({id,totalCents}));
 const targetCents=categories.reduce((n,c)=>n+c.totalCents,0)+unallocatedCents,savingsTargetCents=segments.reduce((n,s)=>n+s.savingsTargetCents,0),debtBudgetTargetCents=segments.reduce((n,s)=>n+s.debtBudgetTargetCents,0);
 return {targetCents,savingsTargetCents,debtBudgetTargetCents,spendableTargetCents:targetCents-savingsTargetCents-debtBudgetTargetCents,savingsCategoryIds,debtCategoryIds,categories,unallocatedCents,segments,sourceMonths:[...new Set(segments.map(s=>s.sourceMonth).filter(Boolean))],estimated:segments.some(s=>s.estimated),legacy:segments.some(s=>s.legacy),covered};
}

// Заощадження є умовним залишком після боргів, а не резервом фактичних коштів.
export function monthlySavingsReserve(rows:any[],categories:any[],transactions:any[],asof:string){
 const start=asof.slice(0,7)+'-01',d=new Date(start+'T00:00:00Z'),end=new Date(Date.UTC(d.getUTCFullYear(),d.getUTCMonth()+1,1)).toISOString().slice(0,10),plan=monthlyPeriodBudget(rows,start,end,{categories});
 const ids=new Set(plan.savingsCategoryIds),seen=new Set<string>();let factCents=0;
 for(const t of transactions||[]){const date=String(t.date||t.created_at||'').slice(0,10),id=t.id==null?null:String(t.id);if(id!=null){if(seen.has(id))continue;seen.add(id);}if(t.type!=='expense'||t.transfer_id!=null||t.fixed_id!=null||t.credit_id!=null||date<start||date>=end||date>asof||!ids.has(String(t.category_id)))continue;const n=Number(t.amount);if(Number.isFinite(n)&&n>0)factCents+=Math.round(n*100);}
 const plannedCents=plan.covered?plan.savingsTargetCents:0;return{plannedCents,factCents,reserveCents:0,provisional:true,sourceMonths:plan.sourceMonths,estimated:plan.estimated};
}
// Авторозподіл змінює лише системні резерви боргу; факт рахунків не змінюється.
export function autoDebtAllocations(row:any,categories:any[],capacity:{cardDebtCents:number;installmentRemainingCents:number;installments?:{creditId:string;date:string;amountCents:number}[]},priority:string[]=['debt_card','debt_installment']){
 const nonnegative=(v:any)=>{const n=Number(v);if(!Number.isSafeInteger(n)||n<0)throw new RangeError('Invalid debt budget cents');return n;};
 const allocations:Record<string,number>={...row.allocations},roles=['debt_card','debt_installment'],ids:Record<string,string>={};
 for(const c of categories||[])if(roles.includes(c.budget_role)){const id=String(c.id);if(ids[c.budget_role])throw new Error('Duplicate debt budget role');ids[c.budget_role]=id;delete allocations[id];}
 const savingsIds=(categories||[]).filter(c=>!c.is_income&&!c.isIncome&&c.type!=='income'&&(String(c.id)==='savings'||String(c.name||'').normalize('NFKC').trim().toLocaleLowerCase('uk-UA')==='заощадження')).map(c=>String(c.id));for(const id of savingsIds)delete allocations[id];
 const mandatory=(row.mandatory_items||[]).reduce((n:number,x:any)=>n+nonnegative(x.amount_cents),0),mandatoryInstallmentTotalCents=(row.mandatory_items||[]).filter((x:any)=>x.kind==='installment').reduce((n:number,x:any)=>n+nonnegative(x.amount_cents),0);
 const outstanding=new Map<string,number>();for(const x of capacity.installments||[]){const key=String(x.creditId)+'|'+x.date;outstanding.set(key,(outstanding.get(key)||0)+nonnegative(x.amountCents));}
 const mandatoryInstallmentCents=capacity.installments==null?mandatoryInstallmentTotalCents:(row.mandatory_items||[]).filter((x:any)=>x.kind==='installment').reduce((n:number,x:any)=>{const key=String(x.key).split(':')[1]+'|'+String(x.date),amount=Math.min(nonnegative(x.amount_cents),outstanding.get(key)||0);outstanding.set(key,(outstanding.get(key)||0)-amount);return n+amount;},0);
 let left=Math.max(0,nonnegative(row.total_cents)-mandatory-Object.values(allocations).reduce((n,v)=>n+nonnegative(v),0));
 // Пріоритет незмінний: кредитки, потім умовні заощадження; перед заощадженнями також достроково погашаємо розстрочки.
 if(ids.debt_card){const n=Math.min(left,nonnegative(capacity.cardDebtCents));allocations[ids.debt_card]=n;left-=n;}
 if(ids.debt_installment){const n=Math.min(left,Math.max(0,nonnegative(capacity.installmentRemainingCents)-mandatoryInstallmentCents));allocations[ids.debt_installment]=n;left-=n;}
 const savingsCents=savingsIds.length?left:0;if(savingsIds.length){allocations[savingsIds[0]]=savingsCents;left=0;}
 return{row:{...row,allocations},allocations,debtCardCents:allocations[ids.debt_card]||0,debtInstallmentCents:allocations[ids.debt_installment]||0,unallocatedCents:left,savingsCents,savingsProvisional:true,mandatoryInstallmentCents,mandatoryInstallmentTotalCents};
}
