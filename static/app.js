const API='/api';
const state={page:'dashboard',hazard:'flood',districts:[],districtNames:[],selected:null,map:null,routeMap:null,markers:[],chart:null,monthlyChart:null,currentUser:localStorage.getItem('cg_user')||''};
const hazards=[['flood','Flood','#36a7ff'],['earthquake','Earthquake','#f7b84b'],['fire','Fire','#ff5364'],['sealevel','Sea Level','#32d6e7']];
const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const level=v=>v>=.75?'critical':v>=.55?'high':v>=.35?'medium':'low';
const cap=s=>s.charAt(0).toUpperCase()+s.slice(1);
async function api(path,opt){const r=await fetch(API+path,opt);if(!r.ok){let e='Request failed';try{const j=await r.json();e=j.detail||j.error||j.message||e}catch{}throw Error(e)}return r.json()}
function init(){renderHazards();$('#nav').addEventListener('click',e=>{const b=e.target.closest('[data-page]');if(b)navigate(b.dataset.page)});$('#collapse').onclick=()=>{$('#sidebar').classList.toggle('collapsed');$('.main').style.marginLeft=$('#sidebar').classList.contains('collapsed')?'72px':'248px'};$('#accountBtn').onclick=accountModal;$('#chatFab').onclick=()=>$('#chat').classList.toggle('hidden');$('#chatClose').onclick=()=>$('#chat').classList.add('hidden');$('#chatForm').onsubmit=sendChat;setInterval(()=>$('#clock').textContent=new Date().toLocaleTimeString('en-IN',{hour12:false}),1000);load();}
function renderHazards(){ $('#hazards').innerHTML=hazards.map(([id,label,color])=>`<div class="hazard ${state.hazard===id?'active':''}" data-hazard="${id}"><i class="dot" style="background:${color}"></i><span>${label}</span></div>`).join('');$('#hazards').onclick=e=>{const h=e.target.closest('[data-hazard]');if(h){state.hazard=h.dataset.hazard;renderHazards();syncHazardToPage()}}}
function syncHazardToPage(){
 if(state.page==='dashboard'){renderDashboard();return;}
 if(state.page==='predict'){
  const monthly=$('#monthlyHazard');
  if(monthly){monthly.value=state.hazard;setPredictMode();loadMonthlySignal();}
  return;
 }
 if(state.page==='evacuate'){
  const routeHazard=$('#routeHazard');
  if(routeHazard)routeHazard.value=state.hazard;
 }
}
async function load(){try{const [d,n]=await Promise.all([api('/districts'),api('/predict/districts')]);state.districts=d.districts;state.districtNames=n.districts;$('#apiStatus').textContent='● API ONLINE';renderDashboard()}catch(e){$('#apiStatus').textContent='● API OFFLINE';renderDashboard(e.message)}}
function navigate(page){state.page=page;document.querySelectorAll('.nav-item').forEach(b=>b.classList.toggle('active',b.dataset.page===page));$('#pageTitle').textContent=cap(page);({dashboard:renderDashboard,predict:renderPredict,evacuate:renderEvacuate,about:renderAbout}[page])()}
function renderDashboard(error=''){const v=$('#view');if(error){v.innerHTML=`<div class="content"><div class="panel"><h2>Backend unavailable</h2><p class="small">${esc(error)}. Start the Django server on port 8000.</p></div></div>`;return}const key=state.hazard;const vals=state.districts.map(d=>d.risks[key]??0);const avg=vals.length?vals.reduce((a,b)=>a+b,0)/vals.length:0;const high=vals.filter(x=>x>=.55).length;const critical=vals.filter(x=>x>=.75).length;v.innerHTML=`<div class="content"><div class="cards"><div class="card"><div class="label">Monitored districts</div><div class="metric">${state.districts.length}</div></div><div class="card"><div class="label">${cap(key)} average risk</div><div class="metric">${(avg*100).toFixed(1)}%</div></div><div class="card"><div class="label">High + critical</div><div class="metric">${high}</div></div><div class="card"><div class="label">Critical</div><div class="metric critical">${critical}</div></div></div><div class="panel" style="margin-top:16px"><h2>LIVE MULTI-HAZARD FEEDS</h2><div id="liveHazards" class="cards"></div></div><div class="grid"><section class="panel"><h2>LIVE HAZARD MAP · ${cap(key)}</h2><div class="map"><div id="map"></div></div></section><section class="panel"><h2>RISK DISTRIBUTION <span class="small">· click a district</span></h2><div class="toolbar"><button class="ghost" id="refreshAlerts">Refresh alerts</button><button class="ghost" id="liveWeather">Live weather</button></div><div id="districtList" class="list"></div><div id="alerts"></div></section></div><div class="panel" style="margin-top:16px"><h2>MONTHLY SIGNAL</h2><canvas id="riskChart" height="90"></canvas></div></div>`;renderList();initMap();loadAlerts();$('#refreshAlerts').onclick=()=>loadAlerts(true);$('#liveWeather').onclick=showLiveWeather;renderChart();loadLiveHazardCenter()}
async function loadLiveHazardCenter(){
 const box=$('#liveHazards'); if(!box)return;
 const name=state.selected?.name||state.districts[0]?.name||'Mumbai';
 try{
   const x=await api('/hazards/'+encodeURIComponent(name));
   const items=[['flood','Flood',x.flood],['earthquake','Earthquake',x.earthquake],['fire','Fire',x.fire],['sealevel','Sea Level',x.sealevel]];
   box.innerHTML=items.map(([id,label,val])=>`<div class="card"><div class="label">${label} · LIVE</div><div class="metric">${(val*100).toFixed(1)}%</div><div class="small">${id==='earthquake'?(x.earthquakes?.length||0)+' recent events':id==='fire'?(x.fires?.length||0)+' detections':id==='sealevel'?(x.sealevel_data?.length||0)+' marine readings':'weather-derived flood signal'}</div></div>`).join('');
 }catch(e){box.innerHTML=`<div class="small">Live hazard feeds unavailable: ${esc(e.message)}</div>`}
}
function renderList(){const sorted=[...state.districts].sort((a,b)=>(b.risks[state.hazard]||0)-(a.risks[state.hazard]||0));$('#districtList').innerHTML=sorted.slice(0,25).map(d=>{const r=d.risks[state.hazard]||0;const driver=d.risk_drivers?.[state.hazard]||'District risk profile';return `<div class="row" data-name="${esc(d.name)}"><div><b>${esc(d.name)}</b><div class="small">${esc(d.state)} - ${esc(driver)}</div></div><div class="risk ${level(r)}">${(r*100).toFixed(0)}% - ${level(r).toUpperCase()}</div></div>`}).join('');$('#districtList').onclick=e=>{const row=e.target.closest('.row');if(row)showDistrict(row.dataset.name)}}
function hazardColor(){return (hazards.find(h=>h[0]===state.hazard)||hazards[0])[2]}
function mapRiskColor(r){return r>=.75?'#ff5364':r>=.55?'#f4d45b':r>=.35?'#36a7ff':'#18e0a0'}
function initMap(){if(state.map)state.map.remove();state.map=L.map('map',{zoomControl:false}).setView([22.5,79],5);L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'OpenStreetMap contributors'}).addTo(state.map);state.markers=[];const label=selectedHazardMeta()[1];state.districts.forEach(d=>{const r=d.risks[state.hazard]||0;const color=mapRiskColor(r);const m=L.circleMarker([d.lat,d.lng],{radius:6+Math.min(r*12,10),color:color,fillColor:color,fillOpacity:.35+Math.min(r*.55,.55),weight:2}).addTo(state.map).bindTooltip(`${d.name}: ${label} ${(r*100).toFixed(0)}% - ${level(r).toUpperCase()}`);m.on('click',()=>showDistrict(d.name));state.markers.push(m)});}
async function showDistrict(name){try{const d=await api('/districts/'+encodeURIComponent(name));state.selected=d;loadLiveHazardCenter();const drivers=d.risk_drivers||{};alert(`District: ${d.name}
State: ${d.state}
Flood ${(d.risks.flood*100).toFixed(0)}% - ${drivers.flood||'profile'}
Earthquake ${(d.risks.earthquake*100).toFixed(0)}% - ${drivers.earthquake||'profile'}
Fire ${(d.risks.fire*100).toFixed(0)}% - ${drivers.fire||'profile'}
Sea level ${(d.risks.sealevel*100).toFixed(0)}% - ${drivers.sealevel||'profile'}`)}catch(e){alert(e.message)}}
async function loadAlerts(live=false){const box=$('#alerts');if(!box)return;try{const d=await api('/alerts'+(live?'?live=1':''));box.innerHTML='<h2 style="margin-top:18px">ACTIVE ALERTS</h2>'+d.alerts.slice(0,4).map(a=>`<div class="alert"><b class="${a.level.toLowerCase()}">${a.level}</b> · ${esc(a.district)}<div class="small">${esc(a.message)}</div></div>`).join('')}catch(e){box.innerHTML=`<div class="small">Alerts unavailable: ${esc(e.message)}</div>`}}
async function showLiveWeather(){if(!state.districts.length)return;const d=state.selected?.name||state.districts[0].name;try{const x=await api('/live/'+encodeURIComponent(d));const c=x.current||{};alert(`${d} live weather\nTemperature: ${c.temperature_2m??'—'}°C\nHumidity: ${c.relative_humidity_2m??'—'}%\nRain: ${c.precipitation??'—'} mm\nWind: ${c.wind_speed_10m??'—'} km/h\nSource: ${x.source}`)}catch(e){alert(e.message)}}
async function renderChart(){const el=$('#riskChart');if(!el)return;try{const hazard=state.hazard;const district=state.selected?.name||state.districts[0]?.name||'Patna';const d=await api('/predict/monthly',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({district,hazard})});if(state.chart)state.chart.destroy();const labels=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];const color=(hazards.find(h=>h[0]===d.hazard)||hazards[0])[2];state.chart=new Chart(el,{type:'line',data:{labels:labels,datasets:[{label:d.hazard_label,data:d.series.map(x=>x.risk),borderColor:color,backgroundColor:color,borderWidth:2,tension:.3}]},options:{plugins:{legend:{labels:{color:'#9bb0b8'}}},scales:{x:{ticks:{color:'#78909c'},grid:{color:'#15252d'}},y:{min:0,max:1,ticks:{color:'#78909c'},grid:{color:'#15252d'}}}}})}catch{} }
async function loadMonthlySignal(){const el=$('#predictMonthlyChart');if(!el)return;try{const district=$('#pDistrict')?.value||state.selected?.name||state.districtNames[0];const hazard=$('#monthlyHazard')?.value||state.hazard||'flood';const d=await api('/predict/monthly',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({district,hazard})});if(state.monthlyChart)state.monthlyChart.destroy();const labels=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];const color=(hazards.find(h=>h[0]===d.hazard)||hazards[0])[2];state.monthlyChart=new Chart(el,{type:'line',data:{labels:labels,datasets:[{label:d.hazard_label,data:d.series.map(x=>x.risk),borderColor:color,backgroundColor:color,borderWidth:2,tension:.3}]},options:{responsive:true,scales:{y:{min:0,max:1}},plugins:{legend:{display:true}}}});$('#monthlySignalText').textContent=`Peak modeled ${d.hazard_label.toLowerCase()} signal: ${labels[d.peak_month-1]} - ${(d.peak_value*100).toFixed(0)}% for ${d.district}`; }catch(e){if($('#monthlySignalText'))$('#monthlySignalText').textContent='Monthly signal unavailable.'}}
function selectedHazardMeta(){return hazards.find(h=>h[0]===state.hazard)||hazards[0]}
function setPredictMode(){
 const [hazard,label]=selectedHazardMeta();
 const isFlood=hazard==='flood';
 if($('#predictTitle'))$('#predictTitle').textContent=isFlood?'AI FLOOD PREDICTION':`${label.toUpperCase()} RISK SIGNAL`;
 if($('#predictHelp'))$('#predictHelp').textContent=isFlood?'Random Forest + Gradient Boosting ensemble with optional live-weather input.':'Hazard-specific risk signal using district risk profile, seasonality, and bundled historical events.';
 if($('#predictInputs'))$('#predictInputs').classList.toggle('hidden',!isFlood);
 if($('#runPredict'))$('#runPredict').textContent=isFlood?'Run flood prediction':`Show ${label} signal`;
 if($('#monthlyHazard'))$('#monthlyHazard').value=hazard;
}
async function runHazardSignal(){
 const district=$('#pDistrict').value;
 const hazard=state.hazard;
 const label=selectedHazardMeta()[1];
 const d=await api('/predict/monthly',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({district,hazard})});
 const avg=d.series.reduce((a,b)=>a+b.risk,0)/d.series.length;
 const cls=level(avg);
 $('#predictionResult').innerHTML=`<div class="result"><div class="small">${label.toUpperCase()} RISK SIGNAL</div><div class="metric">${(avg*100).toFixed(1)}%</div><div class="risk ${cls}">${cls.toUpperCase()}</div><div class="bar"><i style="width:${avg*100}%"></i></div><p class="small">Peak month: ${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][d.peak_month-1]} - ${(d.peak_value*100).toFixed(0)}%</p><p class="small">This is not the flood ML model. It is a hazard-specific planning signal from district risk, seasonality, and historical context.</p></div>`;
}
function renderPredict(){const v=$('#view');v.innerHTML=`<div class="content"><div class="panel"><h2 id="predictTitle">AI FLOOD PREDICTION</h2><p id="predictHelp" class="small">Random Forest + Gradient Boosting ensemble with optional live-weather input.</p><form id="predictForm" class="form-grid"><div class="field"><label>District</label><select id="pDistrict">${state.districtNames.map(n=>`<option>${esc(n)}</option>`).join('')}</select></div><div class="field"><label>Hazard</label><select id="monthlyHazard">${hazards.map(h=>`<option value="${h[0]}" ${state.hazard===h[0]?'selected':''}>${h[1]}</option>`).join('')}</select></div><div id="predictInputs" class="wide form-grid"><div class="field"><label>Month</label><input id="pMonth" type="number" min="1" max="12" value="8"></div><div class="field"><label>Rainfall (mm)</label><input id="rain" type="number" min="0" max="1000" value="280"></div><div class="field"><label>River level (m)</label><input id="river" type="number" min="0" max="20" step=".1" value="8.5"></div><div class="field"><label>Elevation (m)</label><input id="elev" type="number" min="0" max="9000" value="50"></div><div class="field"><label>Temperature (?C)</label><input id="temp" type="number" min="-10" max="55" value="30"></div><div class="field"><label><input id="useLive" type="checkbox"> Use live weather API</label></div></div><div class="wide"><button id="runPredict" class="primary">Run flood prediction</button></div></form><div id="predictionResult"></div><div class="panel" style="margin-top:16px"><h2>MONTHLY SIGNAL</h2><p class="small">12-month signal for the selected district and hazard.</p><canvas id="predictMonthlyChart" height="90"></canvas><div id="monthlySignalText" class="small"></div></div></div></div>`;setPredictMode();loadMonthlySignal();$('#pDistrict').onchange=loadMonthlySignal;$('#monthlyHazard').onchange=()=>{state.hazard=$('#monthlyHazard').value;renderHazards();setPredictMode();loadMonthlySignal()};$('#predictForm').onsubmit=async e=>{e.preventDefault();if(state.hazard!=='flood'){try{await runHazardSignal()}catch(err){$('#predictionResult').innerHTML=`<div class="result">${esc(err.message)}</div>`}return;}const body={district:$('#pDistrict').value,rainfall_mm:+$('#rain').value,river_level_m:+$('#river').value,elevation_m:+$('#elev').value,temperature_c:+$('#temp').value,month:+$('#pMonth').value,use_live:$('#useLive').checked};try{const r=await api('/predict/',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});$('#predictionResult').innerHTML=`<div class="result"><div class="small">PREDICTED FLOOD PROBABILITY</div><div class="metric">${(r.flood_probability*100).toFixed(1)}%</div><div class="risk ${r.risk_level.toLowerCase()}">${r.risk_level}</div><div class="bar"><i style="width:${r.flood_probability*100}%"></i></div><p class="small">Model ${(r.model_probability*100).toFixed(1)}% - Historical prior ${((r.historical_context?.flood_prior||0)*100).toFixed(0)}% - ${r.historical_context?.events||0} local/state historical events</p><p class="small">Common hazards: ${(r.historical_context?.common_hazards||[]).map(esc).join(', ')||'Not enough local history'}</p><p class="small">Top factors: ${r.contributing_factors.map(x=>esc(x.factor.replaceAll('_',' '))).join(', ')}</p><p class="small">${esc(r.note||'Prototype estimate; not an official warning.')}</p></div>`}catch(err){$('#predictionResult').innerHTML=`<div class="result">${esc(err.message)}</div>`}}}
function renderEvacuate(){
 const v=$('#view');
 v.innerHTML=`<div class="content"><div class="two"><section class="panel"><h2>LOCAL EVACUATION ROUTE</h2><form id="routeForm"><div class="field"><label>Origin</label><select id="origin">${state.districtNames.map(n=>`<option>${esc(n)}</option>`).join('')}</select></div><div class="field"><label>Destination (optional - leave blank for nearest shelter/safe point)</label><select id="destination"><option value="">Auto-select nearest local safe place</option>${state.districtNames.map(n=>`<option>${esc(n)}</option>`).join('')}</select></div><div class="field"><label>Hazard</label><select id="routeHazard">${hazards.map(h=>`<option value="${h[0]}" ${state.hazard===h[0]?'selected':''}>${h[1]}</option>`).join('')}</select></div><button class="primary">Find local safe route</button></form><div id="routeResult"></div></section><section class="panel"><h2>ROUTE MAP</h2><div class="map route-map"><div id="routeMap"></div><div id="routePreview" class="route-preview hidden"></div></div></section></div></div>`;
 initRouteMap();
 $('#routeForm').onsubmit=async e=>{
  e.preventDefault();
  const body={origin_district:$('#origin').value,destination_district:$('#destination').value||null,disaster_type:$('#routeHazard').value};
  $('#routeResult').innerHTML='<div class="result">Finding local safe route...</div>';
  try{
   const r=await api('/evacuate/',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
   const shelters=(r.suggested_resources?.shelters||[]).map(x=>`<div class="row"><span>${esc(x.name)}<br><span class="small">${esc(x.district)} - ${x.distance_from_destination_km} km from destination - capacity ${x.capacity}</span></span><span>${esc(x.contact||'112')}</span></div>`).join('')||'<p class="small">No shelter data available.</p>';
   const hospitals=(r.suggested_resources?.hospitals||[]).map(x=>`<div class="row"><span>${esc(x.name)}<br><span class="small">${esc(x.district)} - ${x.distance_from_destination_km} km from destination</span></span><span>${esc(x.contact||'112')}</span></div>`).join('')||'<p class="small">No hospital data available.</p>';
   const duration=r.duration_min?` - about ${r.duration_min} min`:'';
   const source=r.route_source==='osrm_road_route'?'Road route':'Coordinate estimate';
   const dest=r.destination_detail||{};
   const destLine=`<div class="result" style="margin-top:10px"><b>Safe destination</b><p class="small">${esc(dest.name||r.destination)} - ${esc(dest.type||r.route_type||'safe point')} - ${dest.distance_from_origin_km??r.direct_distance_km??r.distance_km} km from origin${dest.contact?` - emergency contact ${esc(dest.contact)}`:''}</p>${dest.description?`<p class="small">${esc(dest.description)}</p>`:''}</div>`;
   const steps=(r.route_steps||[]).map((x,i)=>`<div class="row"><span>${i+1}. ${esc(x.instruction)}</span><span>${x.distance_km} km</span></div>`).join('')||'<p class="small">No road instructions available.</p>';
   $('#routeResult').innerHTML=`<div class="result"><b>${esc(r.origin)} -> ${esc(r.destination)}</b><p class="small">${source} - ${r.distance_km||0} km${duration} - path risk ${r.total_path_risk}</p>${destLine}${r.waypoints.map(w=>`<div class="row"><span>${w.order+1}. ${esc(w.name)}</span><span class="risk ${level(w.risk_score)}">${(w.risk_score*100).toFixed(0)}%</span></div>`).join('')}<p class="small">${esc(r.route_note||'Planning estimate only.')}</p>${r.route_warning?`<p class="small">${esc(r.route_warning)}</p>`:''}<h3>Safest way to go</h3>${steps}<h3>Nearby shelters</h3>${shelters}<h3>Nearby hospitals</h3>${hospitals}</div>`;
   showRoutePreview(r.waypoints);setTimeout(()=>drawRoute(r),60);
  }catch(err){
   $('#routeResult').innerHTML=`<div class="result">${esc(err.message)}</div>`;
  }
 };
}
function initRouteMap(){
 const el=$('#routeMap');
 if(!el)return;
 if(state.routeMap){state.routeMap.remove();state.routeMap=null;}
 if(typeof L==='undefined'){
  el.innerHTML='<div class="result"><b>Map library not loaded.</b><p class="small">The route will appear here after you click Find local safe route.</p></div>';
  return;
 }
 state.routeMap=L.map('routeMap').setView([22.5,79],5);
 L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'OpenStreetMap contributors'}).addTo(state.routeMap);
 setTimeout(()=>state.routeMap&&state.routeMap.invalidateSize(),80);
}
function drawRouteFallback(points,msg='Map tiles unavailable. Showing route preview instead.'){
 const el=$('#routeMap');
 if(!el)return;
 const safe=(points||[]).map((p,i)=>({name:esc(p.name||('Stop '+(i+1))),risk:Number(p.risk_score||0),order:i}));
 const stops=safe.length?safe:[{name:'Select route',risk:0,order:0}];
 const w=620,h=Math.max(230,stops.length*54),left=46,right=w-46,top=46,bottom=h-46;
 const coords=stops.map((p,i)=>{const t=stops.length===1?.5:i/(stops.length-1);return {x:left+(right-left)*t,y:top+(bottom-top)*t,...p}});
 const line=coords.map(p=>`${p.x},${p.y}`).join(' ');
 el.innerHTML=`<div class="result" style="height:100%;margin-top:0;overflow:auto"><b>${esc(msg)}</b><svg viewBox="0 0 ${w} ${h}" style="width:100%;min-height:260px;margin-top:10px"><polyline points="${line}" fill="none" stroke="#18e0a0" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>${coords.map((p,i)=>`<g><circle cx="${p.x}" cy="${p.y}" r="13" fill="${p.risk>=.55?'#ffae54':'#18e0a0'}"/><text x="${p.x}" y="${p.y+4}" text-anchor="middle" font-size="12" fill="#051016" font-weight="700">${i+1}</text><text x="${Math.min(p.x+18,w-190)}" y="${p.y-8}" font-size="13" fill="#e7f0f4">${p.name}</text><text x="${Math.min(p.x+18,w-190)}" y="${p.y+10}" font-size="11" fill="#78909c">Risk ${(p.risk*100).toFixed(0)}%</text></g>`).join('')}</svg></div>`;
}
function showRoutePreview(points){
 const box=$('#routePreview');
 if(!box)return;
 const stops=(points||[]).map((p,i)=>`<span class="route-stop"><b>${i+1}</b>${esc(p.name||'Stop')}</span>`).join('<span class="route-arrow">-></span>');
 box.classList.remove('hidden');
 box.innerHTML=`<div class="small">Route preview</div><div class="route-strip">${stops||'No route points returned'}</div>`;
}
function kmBetweenLatLng(a,b){const R=6371,rad=x=>x*Math.PI/180;const dLat=rad(b[0]-a[0]),dLng=rad(b[1]-a[1]);const s=Math.sin(dLat/2)**2+Math.cos(rad(a[0]))*Math.cos(rad(b[0]))*Math.sin(dLng/2)**2;return 2*R*Math.asin(Math.sqrt(s))}
function drawRoute(route){
 const el=$('#routeMap');
 if(!el)return;
 const points=Array.isArray(route)?route:(route?.waypoints||[]);
 if(!points||!points.length){initRouteMap();return;}
 if(typeof L==='undefined'){
  drawRouteFallback(points,'Map library did not load. Showing route preview.');
  return;
 }
 try{
  if(state.routeMap){state.routeMap.remove();state.routeMap=null;}
  const road=(Array.isArray(route?.route_geometry)?route.route_geometry:[]).map(p=>[Number(p.lat),Number(p.lng)]).filter(x=>Number.isFinite(x[0])&&Number.isFinite(x[1]));
  const stops=points.map(p=>[Number(p.lat),Number(p.lng)]).filter(x=>Number.isFinite(x[0])&&Number.isFinite(x[1]));
  const hasRoad=route?.route_source==='osrm_road_route'&&road.length>1;
  const latlngs=hasRoad?road:stops;
  if(!latlngs.length){drawRouteFallback(points,'Route coordinates unavailable. Showing route preview.');return;}
  state.routeMap=L.map('routeMap').setView(latlngs[0],14);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'OpenStreetMap contributors'}).addTo(state.routeMap);
  L.polyline(latlngs,{color:hasRoad?'#18e0a0':'#f4d45b',weight:5,opacity:.95,dashArray:hasRoad?null:'8 8'}).addTo(state.routeMap);
  if(hasRoad&&stops.length){
   const first=stops[0],last=stops[stops.length-1];
   if(kmBetweenLatLng(first,latlngs[0])>.03)L.polyline([first,latlngs[0]],{color:'#36a7ff',weight:3,opacity:.9,dashArray:'5 7'}).addTo(state.routeMap);
   if(kmBetweenLatLng(latlngs[latlngs.length-1],last)>.03)L.polyline([latlngs[latlngs.length-1],last],{color:'#36a7ff',weight:3,opacity:.9,dashArray:'5 7'}).addTo(state.routeMap);
  }
  points.forEach((p,i)=>{const kind=i===0?'Hazard location':'Safe destination';L.marker([Number(p.lat),Number(p.lng)]).addTo(state.routeMap).bindPopup(`<b>${kind}</b><br>${esc(p.name)}<br>Risk ${(Number(p.risk_score||0)*100).toFixed(0)}%`)});
  const bounds=[...latlngs,...stops];
  if(bounds.length===1)state.routeMap.setView(bounds[0],15);else state.routeMap.fitBounds(bounds,{padding:[30,30],maxZoom:16});
  setTimeout(()=>state.routeMap&&state.routeMap.invalidateSize(),100);
 }catch(e){
  drawRouteFallback(points,'Interactive map failed. Showing route preview.');
 }
}
function renderAbout(){$('#view').innerHTML=`<div class="content"><div class="panel about"><h2>CLIMATEGUARD INDIA</h2><p>ClimateGuard is a multi-hazard decision-support prototype for Indian districts. It combines live weather/news APIs, an ML flood model, live district risk profiles and Dijkstra-based evacuation routing.</p><div class="cards"><div class="card"><div class="label">Flood model</div><div class="metric">RF + GB</div></div><div class="card"><div class="label">Routing</div><div class="metric">Dijkstra</div></div><div class="card"><div class="label">Frontend</div><div class="metric">HTML / CSS / JS</div></div><div class="card"><div class="label">Backend</div><div class="metric">Django</div></div></div><p><b>Important:</b> Risk scores are decision-support estimates, not official warnings. During a real emergency, follow government and local emergency authority instructions.</p></div></div>`}
function accountModal(){
  const m=$('#modal');
  m.classList.remove('hidden');
  m.innerHTML=`
    <div class="modal-box account-modal-box" role="dialog" aria-modal="true" aria-labelledby="accountTitle">
      <button type="button" id="accountClose" class="account-close" aria-label="Close account">&times;</button>
      <h2 id="accountTitle">ClimateGuard Account & Alerts</h2>
      <p class="small">Create an account or log in to manage your personal disaster-alert subscriptions.</p>

      <div class="field"><label>Username</label><input id="u" minlength="3" autocomplete="username" value="${esc(state.currentUser)}"></div>
      <div class="field"><label>Password</label><input id="pw" type="password" minlength="6" autocomplete="current-password" placeholder="At least 6 characters"></div>
      <div class="field"><label>Email (required for registration and alerts)</label><input id="subEmail" type="email" autocomplete="email" placeholder="you@example.com"></div>

      <div class="toolbar">
        <button class="primary" id="login" type="button">Login</button>
        <button class="ghost" id="register" type="button">Register</button>
        ${state.currentUser?'<button class="ghost" id="logout" type="button">Logout</button>':''}
      </div>

      <hr>
      <h3>Email Alert Subscription</h3>
      <div class="field"><label>District (blank = all monitored districts)</label><select id="subDistrict"><option value="">All districts</option>${state.districtNames.map(n=>`<option>${esc(n)}</option>`).join('')}</select></div>
      <div class="field"><label>Alert threshold: <span id="thresholdValue">75%</span></label><input id="subThreshold" type="range" min="30" max="95" value="75"></div>
      <div class="field"><label>Hazards</label><div class="toolbar hazard-checks">${hazards.map(([id,label])=>`<label><input class="subHazard" type="checkbox" value="${id}" checked> ${label}</label>`).join('')}</div></div>

      <div class="toolbar">
        <button class="primary" id="subscribe" type="button">Save Subscription</button>
        <button class="ghost" id="loadSubs" type="button">My Subscriptions</button>
        <button class="ghost" id="unsubscribe" type="button">Unsubscribe</button>
      </div>
      <div id="authMsg" class="small"></div>
      <div id="subscriptionList" class="small"></div>
    </div>`;

  $('#accountClose').onclick=()=>m.classList.add('hidden');
  m.onclick=(e)=>{if(e.target===m)m.classList.add('hidden')};
  const escClose=(e)=>{if(e.key==='Escape'&&!m.classList.contains('hidden'))m.classList.add('hidden')};
  document.addEventListener('keydown',escClose,{once:true});
  $('#subThreshold').oninput=()=>$('#thresholdValue').textContent=$('#subThreshold').value+'%';
  $('#login').onclick=()=>auth('/auth/login');
  $('#register').onclick=()=>auth('/auth/register');
  if($('#logout'))$('#logout').onclick=async()=>{
    try{
      await api('/auth/logout');
      state.currentUser='';
      localStorage.removeItem('cg_user');
      $('#authMsg').textContent='Logged out successfully.';
      accountModal();
    }catch(e){$('#authMsg').textContent=e.message}
  };
  $('#subscribe').onclick=subscribe;
  $('#unsubscribe').onclick=unsubscribe;
  $('#loadSubs').onclick=loadSubscriptions;
  if(state.currentUser)loadSubscriptions();
}

async function auth(path){try{const r=await api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:$('#u').value.trim(),password:$('#pw').value,email:$('#subEmail').value.trim()})});state.currentUser=r.username;localStorage.setItem('cg_user',r.username);$('#authMsg').textContent=`Signed in as ${r.username}. You can now save subscriptions.`;await loadSubscriptions()}catch(e){$('#authMsg').textContent=e.message}}
async function subscribe(){const hazardsSelected=[...document.querySelectorAll('.subHazard:checked')].map(x=>x.value);if(!state.currentUser){$('#authMsg').textContent='Please create an account or login before subscribing.';return}try{const r=await api('/alerts/subscribe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:$('#subEmail').value.trim(),district:$('#subDistrict').value,hazards:hazardsSelected,threshold:+$('#subThreshold').value/100})});$('#authMsg').textContent=r.message;await loadSubscriptions()}catch(e){$('#authMsg').textContent=e.message}}
async function loadSubscriptions(){if(!state.currentUser)return;try{const r=await api('/alerts/subscriptions');$('#subscriptionList').innerHTML=r.subscriptions.length?'<br><b>Active subscriptions</b>'+r.subscriptions.map(x=>`<div class="row"><span>${esc(x.district)} · ${x.hazards.map(cap).join(', ')}</span><span>${(x.threshold*100).toFixed(0)}%</span></div>`).join(''):'<br>No active subscriptions.'}catch(e){$('#subscriptionList').textContent=e.message}}
async function unsubscribe(){const token=prompt('Paste your unsubscribe token from an alert email:');if(!token)return;try{const r=await api('/alerts/unsubscribe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});$('#authMsg').textContent=r.message;await loadSubscriptions()}catch(e){$('#authMsg').textContent=e.message}}
function chatText(s){return esc(s).replace(/\n/g,'<br>')}
async function sendChat(e){e.preventDefault();const input=$('#chatInput'),msg=input.value.trim();if(!msg)return;const messages=$('#chatMessages');messages.insertAdjacentHTML('beforeend',`<div class="user">${chatText(msg)}</div>`);input.value='';const loadingId='chatLoading'+Date.now();messages.insertAdjacentHTML('beforeend',`<div class="bot loading" id="${loadingId}">Thinking...</div>`);messages.scrollTop=messages.scrollHeight;try{const r=await api('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg,district:state.selected?.name})});const meta=r.source?`<div class="small">${esc(r.source)}</div>`:'';$('#'+loadingId).outerHTML=`<div class="bot">${chatText(r.response)}${meta}</div>`}catch(err){$('#'+loadingId).outerHTML=`<div class="bot">${chatText(err.message)}</div>`}messages.scrollTop=messages.scrollHeight}
init();
