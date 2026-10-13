// v152: кільце бюджету (власник: «нормально по кольорах, а не по формі»). Палітра з 10 тонів: пара кольорів сегмента
// одного тону, тони попарно різняться не менше 25°.
// v153 (власник: «стабільний колір за категорією, не за місцем у періоді»): тон категорії сталий (budStable за id),
// сусіди в кільці різняться не менше 40° завдяки порядку сегментів (budRing); бот малює ті самі кольори в тому самому порядку.
// v155 (власник: «як в епл», рішення координатора 13.10): 10 системних кольорів Apple, пласко, слот = [світла тема, темна тема].
// Замість «усі пари ≥ 25°»: а) усі пари Lab CIE76 ≥ 15 в обох темах; б) пʼять головних слотів (5, 7, 2, 0, 3) попарно ≥ 30° за тоном
// в обох темах; в) сусіди кільця ≥ 40°, як було; г) теплі тони (20-70°) попарно Lab ≥ 25 в обох темах; червоного (мінус) у палітрі немає.
// г) замість «рівно один жовтий або бурштиновий (тон 35-65°)» v152: мета того правила була, щоб у палітрі не було двох схожих
// жовто-бурштинових тонів. Помаранчевий Apple (35-36,5°) і жовтий (48-50°) різняться на Lab 32,4/32,7, тобто далі, ніж будь-яка
// пара під загальним порогом 15; тому правило тепер вимагає для теплих тонів більшого розрізнення (25), а не рахує їх кількість.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const html=fs.readFileSync(path.join(__dirname,'..','index.html'),'utf8');

function ring(){
 const pick=re=>{const m=html.match(re);assert.ok(m,'не знайдено в index.html: '+re);return m[0];};
 return new Function([pick(/^const BUD_PAL=.*$/m),pick(/^const BUD_OTH=.*$/m),pick(/^let BUD_DARK=.*$/m),pick(/^function budPal\(.*$/m),pick(/^function hexLab\(.*$/m),pick(/^const budHue=.*$/m),pick(/^function budStable\(.*$/m),pick(/^function budRing\(.*$/m),pick(/^function budDonutData\(.*$/m),
  'return {BUD_PAL,BUD_OTH,BUD_NONE,budPal,budHue,budDh,budStable,budRing,budDonutData,hexLab,setIdx:function(x){BUD_IDX=x},setDark:function(d){BUD_DARK=d}};'].join('\n'))();
}
const dh=(a,b)=>{const x=Math.abs(a-b)%360;return Math.min(x,360-x)};
// детермінований генератор: однакові набори на кожному запуску
const rng=seed=>()=>{seed=(seed*1103515245+12345)%2147483648;return seed/2147483648};

test('palette: 10 Apple colours, light and dark of a slot in one tone, Lab distance at least 15, main slots 30 degrees apart, no red',()=>{
 const {BUD_PAL,budHue,hexLab}=ring();
 assert.equal(BUD_PAL.length,10);
 BUD_PAL.forEach((p,i)=>assert.ok(dh(budHue(p[0]),budHue(p[1]))<=3,'світлий і темний слота '+i+' різних тонів: '+p));
 const lab=(a,b)=>{const x=hexLab(a),y=hexLab(b);return Math.hypot(x[0]-y[0],x[1]-y[1],x[2]-y[2])};
 for(const t of [0,1]){
  const th=t?'темна':'світла';
  // а) усі пари помітно різні
  let min=1e9,at='';
  for(let i=0;i<10;i++)for(let j=i+1;j<10;j++){const d=lab(BUD_PAL[i][t],BUD_PAL[j][t]);if(d<min){min=d;at=i+' і '+j}}
  assert.ok(min>=15,th+': найближчі слоти '+at+', Lab '+min.toFixed(1));
  // б) пʼять головних слотів (найбільші живі частки) далеко за тоном
  const MAIN=[5,7,2,0,3];let mh=360;
  for(let i=0;i<5;i++)for(let j=i+1;j<5;j++)mh=Math.min(mh,dh(budHue(BUD_PAL[MAIN[i]][t]),budHue(BUD_PAL[MAIN[j]][t])));
  assert.ok(mh>=30,th+': головні слоти ближче за 30°: '+mh.toFixed(1)+'°');
  // червоний лише для мінусу й перевитрати
  assert.ok(!BUD_PAL.some(p=>/^#(FF3B30|FF453A)$/i.test(p[t])),th+': червоний у палітрі категорій');
  // г) теплі тони (20-70°: бурштин, помаранчевий, жовтий, коричневий) не плутаються між собою: попарно Lab ≥ 25
  const warm=BUD_PAL.map((p,k)=>[k,budHue(p[t])]).filter(q=>q[1]>=20&&q[1]<=70);
  assert.ok(warm.length>=1,th+': немає теплого тону');
  for(let i=0;i<warm.length;i++)for(let j=i+1;j<warm.length;j++){const d=lab(BUD_PAL[warm[i][0]][t],BUD_PAL[warm[j][0]][t]);
   assert.ok(d>=25,th+': теплі слоти '+warm[i][0]+' і '+warm[j][0]+' ('+warm[i][1].toFixed(1)+'°, '+warm[j][1].toFixed(1)+'°) схожі: Lab '+d.toFixed(1))}
 }
});

test('budStable: the colour of a category depends on its id only, not on the period, the list order or other categories',()=>{
 const {budStable}=ring();
 const a=budStable(['1','2','13','20','27']),b=budStable(['27','5','1','20']);
 assert.deepEqual([a['1'],a['2'],a['13'],a['20'],a['27']],[0,1,2,9,6]);
 for(const id of ['1','20','27'])assert.equal(a[id],b[id],'колір '+id+' залежить від набору');
 // демо-id (нечислові) за місцем серед нечислових у списку
 assert.deepEqual(budStable(['food','cafe','x1']),{food:0,cafe:1,x1:2});
});

test('budRing: neighbours differ by at least 40 degrees (closed ring: last to first too) whenever such an order exists; grey segments go last',()=>{
 const {budRing,budDh}=ring();
 const r=rng(153);
 const perms=a=>a.length<2?[a]:a.flatMap((x,i)=>perms(a.slice(0,i).concat(a.slice(i+1))).map(p=>[x].concat(p)));
 const valid=(ord,idx,closed)=>ord.every((s,k)=>k+1>=ord.length?(!closed||ord.length<2||budDh(idx[s.id],idx[ord[0].id])>=40):budDh(idx[s.id],idx[ord[k+1].id])>=40);
 let found=0,none=0;
 for(let t=0;t<400;t++){
  const n=1+Math.floor(r()*8),grey=r()<0.4;
  const ids=[...new Set(Array.from({length:n},()=>String(1+Math.floor(r()*27))))];
  const idx={};ids.forEach(id=>idx[id]=(Number(id)-1)%10);
  const col=ids.map((id,i)=>({id,fact:100-i}));const segs=grey?col.concat([{id:'__other',fact:1}]):col;
  const out=budRing(segs,idx);
  assert.deepEqual(out.map(s=>s.id).slice().sort(),segs.map(s=>s.id).slice().sort(),'не перестановка');
  if(grey)assert.equal(out[out.length-1].id,'__other','сірі не в кінці');
  const oc=out.filter(s=>s.id.slice(0,2)!=='__');
  const can=perms(col).some(p=>valid(p,idx,!grey));
  if(can){found++;assert.ok(valid(oc,idx,!grey),'порядок без 40°: '+oc.map(s=>s.id+':'+idx[s.id]).join(','));if(perms(col).some(p=>p[0]===col[0]&&valid(p,idx,!grey)))assert.equal(oc[0].id,col[0].id,'першим не найбільший')}
  else{none++;assert.deepEqual(out,segs,'немає порядку: має лишитись спадний')}
 }
 assert.ok(found>300&&none>0,'набори не показові: є порядок '+found+', немає '+none);
});

test('bot ring = app ring: same segments, same order, same colour per category (bot picture is light)',async()=>{
 const A=ring();
 const ch=await import(pathToFileURL(path.resolve(__dirname,'../supabase/functions/_shared/bot-charts.ts')).href);
 assert.deepEqual(ch.BUD_PAL,A.BUD_PAL,'палітра бота інша');
 A.setDark(false);
 const r=rng(7);
 for(let t=0;t<200;t++){
  const n=2+Math.floor(r()*14);
  const ids=[...new Set(Array.from({length:n},()=>String(1+Math.floor(r()*27))))];
  const rows=ids.map(id=>({id,name:'к'+id,fact:Math.round(r()*r()*500000)/100,plan:0,over:false,near:false}));
  if(r()<0.3)rows.push({id:'__none',name:'Без категорії',fact:Math.round(r()*30000)/100,plan:0,over:false,near:false,noPlan:true});
  rows.sort((a,b)=>b.fact-a.fact);
  const idx=A.budStable(ids);A.setIdx(idx);
  const d=A.budDonutData(rows);const app=A.budRing(d.segs,idx).map(s=>[s.id,s.pct,(A.budPal(s.id,null)||A.BUD_OTH)[0]]);
  const bot=ch.donutSegments(rows).segs.map(s=>[s.id,s.pct,s.color]);
  assert.deepEqual(bot,app,'набір '+t);
 }
});
