/* V6: reusable per-visual zoom and pan controls. No analytics API changes. */
(() => {
 'use strict';
 const targets='.dashboard-grid > .card';
 function setup(card){
  if(card.querySelector('.visual-zoom-controls'))return;
  const target=card.querySelector('.chart-wrap, .plot-map, .heatmap');
  if(!target)return;
  const heading=card.querySelector('.chart-head');
  const controls=document.createElement('div');controls.className='visual-zoom-controls';
  const label=document.createElement('label');
  const id='zoom-'+(target.id||target.querySelector('[id]')?.id||Math.random().toString(36).slice(2));
  const caption=document.createElement('span');caption.textContent='Zoom';
  const range=document.createElement('input');range.id=id;range.type='range';
  range.min='75';range.max='225';range.step='25';range.value='100';
  range.setAttribute('aria-label','Zoom '+(heading?.querySelector('h2')?.textContent||'visualization'));
  const percent=document.createElement('output');percent.htmlFor=id;percent.textContent='100%';
  const reset=document.createElement('button');reset.type='button';reset.className='zoom-reset';
  reset.textContent='Reset';reset.setAttribute('aria-label','Reset visualization zoom to 100 percent');
  label.append(caption,range,percent);controls.append(label,reset);
  heading?.insertAdjacentElement('afterend',controls);
  const viewport=document.createElement('div');viewport.className='zoom-viewport';
  const stage=document.createElement('div');stage.className='zoom-stage';
  target.parentNode.insertBefore(viewport,target);viewport.append(stage);stage.append(target);
  const apply=()=>{
   const scale=Number(range.value)/100;
   stage.style.transform=`scale(${scale})`;
   // Reserve scrollable space for enlarged graphics and maps.
   stage.style.width='100%';
   stage.style.height='100%';
   percent.textContent=`${range.value}%`;
   viewport.classList.toggle('zoom-enlarged',scale>1);
  };
  range.addEventListener('input',apply);
  reset.addEventListener('click',()=>{range.value='100';viewport.scrollTo({top:0,left:0});apply();});
  apply();
 }
 function start(){document.querySelectorAll(targets).forEach(setup);}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);
 else start();
})();
