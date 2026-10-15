"""Синтетичні відкладені записи перевіряють справжні handlers і повторні рендери React."""
from helpers import ROOT, check


def _source(name, end):
    text = (ROOT / 'index.html').read_text(encoding='utf-8')
    start = text.index('const ' + name + '=') + len(name) + 7
    return text[start:text.index(end, start)].strip().removesuffix(';')


MOUNT = r"""({kind,code})=>{
 const host=document.createElement('div');host.id='save-integrity-probe';
 host.style.cssText='position:fixed;inset:0;z-index:99999;background:white;color:black;padding:20px';document.body.append(host);
 const mock=window.__saveIntegrity={calls:[],pending:[],failRefresh:false,syncAuth:{current:'synthetic'},syncController:{current:{}}};
 const sb={from(table){const call={table};const q={};for(const key of ['insert','update','eq','select','single'])q[key]=(...args)=>{call[key]=args;return q};q.then=(yes,no)=>{mock.calls.push(call);return new Promise((resolve,reject)=>mock.pending.push({resolve,reject})).then(yes,no)};return q}};
 const factory=new Function('ctx','with(ctx){return ('+code+')}');
 function Probe(){
  const [draft,setDraft]=React.useState(kind==='goal'?{id:null,name:'Synthetic goal',target:1234,sort:0}:kind==='pay'?{id:null,name:'Synthetic payment',amount:'1234',day:12,kind:'fixed'}:{rate:1234});
  const [busy,setBusy]=React.useState(false),[err,setErr]=React.useState(''),[done,setDone]=React.useState(false),[cfg,setCfg]=React.useState(null);
  const lock=React.useRef(false),saved=React.useRef(null),editor=React.useRef(draft),draftKey=React.useRef(Symbol()),photo=React.useRef(null);
  const changeDraft=v=>{const next=typeof v==='function'?v(editor.current):v;editor.current=next;setDraft(next)};
  const reload=async strict=>{if(strict!==true)throw Error('strict refresh missing');if(mock.failRefresh)throw Error('synthetic refresh offline')};
  const ctx={sb,syncAuth:mock.syncAuth,syncController:mock.syncController,requestFinance:()=>Promise.resolve({status:'updated'}),session:{user:{id:'synthetic'}},[kind==='salary'?'salEditor':kind+'Editor']:editor,[kind==='salary'?'salDraftKey':kind+'DraftKey']:draftKey};
  if(kind==='goal')Object.assign(ctx,{goalEdit:draft,goalSaveLock:lock,goalSavedDraft:saved,goalPhotoPending:photo,goalBusy:busy,goalLocal:false,setGoalErr:setErr,setGoalBusy:setBusy,setGoalEdit:v=>{changeDraft(v);if(v===null)setDone(true)},loadGoals:reload});
  if(kind==='pay')Object.assign(ctx,{payEdit:draft,paySaveLock:lock,paySavedDraft:saved,paySaving:busy,setPayErr:setErr,setPaySaving:setBusy,setPayEdit:changeDraft,loadCredits:reload,loadFixed:reload,payDone:()=>setDone(true)});
  if(kind==='salary')Object.assign(ctx,{salDraft:draft,salSaveLock:lock,salSavedId:saved,salCfg:cfg,salNow:{},salParse:d=>({fields:d}),setSalErr:setErr,setSalSaving:setBusy,setSalCfg:setCfg,setShowSalary:v=>setDone(!v)});
  const save=factory(ctx);
  return React.createElement('div',null,
   React.createElement('input',{'data-probe-draft':true,value:draft?(draft.name||draft.rate):'',onChange:e=>changeDraft(Object.assign({},draft,kind==='salary'?{rate:e.target.value}:{name:e.target.value}))}),
   React.createElement('button',{'data-probe-save':true,disabled:!!busy,onClick:()=>{save();save()}},'Save twice'),
   React.createElement('div',{'data-probe-error':true},err),React.createElement('div',{'data-probe-done':true},String(done)));
 }
 mock.root=ReactDOM.createRoot(host);mock.root.render(React.createElement(Probe));
}"""


def delayed_write_recovery(page):
    for kind, name, end in [('goal', 'saveGoal', '\nconst deleteGoal='),
                            ('pay', 'savePay', ';const delPay='),
                            ('salary', 'saveSalary', ';const salPrevM=')]:
        page.evaluate(MOUNT, {'kind': kind, 'code': _source(name, end)})
        button = page.locator('[data-probe-save]')
        draft = page.locator('[data-probe-draft]')
        expected = '4321' if kind == 'salary' else 'Changed synthetic draft'
        draft.fill(expected)
        button.click()
        page.wait_for_function('window.__saveIntegrity.calls.length===1')
        check(button.is_disabled(), kind + ': pending write must disable retry')
        page.evaluate("window.__saveIntegrity.pending.shift().reject(Error('synthetic network offline'))")
        page.wait_for_function("document.querySelector('[data-probe-error]').textContent.includes('network offline')")
        check(draft.input_value() == expected, kind + ': rejected write lost draft')
        check(button.is_enabled(), kind + ': rejection did not unlock')
        if kind != 'salary':
            page.evaluate('window.__saveIntegrity.failRefresh=true')
        button.click()
        page.wait_for_function('window.__saveIntegrity.calls.length===2')
        page.evaluate("kind=>window.__saveIntegrity.pending.shift().resolve({data:kind==='pay'?[{id:17}]:{id:17}})", kind)
        if kind != 'salary':
            page.wait_for_function("document.querySelector('[data-probe-error]').textContent.includes('Збережено')")
            check(draft.input_value() == expected, kind + ': refresh failure lost draft')
            page.evaluate('window.__saveIntegrity.failRefresh=false')
            button.click()
            page.wait_for_function('window.__saveIntegrity.calls.length===3')
            calls = page.evaluate('window.__saveIntegrity.calls')
            check(sum('insert' in c for c in calls) == 2 and 'update' in calls[-1], kind + ': retry duplicated saved row')
            page.evaluate("kind=>window.__saveIntegrity.pending.shift().resolve({data:kind==='pay'?[{id:17}]:{id:17}})", kind)
        page.wait_for_function("document.querySelector('[data-probe-done]').textContent==='true'")
        page.evaluate("()=>{window.__saveIntegrity.root.unmount();document.querySelector('#save-integrity-probe').remove();delete window.__saveIntegrity}")


CHECKS = [
    ('save-integrity delayed reject/refresh/retry desktop', 'desktop', delayed_write_recovery),
    ('save-integrity delayed reject/refresh/retry mobile', 'mobile', delayed_write_recovery),
]
