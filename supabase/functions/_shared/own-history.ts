// Відновлюємо власні кошти з урахуванням погашення боргу й переплати на кредитці.
export function ownCashDeltas(rawAccounts:any[],txs:any[],effectiveAccounts:any[],asof:string):Record<string,number>{
 const cents=(n:any)=>Math.round((Number(n)||0)*100),date=(t:any)=>String(t.date||t.created_at||'').slice(0,10),key=(t:any)=>t.account_id==null?'':String(t.account_id);
 const seen=new Set<string>(),rows=(txs||[]).filter(t=>{if(date(t)>asof||date(t).length!==10)return false;if(t.id==null)return true;const id=String(t.id);if(seen.has(id))return false;seen.add(id);return true;});
 const out:Record<string,number>={},add=(d:string,n:number)=>{out[d]=(out[d]||0)+n;},signed=(t:any)=>t.type==='income'?cents(t.amount):t.type==='expense'?-cents(t.amount):0;
 for(const t of rows.filter(t=>key(t)===''))add(date(t),signed(t));
 for(const raw of rawAccounts||[]){
  if(raw.active===false||raw.id==null)continue;
  const list=rows.filter(t=>key(t)===String(raw.id));
  if(raw.kind!=='credit'){for(const t of list)add(date(t),signed(t));continue;}
  const stamp=Date.parse(raw.balance_updated_at||'');
  if(!raw.mono_account_id&&Number.isFinite(stamp)){
   let own=Math.max(0,cents(raw.balance)),debt=Math.max(0,cents(raw.debt));
   for(const t of list.filter(t=>Date.parse(t.created_at||'')>stamp).sort((a,b)=>Date.parse(a.created_at)-Date.parse(b.created_at)||String(a.id??'').localeCompare(String(b.id??'')))){
    const amount=Math.max(0,cents(t.amount)),before=own;
    if(t.type==='income'){const paid=Math.min(debt,amount);debt-=paid;own+=amount-paid;}
    else if(t.type==='expense'){const used=Math.min(own,amount);own-=used;debt+=amount-used;}
    add(date(t),own-before);
   }
  }else if(raw.mono_account_id){
   const effective=(effectiveAccounts||[]).find(a=>String(a.id)===String(raw.id))||raw;
   let net=(effective.balanceCents??cents(effective.balance))-(effective.debtCents??cents(effective.debt));
   const daily:Record<string,number>={};for(const t of list)daily[date(t)]=(daily[date(t)]||0)+signed(t);
   for(const d of Object.keys(daily).sort().reverse()){const before=net-daily[d];add(d,Math.max(0,net)-Math.max(0,before));net=before;}
  }
 }
 return out;
}
export function ownCashSeries(rawAccounts:any[],txs:any[],effectiveAccounts:any[],anchorCents:number,fromIso:string,toIso:string){
 const deltas=ownCashDeltas(rawAccounts,txs,effectiveAccounts,toIso),points=[];let value=anchorCents;
 for(let d=toIso,g=0;d>=fromIso&&g<20000;d=new Date(Date.parse(d+'T00:00:00Z')-86400000).toISOString().slice(0,10),g++){points.push({date:d,cents:value});value-=deltas[d]||0;}
 return points.reverse();
}
