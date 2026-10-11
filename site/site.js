'use strict';
const toggle=document.querySelector('.mobile-toggle');
const nav=document.getElementById('nav');
if(toggle && nav){
  const setOpen=open=>{toggle.setAttribute('aria-expanded',String(open));nav.classList.toggle('open',open)};
  toggle.addEventListener('click',()=>setOpen(toggle.getAttribute('aria-expanded')!=='true'));
  nav.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>setOpen(false)));
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape' && toggle.getAttribute('aria-expanded')==='true'){setOpen(false);toggle.focus()}
  });
}
// Shows which source version this page was built from. It is not a claim about which release is downloadable.
fetch('./version.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('Unavailable');return r.json()}).then(d=>{
 if(typeof d.version==='string' && /^\d+\.\d+\.\d+$/.test(d.version))document.querySelectorAll('[data-star-version]').forEach(el=>{el.textContent=d.version});
}).catch(()=>{});
