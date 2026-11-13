/* Source-only charts: missing values are left blank, never replaced with invented metrics. */
(() => {
 const instances=new Map();
 const C={green:'#1ed760',blue:'#77b9ff',gold:'#ecbe68',ink:'#aab7ac',red:'#ff8e9b',dark:'#101111'};
 const base={responsive:true,maintainAspectRatio:false,animation:{duration:200},
  plugins:{legend:{labels:{color:C.ink}},tooltip:{backgroundColor:'#292d2c'}},
  scales:{x:{ticks:{color:C.ink,maxTicksLimit:9},grid:{color:'#333a38'}},y:{ticks:{color:C.ink},grid:{color:'#333a38'},beginAtZero:true}}};
 function update(id,type,data,extra={}){
   const el=document.getElementById(id);if(!el)return;
   instances.get(id)?.destroy();instances.delete(id);
   const empty=document.querySelector(`[data-empty-for="${id}"]`);
   const length=data.labels?.length||data.datasets?.[0]?.data?.length||0;
   if(!length||typeof Chart==='undefined'){
    el.style.display='none';if(empty){empty.hidden=false;empty.textContent='No chart observations for this selection.';}return;
   }
   el.style.display='block';if(empty)empty.hidden=true;
   const options=structuredClone(base);
   if(type==='doughnut')delete options.scales;
   Object.assign(options,extra);
   instances.set(id,new Chart(el,{type,data,options}));
 }
 function line(id,entries,series,reverse=false){
   const x=entries||[];
   update(id,'line',{labels:x.map(r=>String(r.day).slice(0,10)),datasets:series.map((s,i)=>({
    label:s.label,data:x.map(r=>r[s.key]??null),borderColor:i?C.blue:C.green,
    backgroundColor:i?'#77b9ff14':'#1ed76018',pointRadius:x.length<35?2:0,
    tension:.18,spanGaps:false,borderWidth:2,fill:i===0
   }))},{scales:{x:{ticks:{color:C.ink,maxTicksLimit:9}},y:{reverse,ticks:{color:C.ink},grid:{color:'#303b33'}}}});
 }
 function bars(id,items,labelKey,valueKey,label,horizontal=false){
   const r=items||[];update(id,'bar',{labels:r.map(x=>String(x[labelKey]||'Unknown').slice(0,38)),datasets:[{
    label,data:r.map(x=>x[valueKey]??null),backgroundColor:r.map((_,i)=>i===0?C.green:'#318a54'),borderRadius:4,maxBarThickness:40
   }]},{indexAxis:horizontal?'y':'x'});
 }
 function doughnut(id,items){const a=items||[];update(id,'doughnut',{labels:a.map(x=>x.name),datasets:[{
  data:a.map(x=>x.value),backgroundColor:[C.green,C.blue,C.gold,C.red],borderWidth:2,borderColor:C.dark
 }]},{cutout:'68%'});}
 function scatter(id,points){const a=(points||[]).filter(x=>x.entry_rank!=null&&x.peak_rank!=null);
   update(id,'scatter',{datasets:[{label:'Entry / Peak',data:a.map(x=>({x:Number(x.entry_rank),y:Number(x.peak_rank)})),
       pointRadius:4,backgroundColor:C.green}]},{scales:{x:{title:{display:true,text:'Entry rank',color:C.ink},ticks:{color:C.ink}},
       y:{title:{display:true,text:'Peak rank (lower is better)',color:C.ink},reverse:true,ticks:{color:C.ink}}}});
 }
 function histogram(id,items){const a=items||[];bars(id,a,'bucket','count','Tracks');}
 function emptyPlot(id,message){const el=document.getElementById(id);if(el)el.textContent=message;}
 function plot(id,traces,layout={}){const el=document.getElementById(id);if(!el)return;
  if(!window.Plotly){emptyPlot(id,'Map and box plot library unavailable. Check your internet connection.');return;}
  if(!traces.length){emptyPlot(id,'No supported observations for this selection.');return;}
  Plotly.react(el,traces,{paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{color:C.ink,size:11},margin:{t:12,b:35,l:40,r:8},...layout},
      {responsive:true,displayModeBar:false});
 }
 function map(id,items,key='streams',selected){const valid=(items||[]).filter(x=>x.iso3 && x[key]!=null);
   if(!valid.length){emptyPlot(id,'No valid ISO-country chart data available.');return;}
   plot(id,[{type:'choropleth',locationmode:'ISO-3',locations:valid.map(x=>x.iso3),z:valid.map(x=>Number(x[key])),
     text:valid.map(x=>x.code||x.country_code),colorscale:[[0,'#1c3023'],[.5,'#218d50'],[1,C.green]],
     marker:{line:{color:'#2d3b34',width:.5}},colorbar:{title:'Streams',tickfont:{color:C.ink}}}],
     {geo:{scope:'world',showframe:false,showcoastlines:false,projection:{type:'natural earth'},bgcolor:'rgba(0,0,0,0)'},margin:{t:4,l:0,r:0,b:0}});
 }
 function boxplot(id,items){const groups=new Map();for(const row of items||[]){const k=row.label_name;if(!groups.has(k))groups.set(k,[]);groups.get(k).push(Number(row.days));}
   const top=[...groups].sort((a,b)=>b[1].length-a[1].length).slice(0,8);
   plot(id,top.map(([name,vals])=>({type:'box',name,y:vals,boxpoints:false,marker:{color:C.green}})),
     {xaxis:{color:C.ink},yaxis:{title:'Days on chart',color:C.ink}});
 }
 function calendar(id,history){
   const el=document.getElementById(id);if(!el)return;el.replaceChildren();
   const days=(history||[]).filter(r=>r.streams!=null);
   if(!days.length){el.textContent='Daily stream counts are unavailable for this scope.';return;}
   const maximum=Math.max(...days.map(x=>Number(x.streams)));
   const months=new Map();for(const day of days){const date=String(day.day).slice(0,10),key=date.slice(0,7);
     if(!months.has(key))months.set(key,[]);months.get(key).push({...day,date});}
   for(const [key,records] of months){const section=document.createElement('div');section.className='heat-month';
     const title=document.createElement('h3');title.textContent=new Date(key+'-01T12:00:00Z').toLocaleDateString('en',{month:'short',year:'numeric',timeZone:'UTC'});
     const grid=document.createElement('div');grid.className='month-grid';
     const dict=new Map(records.map(d=>[d.date,d]));const [year,month]=key.split('-').map(Number);
     const daysInMonth=new Date(Date.UTC(year,month,0)).getUTCDate();
     const padding=(new Date(Date.UTC(year,month-1,1)).getUTCDay()+6)%7;
     for(let i=0;i<padding;i++){const gap=document.createElement('span');gap.className='heat-gap';grid.append(gap);}
     for(let d=1;d<=daysInMonth;d++){const date=`${key}-${String(d).padStart(2,'0')}`,obs=dict.get(date);
       const cell=document.createElement('span');cell.className='heat-cell';if(obs){const a=maximum?Math.max(.10,Number(obs.streams)/maximum):.10;
        cell.style.background=`rgba(30,215,96,${a.toFixed(3)})`;cell.title=`${date}: ${Number(obs.streams).toLocaleString()} streams`;
       }else{cell.title=`${date}: no observed data`;cell.style.background='#282d2a';}
       grid.append(cell);}
     section.append(title,grid);el.append(section);}
 }
 function clearAll(){
  for(const [id,chart] of instances){chart.destroy();const el=document.getElementById(id);if(el)el.style.display='none';}
  instances.clear();
  for(const id of ['main-chart','secondary-chart','third-chart','fourth-chart','regional-map','artist-map','label-box','calendar-heatmap']){
   const el=document.getElementById(id);if(!el)continue;
   if(window.Chart?.getChart(el))window.Chart.getChart(el).destroy();
   if(el.classList.contains('js-plotly-plot')&&window.Plotly)window.Plotly.purge(el);
   if(!(el instanceof HTMLCanvasElement))el.replaceChildren();
   const empty=document.querySelector(`[data-empty-for="${id}"]`);if(empty){empty.hidden=false;empty.textContent='No chart records for the current selection.';}
  }
 }
 window.SpotifyCharts={line,bars,doughnut,scatter,histogram,map,boxplot,calendar,clearAll};
})();
/* Stacked label share chart: one country total subdivided by record label. */
(() => {
 window.SpotifyCharts.stacked=(id,items)=>{
  const el=document.getElementById(id);if(!el)return;
  const existing=Chart.getChart(el);if(existing)existing.destroy();
  const colors=['#1ed760','#50b985','#8fdfab','#449e7a','#317353','#c3d6a3','#c1a567','#658b78'];
  if(!items?.length){el.style.display='none';return;}el.style.display='block';
  const datasets=items.map((x,i)=>({label:x.label_name,data:[Number(x.streams||0)],backgroundColor:colors[i%colors.length]}));
  new Chart(el,{type:'bar',data:{labels:['Selected country'],datasets},options:{responsive:true,maintainAspectRatio:false,
   plugins:{legend:{labels:{color:'#aab7ac'}}},scales:{x:{stacked:true,ticks:{color:'#aab7ac'}},y:{stacked:true,ticks:{color:'#aab7ac'}}}}});
 };
})();
