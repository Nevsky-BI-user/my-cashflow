import { salaryChoices, salaryOccurrence } from './salary-payout.ts';
// Сума завжди з актуальних налаштувань, callback не містить суми.
export async function salaryOptions(sb:any,today:string){
 const [cfg,accounts]=await Promise.all([sb.from('salary_config').select('*').order('id').limit(1).maybeSingle(),sb.from('accounts').select('id,name,active,is_salary,mono_account_id').eq('active',true).eq('is_salary',true)]);
 if(cfg.error||accounts.error)throw new Error('salary configuration lookup failed');
 return {cfg:cfg.data,accounts:accounts.data||[],choices:salaryChoices(cfg.data,accounts.data||[],today)};
}
export function salaryKeyboard(choices:any[]){return {inline_keyboard:choices.map(p=>[{text:`✅ ${p.kind==='salary'?'Зарплата':'Аванс'} ${new Intl.NumberFormat('uk-UA').format(p.amount)} ₴ · ${p.accountName}`,callback_data:`sal:${p.kind==='salary'?'s':'a'}:${p.date}:${p.accountId}`}])};}
export type SalaryRecordResult={status:'invalid'}|{status:'awaiting'}|{status:'already';id:any}|{status:'choose';payout:any;rows:any[]}|{status:'saved';id:any;payout:any};
export async function recordSalary(sb:any,actorId:string,today:string,kind:string,date:string,accountId:string|number,existingId?:number):Promise<SalaryRecordResult>{
 const data=await salaryOptions(sb,today),p=salaryOccurrence(data.cfg,data.accounts,today,kind,date,accountId);
 if(!p||!data.choices.some(c=>c.date===date&&c.kind===kind&&String(c.accountId)===String(accountId)))return {status:'invalid'};
 const done=await sb.from('salary_payouts').select('transaction_id').eq('account_id',p.accountId).eq('kind',p.kind).eq('due_date',p.date).maybeSingle();
 if(done.error)throw new Error('salary occurrence lookup failed');if(done.data)return {status:'already',id:done.data.transaction_id};
 const shift=(n:number)=>new Date(Date.parse(date+'T00:00:00Z')+n*86400000).toISOString().slice(0,10);
 let query=sb.from('transactions').select('id,account_id,type,amount,date,source,transfer_id,salary_payouts(transaction_id)').eq('account_id',p.accountId).eq('type','income').eq('amount',p.amount).is('transfer_id',null).gte('date',shift(-3)).lte('date',today).order('id').limit(100);
 if(p.mono)query=query.eq('source','mono');
 const candidates=await query;if(candidates.error)throw new Error('salary income lookup failed');
 const rows=(candidates.data||[]).filter((t:any)=>!t.salary_payouts||(Array.isArray(t.salary_payouts)&&t.salary_payouts.length===0));
 if(existingId!=null&&!rows.some((t:any)=>Number(t.id)===existingId))return {status:'invalid'};
 if(existingId==null&&(rows.length>1||rows.some((t:any)=>t.date>shift(3))))return {status:'choose',payout:p,rows};
 const selected=existingId??rows[0]?.id??null;
 if(p.mono&&selected==null)return {status:'awaiting'};
 const result=await sb.rpc('record_salary_payout',{p_account_id:p.accountId,p_due_date:p.date,p_kind:p.kind,p_amount:p.amount,p_actor_id:actorId,p_existing_tx_id:selected});
 if(result.error)throw new Error('salary write failed');return {status:'saved',id:result.data,payout:p};
}
