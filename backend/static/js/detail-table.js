/* Bounded, server-side detail explorer. No full-table browser downloads. */
(() => {
 const $ = id => document.getElementById(id);
 const page = document.body.dataset.page;
 let params = new URLSearchParams(), pageNumber = 1, sort = '', direction = 'desc';
 let current = [], columns = [], busy = null, version = 0, next = false;
 const format = val => {
  if (val === null || val === undefined) return 'N/A';
  if (typeof val === 'number') return new Intl.NumberFormat('en-US',{maximumFractionDigits:2}).format(val);
  return String(val);
 };
 async function load() {
  if (!$('detail-table')) return;
  if (busy) busy.abort(); busy = new AbortController(); const ticket = ++version;
  $('detail-status').textContent = 'Loading detailed records…';
  const q = new URLSearchParams(params);
  q.set('page',String(pageNumber));q.set('size',$('detail-page-size').value);
  if (sort) q.set('sort',sort);
  q.set('direction',direction);q.set('search',$('detail-search').value.trim());
  try {
   const res = await fetch(`/api/table/${page}/?${q}`,{signal:busy.signal,headers:{Accept:'application/json'}});
   const data = await res.json(); if (!res.ok) throw new Error(data.error||`HTTP ${res.status}`);
   if(ticket!==version) return;
   current = data.rows||[]; columns=data.columns||[]; next=!!data.has_next;
   const root=$('detail-table');root.replaceChildren();
   if (!current.length) {const p=document.createElement('p');p.className='no-rows';p.textContent='No matching warehouse records.';root.append(p);}
   else {
    const table=document.createElement('table');table.className='detail-data';
    const head=table.createTHead();const tr=head.insertRow();
    for(const [key,label] of columns){
     const th=document.createElement('th');const b=document.createElement('button');
     b.type='button';b.className='detail-sort';
     b.textContent=label+(sort===key?(direction==='asc'?' ↑':' ↓'):'');
     b.setAttribute('aria-label',`Sort by ${label}`);
     b.addEventListener('click',()=>{direction=sort===key && direction==='desc'?'asc':'desc';sort=key;pageNumber=1;load();});
     th.append(b);tr.append(th);
    }
    const body=table.createTBody();
    for (const record of current){const r=body.insertRow();for(const [key] of columns){r.insertCell().textContent=format(record[key]);}}
    root.append(table);
   }
   $('detail-page-number').textContent=`Page ${pageNumber}`;
   $('detail-prev').disabled=pageNumber===1;$('detail-next').disabled=!next;
   $('detail-status').textContent=`Showing ${current.length} row${current.length===1?'':'s'} on page ${pageNumber}`;
   $('detail-note').textContent=data.note||'Records follow the selected dashboard filters. CSV export includes only visible rows.';
  }catch(e){if(e.name==='AbortError')return;$('detail-status').textContent=`Table unavailable: ${e.message}`;}
 }
 function csv() {
  if(!current.length)return;
  const escape = value => '"'+String(value??'').replaceAll('"','""')+'"';
  const lines=[columns.map(x=>escape(x[1])).join(',')];
  for(const r of current) lines.push(columns.map(x=>escape(r[x[0]])).join(','));
  const blob=new Blob(['\uFEFF'+lines.join('\r\n')],{type:'text/csv;charset=utf-8'});
  const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;
  link.download=`spotify_${page}_details_page_${pageNumber}.csv`;link.click();URL.revokeObjectURL(url);
 }
 function init(){if(!$('detail-table'))return;
  let timer;$('detail-search').addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(()=>{pageNumber=1;load();},350);});
  $('detail-page-size').addEventListener('change',()=>{pageNumber=1;load();});
  $('detail-prev').addEventListener('click',()=>{if(pageNumber>1){pageNumber--;load();}});
  $('detail-next').addEventListener('click',()=>{if(next){pageNumber++;load();}});
  $('detail-export').addEventListener('click',csv);
  document.addEventListener('spotify:filters-applied',e=>{params=new URLSearchParams(e.detail.query);pageNumber=1;load();});
  document.addEventListener('spotify:availability-empty',()=>{if(busy)busy.abort();
   ++version;current=[];columns=[];next=false;pageNumber=1;
   $('detail-table').replaceChildren();$('detail-status').textContent='No matching records for the selected filters.';
   $('detail-prev').disabled=true;$('detail-next').disabled=true;});
 }
 document.addEventListener('DOMContentLoaded',init);
})();
