// Єдина сума змінного бюджету: збережений місячний план і точні цілі копійки.
export function monthlyPeriodBudget(rows:any[],start:string,end:string,options:{legacyTargetCents?:number;legacyAllocations?:Record<string,number>}={}){
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
  segments.push({start:cursor,end:stop,month,sourceMonth,estimated,legacy:!row,targetCents:categories.reduce((n,c)=>n+c.totalCents,0)+unallocated,categories,unallocatedCents:unallocated});cursor=stop;
 }
 const categories=[...totals].sort(([a],[b])=>a.localeCompare(b)).map(([id,totalCents])=>({id,totalCents}));
 return {targetCents:categories.reduce((n,c)=>n+c.totalCents,0)+unallocatedCents,categories,unallocatedCents,segments,sourceMonths:[...new Set(segments.map(s=>s.sourceMonth).filter(Boolean))],estimated:segments.some(s=>s.estimated),legacy:segments.some(s=>s.legacy),covered};
}
