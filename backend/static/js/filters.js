/* Capability-aware, persistent selections. Unsupported options never appear as active choices. */
(() => {
 const $ = id => document.getElementById(id);
 let bounds = {}, initialized = false;
 // Artist identity is session-only. Ignore old localStorage defaults from V3/V4.
 const privateKeys=new Set(['artist','artist_name']);
 const storage=key=>privateKeys.has(key)?sessionStorage:localStorage;
 const save=(key,value)=>{try{storage(key).setItem('spotify_v5_'+key,value);}catch(e){}};
 const read=(key,fallback)=>{try{return storage(key).getItem('spotify_v5_'+key)??fallback;}catch(e){return fallback;}};
 const scopeKey=()=>page==='weekly'?'weekly_scope':'scope';
 const iso=d=>d.toISOString().slice(0,10);
 const page=document.body.dataset.page;
 const dated=()=>{
  const p=$('period')?.value||'all';
  if(p==='custom') return {start:$('start-date')?.value||'',end:$('end-date')?.value||''};
  if(p!=='all' && bounds.latest){
   const e=new Date(String(bounds.latest).slice(0,10)+'T12:00:00Z');
   const s=new Date(e);s.setUTCDate(s.getUTCDate()-Number(p)+1);
   return {start:iso(s),end:iso(e)};
  }
  return {};
 };
 function get(){
  const p=new URLSearchParams(),country=$('country')?.value,scope=page==='weekly'?'weekly':($('scope')?.value||'daily');
  if(country)p.set('country',scope==='yearly'&&page==='global'?'GLOBAL':country);
  if($('scope'))p.set('scope',scope);
  const artist=read('artist','');if(artist)p.set('artist_id',artist);
  const track=$('track')?.value;if(track)p.set('track_id',track);
  const period=$('period')?.value||'all';p.set('period',period);
  const {start,end}=dated();if(start)p.set('start',start);if(end)p.set('end',end);
  return p;
 }
 function setup(onChange){
  if(initialized)return;initialized=true;
  const fromURL=new URLSearchParams(location.search);
  const period=$('period');if(period){
   const wanted=fromURL.get('period')||read('period','all');
   if([...period.options].some(x=>x.value===wanted))period.value=wanted;
   $('custom-range').hidden=period.value!=='custom';
   if(fromURL.get('start'))$('start-date').value=fromURL.get('start');
   if(fromURL.get('end'))$('end-date').value=fromURL.get('end');
   period.addEventListener('change',()=>{
    save('period',period.value);$('custom-range').hidden=period.value!=='custom';
    if(period.value!=='custom')onChange();
   });
   $('apply-dates')?.addEventListener('click',()=>{
    if($('end-date')?.value && $('start-date')?.value > $('end-date').value){
     alert('End date must follow start date.');return;
    }
    onChange();
   });
  }
  const scope=$('scope');if(scope){
   const previous=page==='weekly'?'weekly':((fromURL.get('scope')||read('scope','daily'))==='weekly'?'daily':(fromURL.get('scope')||read('scope','daily')));
   scope.value=[...scope.options].some(o=>o.value===previous)?previous:(page==='weekly'?'weekly':'daily');
   scope.addEventListener('change',()=>{save(scopeKey(),scope.value);onChange();});
  }
  $('country')?.addEventListener('change',()=>{save('country_'+page,$('country').value);onChange();});
  $('reset-filters')?.addEventListener('click',()=>{
   if(period){period.value='all';save('period','all');$('custom-range').hidden=true;
    $('start-date').value='';$('end-date').value='';}
   if(scope){scope.value=page==='weekly'?'weekly':'daily';save(scopeKey(),scope.value);}
   save('country_'+page,page==='artist'?'ALL':page==='regional'?'PH':'GLOBAL');onChange();
  });
  const disclose=$('filter-disclosure');if(disclose){
   disclose.open=read('filter_panel','open')==='open';
   disclose.addEventListener('toggle',()=>save('filter_panel',disclose.open?'open':'closed'));
  }
 }
 function setBounds(v){bounds=v||{};for(const id of ['start-date','end-date']){
  const e=$(id);if(e){e.min=String(bounds.earliest||'').slice(0,10);e.max=String(bounds.latest||'').slice(0,10);}
 }}
 function sync(data){
  const select=$('country'),scope=$('scope');
  if(scope){
   const previous=scope.value;
   scope.replaceChildren();for(const x of data.scopes||[]){scope.add(new Option(x.label,x.value));}
   scope.value=[...scope.options].some(o=>o.value===previous)?previous:(page==='weekly'?'weekly':'daily');
   if(scope.selectedIndex<0)scope.selectedIndex=0;
   save(scopeKey(),scope.value);
   const wrap=$('scope-filter');if(wrap)wrap.hidden=scope.options.length<=1;
  }
  if(select){
   const prev=read('country_'+page,'') || new URLSearchParams(location.search).get('country') || (page==='artist'?'ALL':page==='regional'?'PH':'GLOBAL');
   select.replaceChildren();for(const x of data.countries||[]){
    select.add(new Option(x.name===x.code?x.code:`${x.name} (${x.code})`,x.code));
   }
   let wanted=prev;
   if(scope?.value==='yearly' && page==='global')wanted='GLOBAL';
   if(![...select.options].some(o=>o.value===wanted)){
    wanted=page==='regional' && [...select.options].some(o=>o.value==='PH')?'PH':select.options[0]?.value||'';
   }
   if(wanted)select.value=wanted;
   save('country_'+page,wanted);
   const wrap=$('country-filter');if(wrap)wrap.hidden=(scope?.value==='yearly' && page==='global') || select.options.length===0;
  }
  const msg=$('filter-note');if(msg){
   msg.hidden=page==='weekly'||page==='global';
   const note=(data.notes||[]).join(' ');
   msg.textContent=(data.countries||[]).length?note:'No chart observations match the selected artist and date range. Clear the artist selection or reset the dates.';
  }
  const summary=$('filter-summary-meta');if(summary){
   summary.textContent=(select?.value||'No market')+(scope && scope.options.length>1?' · '+scope.selectedOptions[0]?.text:'');
  }
  return !!select?.value;
 }
 window.SpotifyFilters={setup,get,bounds:setBounds,save,read,sync};
})();
