/* Dashboard controller: parameterized JSON APIs, persistent dedication and live chart rendering. */
(() => {
 const $=id=>document.getElementById(id), page=document.body.dataset.page;
 const filter=()=>window.SpotifyFilters;
 const charts=()=>window.SpotifyCharts;
 const hasRows=rows=>Array.isArray(rows)&&rows.length>0;
 const hasMeasure=(rows,...fields)=>hasRows(rows)&&rows.some(r=>
    fields.some(key=>r?.[key]!==null&&r?.[key]!==undefined&&Number.isFinite(Number(r[key]))));
 const hasMappedMeasure=(rows,field)=>hasRows(rows)&&rows.some(r=>
    r.iso3 && r[field]!==null && r[field]!==undefined && Number.isFinite(Number(r[field])));
 const chartPanel=id=>$(id)?.closest('.card');
 const showPanel=(id,hasData)=>{const panel=chartPanel(id);if(panel)panel.hidden=!hasData;};

 let controller=null,version=0;
 const value=(n,type)=>{
  if(n===null||n===undefined||n==='')return 'N/A';
  if(type==='text')return String(n);
  const number=Number(n);if(!Number.isFinite(number))return String(n);
  if(type==='percent')return `${number>0?'+':''}${number.toFixed(2)}%`;
  if(type==='compact')return new Intl.NumberFormat('en',{notation:'compact',maximumFractionDigits:2}).format(number);
  if(type==='decimal')return number.toFixed(2);
  return new Intl.NumberFormat('en',{maximumFractionDigits:0}).format(number);
 };
 const content=(node,s)=>{if(node)node.textContent=s;};

 // Status colors reflect documented thresholds, rather than treating every large total as good.
 const kpiTone=(item)=>{
  const status=String(item.status||'').trim().toLowerCase();
  if(/^(rising|growing|increasing|strong|fast|high)$/.test(status))return 'positive';
  if(/^(falling|declining|decreasing|weak|slow|low)$/.test(status))return 'negative';
  if(/^(stable|moderate|normal|unchanged)$/.test(status))return 'neutral';
  const label=String(item.label||'').toLowerCase(),number=Number(item.value);
  if(Number.isFinite(number)&&/growth|momentum|percent change|change in country share|rank change|position improvement/.test(label))
   return number>0?'positive':number<0?'negative':'neutral';
  return 'default';
 };
 const pictograms={
  streams:'M4 17V9m5 8V5m5 12v-7m5 7V3',
  rank:'M4 17h16M7 13l4-4 3 3 5-6',
  entry:'M12 3v18m-7-7 7 7 7-7M5 6h14',
  growth:'M3 17l6-6 4 4 8-9M16 6h5v5',
  artist:'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m14-17a4 4 0 1 1-8 0 4 4 0 0 1 8 0Zm2 8a4 4 0 0 1 4 4v3',
  globe:'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm-10 10h20M12 2c-4 4-4 16 0 20M12 2c4 4 4 16 0 20',
  label:'M3 4h10l8 8-9 9-9-9V4Zm5 4h.01',
  days:'M7 3v4m10-4v4M3 10h18M5 5h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z',
  streak:'M12 22c5 0 8-4 8-9 0-4-3-7-4-9-1 4-3 5-4 7-1-3-3-5-4-6-1 5-4 8-4 12 0 3 4 5 8 5Z',
  fallback:'M4 19h16M6 15l5-5 4 3 4-6'
 };
 const iconName=(label)=>{
  const text=String(label||'').toLowerCase();
  if(/label/.test(text))return 'label';
  if(/listener|artist volume/.test(text))return 'artist';
  if(/country|market share|reach|diversity/.test(text))return 'globe';
  if(/consecutive|streak/.test(text))return 'streak';
  if(/longevity|days|date/.test(text))return 'days';
  if(/entry|entries/.test(text))return 'entry';
  if(/growth|momentum|change|improvement|climbing/.test(text))return 'growth';
  if(/rank|strength|position/.test(text))return 'rank';
  if(/stream|volume/.test(text))return 'streams';
  return 'fallback';
 };
 const metricIcon=(label)=>{
  const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');
  svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('fill','none');
  svg.setAttribute('stroke','currentColor');svg.setAttribute('stroke-width','1.55');
  svg.setAttribute('stroke-linecap','round');svg.setAttribute('stroke-linejoin','round');
  svg.setAttribute('aria-hidden','true');svg.classList.add('metric-icon-svg');
  const path=document.createElementNS(ns,'path');path.setAttribute('d',pictograms[iconName(label)]);
  svg.append(path);return svg;
 };

 async function get(url,signal){const r=await fetch(url,{signal,headers:{Accept:'application/json'}});let j;
  try{j=await r.json();}catch(e){throw new Error(`Invalid response from ${url}`);}
  if(!r.ok)throw new Error(j.error||`HTTP ${r.status}`);return j;}
 function metrics(items,d){const root=$('metrics');root.replaceChildren();
  const replacements={
   global:[['Observed Chart Dates',(d.history||[]).length]],
   regional:[['Charted Record Labels',(d.labels||[]).length]],
   velocity:[['Tracks in Comparison',(d.tracks||[]).length]],
   artist:[['Observed Stream Dates',(d.daily||[]).length],['Charted Albums',(d.albums||[]).length]]
  };
  const cards=[...(items||[])];
  for(const [label,val] of replacements[page]||[]){
   if(cards.filter(i=>i.value!==null&&i.value!==undefined&&i.value!=='').length>=4)break;
   if(val>0&& !cards.some(x=>x.label===label))cards.push({label,value:val,
     note:'Supplementary metric calculated from current filtered observations'});
  }

  const invalid=cards.filter(item=>item.value===null||item.value===undefined||item.value==='');
  const available=cards.filter(item=>item.value!==null&&item.value!==undefined&&item.value!=='').slice(0,4);
  const details=$('unavailable-metrics'),list=$('unavailable-list');
  if(details&&list){details.hidden=!invalid.length;list.replaceChildren();
    const count=$('unavailable-count');if(count)count.textContent=`(${invalid.length})`;
    for(const item of invalid){const li=document.createElement('li');li.textContent=item.label+(item.note?`: ${item.note}`:' (no verified data)');list.append(li);}}
  for(const item of available){
  const card=document.createElement('article');card.className='metric-card';card.dataset.tone=kpiTone(item);
  const heading=document.createElement('div');heading.className='metric-heading';
  const title=document.createElement('div');title.className='metric-label';content(title,item.label);
  const symbol=document.createElement('span');symbol.className='metric-icon';symbol.append(metricIcon(item.label));
  heading.append(title,symbol);
  const number=document.createElement('div');number.className='metric-value';content(number,value(item.value,item.format));
  card.append(heading,number);if(item.status){const tag=document.createElement('span');tag.className='metric-status';content(tag,item.status);card.append(tag);}
  if(item.note){const hint=document.createElement('div');hint.className='metric-note';content(hint,item.note);card.append(hint);}root.append(card);
 }}
 function table(id,data,cols){const root=$(id);if(!root)return;root.replaceChildren();
  if(!data?.length){const p=document.createElement('p');p.className='no-rows';p.textContent='No matching chart observations.';root.append(p);return;}
  const tab=document.createElement('table'),thead=document.createElement('thead'),tr=document.createElement('tr');
  for(const [,label] of cols){const th=document.createElement('th');th.textContent=label;tr.append(th);}thead.append(tr);
  const tbody=document.createElement('tbody');for(const item of data){const tr=document.createElement('tr');for(const [key,,type] of cols){
    const td=document.createElement('td');td.textContent=value(item[key],type||'text');tr.append(td);}tbody.append(tr);}
  tab.append(thead,tbody);root.append(tab);
 }
 function warning(notes){const el=$('caveats');el.hidden=!(notes||[]).length;if(!el.hidden)el.textContent=notes.join(' ');}
 function updateTracks(arr,selected){const select=$('track');if(!select)return;const desired=selected?String(selected):select.value;
  select.replaceChildren();for(const item of arr||[]){if(item.track_id){select.add(new Option(item.name,String(item.track_id)));}}
  if([...select.options].some(o=>o.value===desired))select.value=desired;
 }
 function draw(d){metrics(d.metrics,d);warning(d.caveats);
  if(page==='artist')setArtistView(true);

  if(page==='global'){
    const isAlbum=d.scope==='weekly';
    const header=$('main-chart')?.closest('.card')?.querySelector('h2');
    if(header)header.textContent=isAlbum?'Top 10 Weekly Albums by Best Rank':'Top 10 Tracks by Total Streams';
    if(isAlbum){charts().bars('main-chart',d.top,'name','best_rank','Best weekly rank',true);
      charts().line('secondary-chart',d.history,[{key:'albums',label:'Weekly charted albums'}]);}
    else{charts().bars('main-chart',d.top,'name','streams','Total streams',true);
      charts().line('secondary-chart',d.history,[{key:'streams',label:'Daily streams'}]);}
    charts().calendar('calendar-heatmap',isAlbum?[]:d.history);
    charts().doughnut('third-chart',d.status);
    showPanel('main-chart',hasMeasure(d.top,isAlbum?'best_rank':'streams'));
    showPanel('secondary-chart',hasMeasure(d.history,isAlbum?'albums':'streams'));
    showPanel('calendar-heatmap',!isAlbum&&hasMeasure(d.history,'streams'));
    showPanel('third-chart',hasMeasure(d.status,'value'));
    table('main-table',d.top,isAlbum?[['name','Album'],['best_rank','Best Rank','integer'],['weeks','Weeks','integer']]:
     [['name','Track'],['streams','Total Streams','compact'],['best_rank','Best Rank','integer']]);
  }else if(page==='regional'){
    charts().bars('main-chart',d.top_artists,'name','avg_rank','Average rank',true);
    charts().stacked('secondary-chart',d.labels);
    charts().line('third-chart',d.compare,[{key:'local_streams',label:'Country #1 streams'},
      {key:'global_streams',label:'Same track GLOBAL streams'}]);
    charts().map('regional-map',d.shares,d.artist_mode?'artist_streams':'share_pct',d.country);
    showPanel('main-chart',hasMeasure(d.top_artists,'avg_rank'));
    showPanel('secondary-chart',hasMeasure(d.labels,'streams'));
    showPanel('third-chart',hasMeasure(d.compare,'local_streams','global_streams'));
    showPanel('regional-map',hasMappedMeasure(d.shares,d.artist_mode?'artist_streams':'share_pct'));
    table('main-table',d.top_artists,[['name','Artist'],['avg_rank','Average Rank','decimal'],['chart_days','Observations','integer']]);
    table('secondary-table',d.labels,[['label_name','Label'],['streams','Streams','compact']]);
  }else if(page==='velocity'){
    charts().scatter('main-chart',d.scatter);
    charts().boxplot('label-box',d.box);
    charts().histogram('third-chart',d.histogram);
    charts().line('fourth-chart',d.rank||[],[{key:'chart_rank',label:'Current rank'},
      {key:'previous_rank',label:'Previous rank'}],true);
    updateTracks(d.tracks,d.selected_track);
    showPanel('main-chart',hasMeasure(d.scatter,'entry_rank','peak_rank'));
    showPanel('label-box',hasMeasure(d.box,'days'));
    showPanel('third-chart',hasMeasure(d.histogram,'count'));
    showPanel('fourth-chart',hasMeasure(d.rank,'chart_rank'));
    table('main-table',d.tracks,[['name','Track / Album'],['entry_rank','Entry Rank','integer'],
      ['peak_rank','Peak Rank','integer'],['improvement','Rank Improvement','integer'],['days','Chart Longevity','integer']]);
  }else if(page==='artist'){
    content($('selected-artist-name'),d.artist?`${d.artist.artist_name||'Unknown artist'}`:'No artist found');
    charts().map('artist-map',d.reach,'streams');
    charts().line('main-chart',d.daily,[{key:'streams',label:'Credited daily streams'}]);
    charts().bars('secondary-chart',d.albums,'name','weeks','Weeks on chart',true);
    showPanel('artist-map',hasMappedMeasure(d.reach,'streams'));
    showPanel('main-chart',hasMeasure(d.daily,'streams'));
    showPanel('secondary-chart',hasMeasure(d.albums,'weeks'));
    table('main-table',d.reach,[['code','Country'],['chart_days','Chart Days','integer'],['streams','Credited Streams','compact']]);
  }
  if(d.period?.to)content($('period-note'),`${String(d.period.from).slice(0,10)} to ${String(d.period.to).slice(0,10)}`);
 }
 function setArtistView(selected){
  if(page!=='artist')return;
  const empty=$('artist-empty-state'),grid=$('dashboard-visuals'),context=$('selected-artist-name');
  if(empty)empty.hidden=selected;
  if(grid)grid.hidden=!selected;
  if(context)context.hidden=!selected;
  if($('metrics'))$('metrics').hidden=!selected;
  if($('detail-explorer')?.closest('.detail-section'))$('detail-explorer').closest('.detail-section').hidden=!selected;
  if($('filter-disclosure'))$('filter-disclosure').hidden=!selected;
  if($('unavailable-metrics'))$('unavailable-metrics').hidden=!selected;
  if($('caveats'))$('caveats').hidden=!selected;
  if(!selected){
    $('metrics')?.replaceChildren();charts()?.clearAll();
    const name=$('selected-artist-name');if(name)name.textContent='';
    document.dispatchEvent(new Event('spotify:availability-empty'));
  }
 }
 function applyChartVisibility(){
  const grid=$('dashboard-visuals')||document.querySelector('.dashboard-grid');
  if(!grid)return;
  const visible=[...grid.querySelectorAll(':scope > .card:not([hidden])')].length;
  let note=$('chart-availability-note');
  if(!note){note=document.createElement('p');note.id='chart-availability-note';
   note.className='chart-availability-note';grid.after(note);}
  note.hidden=visible>0 || (page==='artist' && !filter().read('artist',''));
  if(!note.hidden)note.textContent='No chart observations match the selected filters. Try another available date or market.';
  grid.classList.toggle('single-visual',visible===1);
 }
 async function refresh(){
  if(controller)controller.abort();controller=new AbortController();const signal=controller.signal;
  if(page==='artist'&&!filter().read('artist','')){
   ++version;setArtistView(false);
   content($('loading'),'');content($('error'),'');$('error').hidden=true;
   return;
  }
  if(page==='artist')setArtistView(true);
  const call=++version;
  content($('error'),'');$('error').hidden=true;content($('loading'),'Updating available filters…');
  try{
   const options=await get(`/api/filter-options/${page}/?${filter().get().toString()}`,signal);
   if(call!==version)return;
   if(!filter().sync(options)){
    $('metrics').replaceChildren();charts().clearAll();
    $('loading').textContent='No matching chart observations. Clear the artist selection or reset dates.';
    $('unavailable-metrics').hidden=true;
    const label=$('filter-summary-meta');if(label)label.textContent='No matching data';
    document.dispatchEvent(new Event('spotify:availability-empty'));
    if(page==='artist')setArtistView(true);
    document.querySelectorAll('.dashboard-grid > .card').forEach(x=>x.hidden=true);
    applyChartVisibility();
    return;
   }
   const query=filter().get();content($('loading'),'Updating dashboard…');
   const data=await get(`/api/${page}/?${query.toString()}`,signal);
   if(call!==version)return;
   if(data.selection_required){setArtistView(false);return;}
   draw(data);applyChartVisibility();
   document.dispatchEvent(new CustomEvent('spotify:filters-applied',{detail:{query:query.toString()}}));
   history.replaceState(null,'',`${location.pathname}?${query.toString()}`);
   content($('loading'),'');
  }catch(e){if(e.name==='AbortError')return;content($('loading'),'');$('error').hidden=false;
   content($('error'),e.message);}
 }
 function artistChip(){const id=filter().read('artist',''),name=filter().read('artist_name','');
  const chip=$('artist-chip'),clear=$('clear-artist');chip.hidden=!id;clear.hidden=!id;
  content(chip,id?`Selected: ${name||`Artist #${id}`}`:'');
 }
 function artistPicker(){const box=$('global-artist-search'),res=$('global-artist-results');if(!box)return;
  $('clear-artist').addEventListener('click',()=>{filter().save('artist','');filter().save('artist_name','');box.value='';artistChip();refresh();});
  let seq=0,timer;
  box.addEventListener('input',()=>{clearTimeout(timer);const q=box.value.trim(),turn=++seq;res.hidden=true;res.replaceChildren();if(q.length<2)return;
   timer=setTimeout(async()=>{try{const payload=await get(`/api/artists/?q=${encodeURIComponent(q)}`);
     if(seq!==turn)return;res.replaceChildren();for(const a of payload.results){const button=document.createElement('button');
     button.type='button';button.className='artist-result';button.textContent=a.name;
     button.addEventListener('click',()=>{filter().save('artist',String(a.id));filter().save('artist_name',a.name);
       filter().save('country_artist','ALL');
       res.hidden=true;box.value=a.name;artistChip();refresh();});res.append(button);}res.hidden=false;
    }catch(e){content($('error'),e.message);$('error').hidden=false;}},260);
  });
  artistChip();
  const choose=$('choose-artist');
  choose?.addEventListener('click',()=>{
   box.focus();box.scrollIntoView({behavior:'smooth',block:'center'});
  });
 }
 async function start(){try{filter().setup(refresh);
   const meta=await get('/api/metadata/');filter().bounds(meta.bounds);
   content($('data-updated'),`Data through ${String(meta.bounds.latest).slice(0,10)}`);
   artistPicker();$('track')?.addEventListener('change',refresh);await refresh();
  }catch(e){content($('loading'),'');$('error').hidden=false;content($('error'),e.message);}}
 document.addEventListener('DOMContentLoaded',start);
})();
