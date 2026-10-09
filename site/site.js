'use strict';
const toggle=document.querySelector('.mobile-toggle');
const nav=document.getElementById('nav');
if(toggle && nav){
  toggle.addEventListener('click',()=>{const active=toggle.getAttribute('aria-expanded')==='true';toggle.setAttribute('aria-expanded',String(!active));nav.classList.toggle('open',!active)});
  nav.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{toggle.setAttribute('aria-expanded','false');nav.classList.remove('open')}));
}
fetch('./version.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('Unavailable');return r.json()}).then(d=>{
 if(typeof d.version==='string' && /^\d+\.\d+\.\d+$/.test(d.version))document.querySelectorAll('[data-star-version]').forEach(el=>{el.textContent=d.version});
}).catch(()=>{});
