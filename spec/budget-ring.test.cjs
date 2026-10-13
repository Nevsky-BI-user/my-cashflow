// v152: кільце бюджету (власник: «нормально по кольорах, а не по формі»). Палітра з 10 тонів: пара кольорів сегмента
// одного тону, тони попарно різняться не менше 25°; індекс категорії = місце в кільці (budAssign), тож сусіди в кільці,
// разом із замиканням останнього сегмента на перший, різняться не менше 40° за будь-якої кількості сегментів.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'..','index.html'),'utf8');

function ring(){
 const pick=re=>{const m=html.match(re);assert.ok(m,'не знайдено в index.html: '+re);return m[0];};
 return new Function([pick(/^const BUD_PAL=.*$/m),pick(/^const budHue=.*$/m),pick(/^function budAssign\(.*$/m),'return {BUD_PAL,budHue,budDh,budAssign};'].join('\n'))();
}
const dh=(a,b)=>{const x=Math.abs(a-b)%360;return Math.min(x,360-x)};

test('palette: 10 distinct tones, each gradient pair within one tone, tones at least 25 degrees apart',()=>{
 const {BUD_PAL,budHue}=ring();
 assert.equal(BUD_PAL.length,10);
 BUD_PAL.forEach((p,i)=>assert.ok(dh(budHue(p[0]),budHue(p[1]))<=3,'пара '+i+' поза тоном: '+p));
 let min=360;
 for(let i=0;i<10;i++)for(let j=i+1;j<10;j++)min=Math.min(min,dh(budHue(BUD_PAL[i][0]),budHue(BUD_PAL[j][0])));
 assert.ok(min>=25,'найближчі тони '+min.toFixed(1)+'°');
 // один жовтий або бурштиновий (тон 35-65°)
 assert.equal(BUD_PAL.filter(p=>{const h=budHue(p[0]);return h>=35&&h<=65}).length,1);
});

test('budAssign: ring neighbours (and last to first when the ring is closed) differ by at least 40 degrees for 1-13 segments',()=>{
 const {BUD_PAL,budHue,budAssign}=ring();
 const all=Array.from({length:13},(_,i)=>'c'+i);
 for(let n=1;n<=13;n++)for(const closed of [true,false]){
  const ids=all.slice(0,n),idx=budAssign(ids,all,closed);
  const hue=id=>budHue(BUD_PAL[idx[id]][0]);
  for(let k=0;k+1<n;k++)assert.ok(dh(hue(ids[k]),hue(ids[k+1]))>=40,`n=${n} closed=${closed}: ${ids[k]} і ${ids[k+1]}`);
  if(closed&&n>2)assert.ok(dh(hue(ids[n-1]),hue(ids[0]))>=40,`n=${n}: замикання ${ids[n-1]} і ${ids[0]}`);
  all.forEach(id=>assert.ok(idx[id]>=0&&idx[id]<10,'немає індексу '+id));
 }
});

test('budAssign: order of the ring, not of the category list, decides the colour; categories outside the ring follow',()=>{
 const {budAssign}=ring();
 const idx=budAssign(['b','a'],['a','b','c','d'],false);
 assert.deepEqual(idx,{b:0,a:1,c:2,d:3});
});
