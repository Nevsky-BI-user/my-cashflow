import { salaryChoices, salaryOccurrence } from './salary-payout.ts';
// Сума завжди з актуальних налаштувань, callback не містить суми.
export async function salaryOptions(sb:any,today:string){
 const [cfg,accounts]=await Promise.all([sb.from('salary_config').select('*').order('id').limit(1).maybeSingle(),sb.from('accounts').select('id,name,active,is_salary,mono_account_id').eq('active',true).eq('is_salary',true)]);
 if(cfg.error||accounts.error)throw new Error('salary configuration lookup failed');
 return {cfg:cfg.data,accounts:accounts.data||[],choices:salaryChoices(cfg.data,accounts.data||[],today)};
}
// v215 (власник: «ти автоматично вніс суму зарплати… а в мене не було можливості внести фактичну суму»): під кожною
// розрахованою виплатою кнопка «Інша сума»; фактичну суму бот просить окремим повідомленням (salx:, стан salary_amount)
export function salaryKeyboard(choices:any[]){return {inline_keyboard:choices.flatMap(p=>{
 const code=`${p.kind==='salary'?'s':'a'}:${p.date}:${p.accountId}`,label=p.kind==='salary'?'Зарплата':'Аванс';
 return [[{text:`✅ ${label} ${new Intl.NumberFormat('uk-UA').format(p.amount)} ₴ · ${p.accountName}`,callback_data:`sal:${code}`}],
  [{text:choices.length>1?`✏️ Інша сума: ${label} · ${p.accountName}`:'✏️ Інша сума',callback_data:`salx:${code}`}]];
})};}
// Кнопка під записаною виплатою: виправити суму (saled:, стан salary_edit)
export const salaryEditKeyboard=(txId:number|string)=>({inline_keyboard:[[{text:'✏️ Змінити суму',callback_data:`saled:${txId}`}]]});
// Фактична сума з повідомлення: «51234», «51 234,56», «51234.5 грн». Групи тисяч рівно по три цифри; інакше null.
export const SALARY_MAX=10000000;
export function parseSalaryAmount(text:string):number|null{
 const m=String(text||'').trim().match(/^((?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)(?:[.,]\d{1,2})?)\s*(?:₴|грн\.?)?$/i);
 if(!m)return null;
 const n=Number(m[1].replace(/[ \u00a0\u202f]/g,'').replace(',','.'));
 return Number.isFinite(n)&&n>0&&n<=SALARY_MAX?Math.round(n*100)/100:null;
}
export type SalaryEditResult={status:'invalid'}|{status:'missing'}|{status:'bank'}|{status:'saved';amount:number;old:number};
export type SalaryRecordResult={status:'invalid'}|{status:'awaiting'}|{status:'already';id:any}|{status:'choose';payout:any;rows:any[]}|{status:'saved';id:any;payout:any};
// amount: фактична сума, яку ввів користувач («Інша сума»); без неї сума з налаштувань. Перевірки дати, рахунку й дубліката ті самі.
export async function recordSalary(sb:any,actorId:string,today:string,kind:string,date:string,accountId:string|number,existingId?:number,amount?:number):Promise<SalaryRecordResult>{
 const data=await salaryOptions(sb,today),calc=salaryOccurrence(data.cfg,data.accounts,today,kind,date,accountId);
 if(!calc||!data.choices.some(c=>c.date===date&&c.kind===kind&&String(c.accountId)===String(accountId)))return {status:'invalid'};
 if(amount!=null&&!(Number.isFinite(amount)&&amount>0&&amount<=SALARY_MAX&&Math.abs(Math.round(amount*100)-amount*100)<1e-6))return {status:'invalid'};
 const p=amount!=null?{...calc,amount}:calc;
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
// Виправлення суми записаної виплати: лише дохід, привʼязаний до salary_payouts, і не з Monobank (банк знає суму сам).
// Пише RPC update_salary_payout_amount (міграція 20261112120000): тригер guard_salary_identity інакше забороняє зміну.
export async function editSalaryAmount(sb:any,actorId:string,txId:number,amount:number):Promise<SalaryEditResult>{
 if(!(Number.isFinite(amount)&&amount>0&&amount<=SALARY_MAX&&Math.abs(Math.round(amount*100)-amount*100)<1e-6))return {status:'invalid'};
 const tx=await sb.from('transactions').select('id,amount,type,source,transfer_id,salary_payouts(transaction_id)').eq('id',txId).maybeSingle();
 if(tx.error)throw new Error('salary transaction lookup failed');
 const linked=tx.data&&(Array.isArray(tx.data.salary_payouts)?tx.data.salary_payouts.length>0:!!tx.data.salary_payouts);
 if(!tx.data||!linked||tx.data.type!=='income'||tx.data.transfer_id!=null)return {status:'missing'};
 if(tx.data.source==='mono')return {status:'bank'};
 const result=await sb.rpc('update_salary_payout_amount',{p_tx_id:txId,p_amount:amount,p_actor_id:actorId});
 if(result.error)throw new Error('salary amount update failed');
 return {status:'saved',amount,old:Number(tx.data.amount)};
}
