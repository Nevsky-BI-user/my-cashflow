const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const {pathToFileURL}=require('node:url');
const root=path.resolve(__dirname,'..'),html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const source=['getDow','adjSal','wdRange','wdMonth'].map(name=>html.match(new RegExp('const '+name+'=.*?;(?=const |function )'))[0]).join('\n')+'\n'+html.slice(html.indexOf('const salaryParts='),html.indexOf(';const nextPayout=',html.indexOf('const salaryParts='))+1);
const salaryParts=new Function(source+';return salaryParts')();
const errorSource=html.slice(html.indexOf('function salaryScheduleError('),html.indexOf('function SalSchedule('));
const validate=new Function(errorSource+';return salaryScheduleError')();
const base={rate:22000,split_day:15,advance_day:21,salary_day:6,advance_amount:11000,salary_amount:11000};
const cfg=(schedule,rate=22000)=>({...base,rate,rate_schedule:schedule});
const change=(effective_from,rate)=>({effective_from,rate});
const backend=()=>import(pathToFileURL(path.join(root,'supabase/functions/_shared/budget.ts')).href);

test('raise starts on earned days, not on salary paid next month',async()=>{
 const c=cfg([change('2026-11-01',42000)]),before=salaryParts(c,2026,9),nov=salaryParts(c,2026,10),dec=salaryParts(c,2026,11);
 assert.equal(before.advance.amount,11000);assert.equal(before.salary.amount,salaryParts(base,2026,9).salary.amount);
 assert.equal(nov.salary.amount,11000,'November salary still pays October');assert.equal(nov.advance.amount,20000);assert.equal(dec.salary.amount,22000);
 const {monthPayouts}=await backend();assert.deepEqual(monthPayouts(c,2026,11).map(p=>p.amount),[20000,11000]);
 assert.equal(c.rate,22000,'planning preserves the base rate');
});
test('mid-period raise uses actual weekdays and final rounding only',()=>{
 const c=cfg([change('2026-10-12',44000)]);
 assert.equal(salaryParts(c,2026,9).advance.amount,15000,'7 old weekdays and 4 new weekdays');
 assert.equal(salaryParts(c,2026,10).salary.amount,22000);
 assert.equal(salaryParts(cfg([change('2026-10-10',44000)]),2026,9).advance.amount,15000,'weekend start has no extra earning days');
});
test('fixed legacy amounts remain exact and transition proportionally',()=>{
 const c=cfg([change('2026-10-12',44000)],0);
 assert.equal(salaryParts(c,2026,8).advance.amount,11000);
 assert.equal(salaryParts(c,2026,9).advance.amount,15000);
 assert.equal(salaryParts({...base,rate:0,advance_amount:11000.125},2026,9).advance.amount,11000.125);
});
test('multiple rates and year rollover retain the earning-month boundary',()=>{
 const c=cfg([change('2027-01-01',46000),change('2026-12-16',23000)]);
 assert.equal(salaryParts(c,2027,0).salary.amount,12000,'January salary pays 12 December workdays at 23000 / 23');
 assert.equal(salaryParts(c,2026,11).advance.amount,10521.74,'December advance remains old rate');
 assert.equal(salaryParts(c,2027,0).advance.amount,24095.24);
});
test('scheduled forecast has full frontend, backend and independent Python parity',async()=>{
 const {financeProjection,monthPayouts}=await backend();
 const embed=new Function(html.split('/* CANONICAL MONTHLY PERIOD BUDGET */')[1].split('/* END CANONICAL MONTHLY PERIOD BUDGET */')[0]+html.split('/* CANONICAL FINANCE PROJECTION */')[1].split('/* END CANONICAL FINANCE PROJECTION */')[0]+';return financeProjection')();
 const inputs=[
  [cfg([change('2026-11-01',42000)]),'2026-10-01','2027-01-31'],
  [cfg([change('2026-10-12',44000)]),'2026-09-30','2026-12-31'],
  [cfg([change('2026-10-12',44000)],0),'2026-09-30','2026-12-31'],
  [cfg([change('2026-12-16',23000),change('2027-01-01',46000)]),'2026-12-01','2027-03-01'],
  [cfg([change('2028-02-15',44000),change('2028-02-29',66000)]),'2028-02-01','2028-03-31'],
 ].map(([salary,asof,through])=>({data:{accounts:[{id:1,kind:'debit',balance:1000,debt:0}],transactions:[],fixed:[],credits:[],categories:[],salary},options:{asof,through}}));
 const p=spawnSync(path.join(root,'.venv','Scripts','python.exe'),['scripts/budget_pool.py','--finance'],{cwd:root,input:JSON.stringify(inputs),encoding:'utf8',timeout:30000,maxBuffer:12*1024*1024});
 assert.equal(p.status,0,p.stderr);const oracle=JSON.parse(p.stdout);
 inputs.forEach((x,i)=>{const ts=financeProjection(x.data,x.options);assert.deepEqual(embed(x.data,x.options),ts,'embedded '+i);assert.deepEqual(ts,oracle[i],'Python '+i);
  for(const event of ts.events.filter(e=>e.kind==='payout')){const [y,m]=event.date.split('-').map(Number),match=monthPayouts(x.data.salary,y,m).find(p=>p.date===event.date&&Math.round(p.amount*100)===event.amountCents);assert.ok(match,JSON.stringify(event));const part=salaryParts(x.data.salary,y,m-1)[match.kind];assert.equal(Math.round(part.amount*100),event.amountCents);}
 });
});
test('schedule validation rejects malformed dates, duplicate dates and nonpositive or infinite rates',()=>{
 for(const value of [null,{},[change('2027-02-30',100)],[change('2027-13-01',100)],[change('2027-01-01',0)],[change('2027-01-01',-2)],[change('2027-01-01',Infinity)],[change('2027-01-01',100),change('2027-01-01',200)],[change('2026-10-29',100)]])assert.ok(validate(value,[],'2026-10-29'),JSON.stringify(value));
 assert.equal(validate([change('2027-01-01','10000')],[],'2026-10-29'),'');
});
test('applied entries cannot be edited or deleted; future entries remain editable',()=>{
 const old=[change('2026-10-01',25000),change('2026-12-01',30000)];
 assert.equal(validate([old[0],change('2027-01-01',35000)],old,'2026-10-29'),'');
 assert.ok(validate([change('2026-10-01',25001)],old,'2026-10-29'));
 assert.ok(validate([],old,'2026-10-29'));
});

test('current salary summary follows effective date rather than the base rate',()=>{
 const source=html.slice(html.indexOf('function salaryRateAt('),html.indexOf('function salaryScheduleError('));
 const activeRate=new Function(source+';return salaryRateAt')();
 const c=cfg([change('2026-11-01',42000),change('2027-01-01',46000)]);
 assert.equal(activeRate(c,'2026-10-31'),22000);
 assert.equal(activeRate(c,'2026-11-01'),42000);
 assert.equal(activeRate(c,'2026-12-31'),42000);
 assert.equal(activeRate(c,'2027-01-01'),46000);
 assert.equal(activeRate({...base,rate:0},'2027-01-01'),0);
});

test('failed schedule write retains the entire draft and permits retry',async()=>{
 const draft={...base,rate_schedule:[change('2026-11-01',42000)]},lock={current:false},draftKey={current:Symbol()},editor={current:draft};
 let calls=0,error='',stored=null,closed=false,reject=true;
 const query={eq(){return this;},select(){return this;},single(){return reject?Promise.reject(Error('offline')):Promise.resolve({data:{id:7,...draft}});}};
 const context={salDraft:draft,salDraftKey:draftKey,salEditor:editor,salSaveLock:lock,salSavedId:{current:null},salCfg:{id:7},salNow:base,
  syncController:{current:{}},syncAuth:{current:'synthetic'},salParse:d=>({fields:d}),
  sb:{from(){return{update(fields){calls++;assert.deepEqual(fields.rate_schedule,draft.rate_schedule);return query;}};}},
  setSalErr:v=>{error=v;},setSalSaving:()=>{},setSalCfg:v=>{stored=v;},setShowSalary:v=>{closed=!v;},requestFinance:()=>Promise.resolve()};
 const start=html.indexOf('const saveSalary=')+'const saveSalary='.length,end=html.indexOf(';const salPrevM=',start);
 const save=new Function(...Object.keys(context),'return '+html.slice(start,end))(...Object.values(context));
 await save();
 assert.match(error,/offline/);assert.equal(lock.current,false);assert.equal(editor.current,draft);assert.deepEqual(draft.rate_schedule,[change('2026-11-01',42000)]);assert.equal(stored,null);assert.equal(closed,false);
 reject=false;await save();assert.equal(calls,2);assert.equal(error,'');assert.equal(closed,true);assert.deepEqual(stored.rate_schedule,draft.rate_schedule);
});
