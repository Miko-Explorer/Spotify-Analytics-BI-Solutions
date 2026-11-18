/* Dashboard controller: parameterized JSON APIs, persistent dedication and live chart rendering. */
(() => {
 const $=id=>document.getElementById(id), page=document.body.dataset.page;
 if(page==='guide') return;
 const filter=()=>window.SpotifyFilters;
 const charts=()=>window.SpotifyCharts;
 const hasRows=rows=>Array.isArray(rows)&&rows.length>0;
 const hasMeasure=(rows,...fields)=>hasRows(rows)&&rows.some(r=>
    fields.some(key=>r?.[key]!==null&&r?.[key]!==undefined&&Number.isFinite(Number(r[key]))));
 const hasMappedMeasure=(rows,field)=>hasRows(rows)&&rows.some(r=>
    r.iso3 && r[field]!==null && r[field]!==undefined && Number.isFinite(Number(r[field])));
 const chartPanel=id=>$(id)?.closest('.card');
 const panelTitle=(id,title,description)=>{const panel=chartPanel(id);if(!panel)return;const h=panel.querySelector('.chart-head h2'),p=panel.querySelector('.chart-head p');if(h)h.textContent=title;if(p)p.textContent=description;};
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
  // Prefer warehouse-defined thresholds. Other classifications are calculated
  // by existing SQL-based KPI logic. Plain totals remain unclassified.
  if(['positive','negative','neutral'].includes(item.tone))return item.tone;
  const status=String(item.status||'').trim().toLowerCase();
  const label=String(item.label||'').toLowerCase();
  if(!status)return 'default';
  if(['rising','strong','fast'].includes(status))return 'positive';
  if(['falling','weak','slow'].includes(status))return 'negative';
  if(['stable','moderate','normal'].includes(status))return 'neutral';
  if(status==='high')return /rank|position|longevity|improvement|new entr|reach|velocity|diversity/.test(label)?'positive':'default';
  if(status==='low')return /rank|position|longevity|improvement|new entr|reach|velocity|diversity/.test(label)?'negative':'default';
  return 'default';
 };
 // Distinct, accessible outline icons. Threshold color still comes from MySQL.
 const pictograms={
  streams:'M4 19V11m5 8V5m5 14v-7m5 7V3',
  rank:'M4 18h16M7 14l4-4 3 3 5-6M16 7h3v3',
  entry:'M12 3v18m-7-7 7 7 7-7M5 6h14',
  growth:'M3 17l6-6 4 4 8-9M16 6h5v5',
  artist:'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m14-17a4 4 0 1 1-8 0 4 4 0 0 1 8 0Zm2 8a4 4 0 0 1 4 4v3',
  globe:'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm-10 10h20M12 2c-4 4-4 16 0 20M12 2c4 4 4 16 0 20',
  label:'M3 4h10l8 8-9 9-9-9V4Zm5 4h.01',
  days:'M7 3v4m10-4v4M3 10h18M5 5h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z',
  album:'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm0 7a3 3 0 1 0 0 6 3 3 0 0 0 0-6Zm0-7v3m0 14v3',
  award:'M7 3h10v7a5 5 0 0 1-10 0V3ZM7 5H4v3a4 4 0 0 0 4 4m9-7h3v3a4 4 0 0 1-4 4m-4 3v4m-4 2h8',
  streak:'M12 22c5 0 8-4 8-9 0-4-3-7-4-9-1 4-3 5-4 7-1-3-3-5-4-6-1 5-4 8-4 12 0 3 4 5 8 5Z',
  weeks:'M8 3v4m8-4v4M3 10h18M5 5h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Zm3 10h4m-4 3h7',
  longevity:'M12 3a9 9 0 1 0 9 9M12 7v5l4 2M16 2h5v5',
  numberOne:'M12 2l3 4 5 1-3 4 .6 5-5.6-2.4L6.4 16 7 11 4 7l5-1 3-4ZM8 20h8',
  fallback:'M4 19h16M6 15l5-5 4 3 4-6'
 };
 const iconName=(label)=>{
  const text=String(label||'').toLowerCase();
  if(/reaching #1|number.one|number 1|#1/.test(text))return 'numberOne';
  if(/best longevity|chart longevity|staying power/.test(text))return 'longevity';
  if(/observed chart weeks|chart weeks|week/.test(text))return 'weeks';
  if(/unique charting albums|charted albums|album/.test(text))return 'album';
  if(/top 10|best chart|chart strength/.test(text))return 'award';
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
   artist:[['Observed Stream Dates',(d.daily||[]).length],['Charted Albums',(d.albums||[]).length]],
   weekly:[['Observed Chart Weeks',(d.history||[]).length]]
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
  const card=document.createElement('article');card.className='metric-card';card.dataset.tone=kpiTone(item);if(item.threshold_description)card.title=item.threshold_description;
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
 function warning(notes){const el=$('caveats');if(!el)return;const cleaned=page==='weekly'?[]:(notes||[]).filter(x=>!/weekly albums? (is|are) unavailable/i.test(x));el.hidden=!cleaned.length;if(!el.hidden)el.textContent=cleaned.join(' ');}
 function updateTracks(arr,selected){const select=$('track');if(!select)return;const desired=selected?String(selected):select.value;
  select.replaceChildren();for(const item of arr||[]){if(item.track_id){select.add(new Option(item.name,String(item.track_id)));}}
  if([...select.options].some(o=>o.value===desired))select.value=desired;
 }
 function spotifyAlbumId(uri){
  const candidate=String(uri||'').trim();
  const match=candidate.match(/^(?:spotify:album:|https?:\/\/open\.spotify\.com\/album\/)?([A-Za-z0-9]{22})(?:[?#].*)?$/);
  return match?match[1]:null;
 }
 function albumEmbed(id,title){
  const iframe=document.createElement('iframe');
  iframe.src=`https://open.spotify.com/embed/album/${encodeURIComponent(id)}?theme=0`;
  iframe.title=`Spotify album artwork and preview: ${title}`;
  iframe.loading='lazy';iframe.referrerPolicy='strict-origin-when-cross-origin';
  iframe.allow='encrypted-media; fullscreen; picture-in-picture';
  iframe.setAttribute('allowfullscreen','');
  iframe.className='spotify-album-embed';iframe.setAttribute('scrolling','no');return iframe;
 }
 function renderAlbumArtwork(album){
  const area=$('album-cover-art'),fallback=$('album-cover-initial');if(!area)return;
  area.querySelector('iframe')?.remove();
  const id=spotifyAlbumId(album.album_uri);
  if(fallback)fallback.hidden=Boolean(id);
  if(id)area.append(albumEmbed(id,album.name));
 }
 function renderAlbumGallery(leaders){
  const section=$('album-gallery'),grid=$('album-gallery-grid');if(!section||!grid)return;
  grid.replaceChildren();
  for(const album of leaders){
   const id=spotifyAlbumId(album.album_uri);if(!id)continue;
   const tile=document.createElement('article');tile.className='album-gallery-item';
   tile.append(albumEmbed(id,album.name));
   const name=document.createElement('p');name.textContent=album.name;
   const stat=document.createElement('small');stat.textContent=`Best rank #${album.best_rank} · ${album.weeks} weeks on chart`;
   tile.append(name,stat);grid.append(tile);
   if(grid.childElementCount===4)break;
  }
  section.hidden=!grid.childElementCount;
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
    panelTitle('third-chart','New Entries Over Time','Number of newly charting tracks on each recorded date');
    charts().line('third-chart',d.history,[{key:'new_entries',label:'New entries'}]);
    showPanel('main-chart',hasMeasure(d.top,isAlbum?'best_rank':'streams'));
    showPanel('secondary-chart',hasMeasure(d.history,isAlbum?'albums':'streams'));
    showPanel('calendar-heatmap',!isAlbum&&hasMeasure(d.history,'streams'));
    showPanel('third-chart',hasMeasure(d.history,'new_entries'));
    table('main-table',d.top,isAlbum?[['name','Album'],['best_rank','Best Rank','integer'],['weeks','Weeks','integer']]:
     [['name','Track'],['streams','Total Streams','compact'],['best_rank','Best Rank','integer']]);
  }else if(page==='weekly'){
    // Global artist selection persists across pages. Show only two artist-specific
    // charts when an artist is selected; otherwise show the three requested
    // overall weekly charts. Do not silently substitute other chart types.
    const artistSelected=Boolean(filter().read('artist',''));
    const chartGrid=$('dashboard-visuals');
    if(chartGrid)chartGrid.classList.toggle('weekly-artist-mode',artistSelected);
    const rankRows=d.rank_distribution||[];
    if(artistSelected){
      charts().bars('main-chart',d.top,'name','best_rank','Best weekly rank (lower is better)',true);
      charts().bars('sixth-chart',rankRows,'band','observations','Weekly album appearances',false);
    }else{
      charts().line('fourth-chart',d.history,[{key:'new_entries',label:'New album entries'}]);
      charts().line('fifth-chart',d.history,[{key:'avg_top10_weeks',label:'Average weeks on chart of Top 10 albums'}]);
      charts().bars('sixth-chart',rankRows,'band','observations','Weekly album appearances',false);
    }
    showPanel('main-chart',artistSelected && hasMeasure(d.top,'best_rank'));
    showPanel('secondary-chart',false);
    showPanel('third-chart',false);
    showPanel('fourth-chart',!artistSelected && hasMeasure(d.history,'new_entries') &&
      (d.history||[]).some(x=>Number(x.new_entries)>0));
    showPanel('fifth-chart',!artistSelected && hasMeasure(d.history,'avg_top10_weeks'));
    showPanel('sixth-chart',hasMeasure(rankRows,'observations') &&
      rankRows.some(x=>Number(x.observations)>0));
    const best=(d.top||[])[0];
    const title=$('album-feature-name'),meta=$('album-feature-meta'),cover=$('album-cover-initial'),spotlight=$('album-spotlight');
    if(spotlight)spotlight.hidden=!best;
    if(best){content(title,best.name);content(meta,`Best chart position: #${best.best_rank} · Maximum weeks on chart: ${best.weeks??'unknown'}`);
      content(cover,String(best.name||'♪').trim().slice(0,1).toUpperCase());
      renderAlbumArtwork(best);renderAlbumGallery(d.leaders||[]);}
    else renderAlbumGallery([]);
  }else if(page==='regional'){
    charts().bars('main-chart',d.top_artists,'name','avg_rank','Average rank',true);
    charts().stacked('secondary-chart',d.labels);
    if(hasMeasure(d.compare,'local_streams','global_streams')){
     panelTitle('third-chart','Local #1 vs Same Track on Global Chart','Country top-ranked track compared with its global streams');
     charts().line('third-chart',d.compare,[{key:'local_streams',label:'Country #1 streams'},
      {key:'global_streams',label:'Same track GLOBAL streams'}]);
    }else{
     panelTitle('third-chart',d.artist_mode?'Selected Artist Daily Streams':'Selected Country vs Global Streams',
       'Available filtered daily stream observations; no matching #1 track comparison');
     charts().line('third-chart',d.history,d.artist_mode?[{key:'streams',label:'Artist credited streams'}]:
      [{key:'streams',label:'Country chart streams'},{key:'global_streams',label:'Global chart streams'}]);
    }
    panelTitle('fourth-chart',d.artist_mode?'Artist Share of Local Market Over Time':'Country Share of Global Charts Over Time',
      d.artist_mode?'Selected artist credited streams as a percentage of country chart streams':'Selected country chart streams as a percentage of global chart streams');
    charts().line('fourth-chart',d.history,[{key:'share',label:d.artist_mode?'Artist share (%)':'Country share (%)'}]);
    showPanel('main-chart',hasMeasure(d.top_artists,'avg_rank'));
    showPanel('secondary-chart',hasMeasure(d.labels,'streams'));
    showPanel('third-chart',hasMeasure(d.compare,'local_streams','global_streams')||hasMeasure(d.history,'streams'));
    showPanel('fourth-chart',hasMeasure(d.history,'share'));
    table('main-table',d.top_artists,[['name','Artist'],['avg_rank','Average Rank','decimal'],['chart_days','Observations','integer']]);
    table('secondary-table',d.labels,[['label_name','Label'],['streams','Streams','compact']]);
  }else if(page==='velocity'){
    charts().scatter('main-chart',d.scatter);
    if(hasMeasure(d.box,'days')){
     panelTitle('label-box','Chart Longevity by Record Label','Distribution of observed chart days by label');
     charts().boxplot('label-box',d.box);
    }else{
     panelTitle('label-box','Longest-Charting Tracks','Observed chart longevity for the selected market and period');
     charts().barsInPlot('label-box',d.tracks.slice(0,12),'name','days','Days on chart');
    }
    charts().histogram('third-chart',d.histogram);
    charts().line('fourth-chart',d.rank||[],[{key:'chart_rank',label:'Current rank'},
      {key:'previous_rank',label:'Previous rank'}],true);
    updateTracks(d.tracks,d.selected_track);
    showPanel('main-chart',hasMeasure(d.scatter,'entry_rank','peak_rank'));
    showPanel('label-box',hasMeasure(d.box,'days')||hasMeasure(d.tracks,'days'));
    showPanel('third-chart',hasMeasure(d.histogram,'count'));
    showPanel('fourth-chart',hasMeasure(d.rank,'chart_rank'));
    table('main-table',d.tracks,[['name','Track / Album'],['entry_rank','Entry Rank','integer'],
      ['peak_rank','Peak Rank','integer'],['improvement','Rank Improvement','integer'],['days','Chart Longevity','integer']]);
  }else if(page==='artist'){
    content($('selected-artist-name'),d.artist?`${d.artist.artist_name||'Unknown artist'}`:'No artist found');
    const topMarkets=(d.reach||[]).filter(r=>r.code&&r.streams!==null&&r.streams!==undefined).sort((a,b)=>Number(b.streams)-Number(a.streams)).slice(0,8);
    charts().bars('artist-market-chart',topMarkets,'code','streams','Credited streams',true);
    charts().line('main-chart',d.daily,[{key:'streams',label:'Credited daily streams'}]);
    if(hasMeasure(d.albums,'weeks')){
     panelTitle('secondary-chart','Album Chart Longevity','Recorded weeks on chart for attributed albums');
     charts().bars('secondary-chart',d.albums,'name','weeks','Weeks on chart',true);
    }else{
     panelTitle('secondary-chart','Leading Artist Chart Markets','Countries ranked by credited streams in the selected period');
     charts().bars('secondary-chart',d.reach.slice(0,12),'code','streams','Credited streams',true);
    }
    showPanel('artist-market-chart',hasMeasure(d.reach,'streams'));
    showPanel('main-chart',hasMeasure(d.daily,'streams'));
    showPanel('secondary-chart',hasMeasure(d.albums,'weeks')||hasMeasure(d.reach,'streams'));
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
   const meta=await get(page==='weekly'?'/api/metadata/weekly/':'/api/metadata/');filter().bounds(meta.bounds);
   content($('data-updated'),`Data through ${String(meta.bounds.latest).slice(0,10)}`);
   artistPicker();$('track')?.addEventListener('change',refresh);await refresh();
  }catch(e){content($('loading'),'');$('error').hidden=false;content($('error'),e.message);}}
 document.addEventListener('DOMContentLoaded',start);
})();
