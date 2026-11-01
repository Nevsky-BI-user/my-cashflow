// Ручні суми категорій зберігаються; налаштування змінюють лише основу активного плану.
export function normalizeMonthlyBudgets(rows:any[],data:any,asof:string,through:string=asof){
 const iso=(d:Date)=>d.toISOString().slice(0,10),date=(y:number,m:number,d:number)=>iso(new Date(Date.UTC(y,m,d))),index=(s:string)=>Number(s.slice(0,4))*12+Number(s.slice(5,7))-1;
 const num=(v:any)=>Number(v)||0,cents=(v:any)=>Math.round(num(v)*100),current=asof.slice(0,7)+'-01',cfg=data.salary;
 if(!cfg)return rows||[];
 const sorted=(rows||[]).slice().sort((a,b)=>String(a.month_start).localeCompare(String(b.month_start))),out=sorted.filter(r=>r.month_start<current);
 const last=Math.max(index(through),...sorted.filter(r=>r.month_start>=current).map(r=>index(r.month_start)));
 const work=(y:number,m:number,lo:number,hi:number)=>{let n=0;for(let d=lo;d<=hi;d++){const w=new Date(Date.UTC(y,m,d)).getUTCDay();if(w!==0&&w!==6)n++;}return n;};
 const earned=(y:number,m:number,lo:number,hi:number,fixed:number)=>{const total=work(y,m,1,new Date(Date.UTC(y,m+1,0)).getUTCDate()),wd=work(y,m,lo,hi),schedule=(cfg.rate_schedule||[]).filter((x:any)=>x.effective_from<=date(y,m,hi)&&num(x.rate)>0).slice().sort((a:any,b:any)=>String(a.effective_from).localeCompare(String(b.effective_from)));if(!schedule.length)return Math.round((num(cfg.rate)>0?num(cfg.rate)/(total||1)*wd:fixed)*100);let weighted=0,fixedDays=0;for(let d=lo;d<=hi;d++){const w=new Date(Date.UTC(y,m,d)).getUTCDay();if(w===0||w===6)continue;let rate=num(cfg.rate);for(const x of schedule){if(x.effective_from>date(y,m,d))break;rate=num(x.rate);}if(rate>0)weighted+=rate;else fixedDays++;}return Math.round((weighted/(total||1)+(wd?fixedDays/wd*fixed:0))*100);};
 const shifted=(y:number,m:number,d:number)=>{const dt=new Date(Date.UTC(y,m,d)),w=dt.getUTCDay();dt.setUTCDate(dt.getUTCDate()+(w===6?-1:w===0?1:0));return iso(dt);};
 for(let k=index(current);k<=last;k++){
  const y=Math.floor(k/12),m=k%12,start=date(y,m,1),end=date(y,m+1,1),source=sorted.filter(r=>r.month_start<=start).pop();
  if(!source)continue;if(source.income_basis_cents==null){if(source.month_start===start)out.push(source);continue;}
  let income=0;for(let j=k-1;j<=k+1;j++){const yy=Math.floor(j/12),mm=j%12,split=Math.round(num(cfg.split_day))||15,prev=new Date(Date.UTC(yy,mm,0)),py=prev.getUTCFullYear(),pm=prev.getUTCMonth();for(const [when,amount] of [[shifted(yy,mm,num(cfg.advance_day)),earned(yy,mm,1,split,num(cfg.advance_amount))],[shifted(yy,mm,num(cfg.salary_day)),earned(py,pm,split+1,prev.getUTCDate(),num(cfg.salary_amount))]] as [string,number][]){if(when>=start&&when<end)income+=amount;}}
  const items:any[]=source.month_start===start&&start===current?(source.mandatory_items||[]).filter((x:any)=>x.date<asof).map((x:any)=>({...x})):[],cut=start===current&&source.month_start===start?asof:start;
  const add=(kind:string,id:any,when:string,name:string,amount:any,estimated=false)=>{if(when<cut||when>=end)return;items.push({key:kind+':'+id+':'+when,date:when,name:String(name||'Платіж').slice(0,240),amount_cents:cents(amount),kind,estimated});};
  (data.fixed||[]).forEach((f:any,i:number)=>{if(f.active===false||f.type==='income')return;const ended=(s:string)=>f.end_date&&s>String(f.end_date).slice(0,10);if(f.period==='week'){for(let d=1;d<=new Date(Date.UTC(y,m+1,0)).getUTCDate();d++){const dt=new Date(Date.UTC(y,m,d)),s=iso(dt);if(((dt.getUTCDay()+6)%7+1)===Number(f.weekday)&&!ended(s))add('fixed',f.id??i+1,s,f.name,f.amount,!!f.variable);}}else if(f.period!=='year'||Number(f.month_of_year)===m+1){const s=date(y,m,Math.min(num(f.day_of_month),new Date(Date.UTC(y,m+1,0)).getUTCDate()));if(!ended(s))add('fixed',f.id??i+1,s,f.name,f.amount,!!f.variable);}});
  (data.credits||[]).forEach((c:any,i:number)=>{if(c.active===false)return;const first=num(c.start_year??c.sy)*12+num(c.start_month??c.sm),count=num(c.total_payments??c.total);if(k<first||k>=first+count)return;add('installment',c.id??i+1,date(y,m,Math.min(num(c.payment_day??c.day),new Date(Date.UTC(y,m+1,0)).getUTCDate())),String(c.name||'')+' (розстрочка)',c.monthly_amount??c.amount);});
  items.sort((a,b)=>a.date.localeCompare(b.date)||a.name.localeCompare(b.name));
  const rawTotal=num(source.settings_total_cents??source.total_cents)+income-num(source.income_basis_cents),total=Math.max(0,rawTotal),mandatory=items.reduce((n,x)=>n+x.amount_cents,0),allocated=Object.values(source.allocations||{}).reduce((n:number,v)=>n+num(v),0),deficit=Math.max(0,mandatory+allocated-rawTotal);
  const copy={...source};if(source.month_start!==start){delete copy.id;delete copy.created_at;delete copy.updated_at;}
  out.push({...copy,month_start:start,total_cents:total,income_basis_cents:income,mandatory_items:items,allocations:{...source.allocations},settings_deficit_cents:deficit,settings_total_cents:rawTotal});
 }
 return out;
}
