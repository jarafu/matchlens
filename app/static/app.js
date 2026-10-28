const $ = s => document.querySelector(s);
const csrf = $('meta[name="csrf-token"]').content;
const state = {fixtures: [], selected: null, candidates: [], timezone: document.documentElement.dataset.timezone || 'Africa/Lagos', analysis: null, generation: 0};
const names = {PL:'Premier League',ELC:'Championship',BL1:'Bundesliga',PD:'La Liga',SA:'Serie A',FL1:'Ligue 1',DED:'Eredivisie',PPL:'Primeira Liga',CL:'Champions League'};
const labels = {over15:'Over 1.5 goals',under45:'Under 4.5 goals',home05:'Home team to score',away05:'Away team to score',dc_1x:'Home or draw',dc_x2:'Away or draw',dc_12:'Either team to win',btts_yes:'Both teams score — Yes',btts_no:'Both teams score — No'};
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const percent = p => `${(p*100).toFixed(1)}%`;
function notice(message,error=false){ const box=$('#notice');box.hidden=!message;box.textContent=message;box.classList.toggle('error',error); }
async function api(path,method='GET',body){
  const response=await fetch(`/api${path}`,{method,headers:{'X-CSRF-Token':csrf,...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined});
  if(response.status===401){location.href='/login';throw new Error('Sign in again');}
  const result=await response.json();
  if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:'Request could not be completed');
  return result;
}
async function busy(button,fn){const before=button.textContent;button.disabled=true;button.textContent='Working…';try{await fn();}catch(e){notice(e.message,true);}finally{button.disabled=false;button.textContent=before;}}
function time(value){return new Intl.DateTimeFormat('en-NG',{hour:'2-digit',minute:'2-digit',hour12:false,timeZone:state.timezone}).format(new Date(value));}
function initials(name){return name.replace(/\bFC\b/g,'').trim().split(/\s+/).map(w=>w[0]).slice(0,2).join('');}
function switchView(view){
  document.querySelectorAll('.view').forEach(el=>el.hidden=el.id!==`${view}-view`);
  document.querySelectorAll('[data-view]').forEach(el=>el.classList.toggle('active',el.dataset.view===view));
  const text={matches:["Today's matches","Every match. A clearer picture.","Explore today's fixtures and the evidence behind each outcome."],shortlist:['Top candidates','The strongest possibilities.','Probability comes first. Price and evidence stay in view.'],history:['Prediction history','Keep the full picture.','Original forecasts, settled outcomes and a record you can inspect.'],coverage:['Data & coverage','Know what supports the numbers.','Connected sources, historical depth and validation status.']}[view];
  $('#breadcrumb-current').textContent=text[0];$('#page-title').textContent=text[1];$('#page-subtitle').textContent=text[2];
  if(view==='coverage')loadCoverage().catch(e=>notice(e.message,true));
  if(view==='history')loadHistory().catch(e=>notice(e.message,true));
}
async function loadFixtures(){
  const generation=invalidateEstimates();
  const data=await api(`/fixtures?day=${encodeURIComponent($('#match-date').value)}`);
  if(generation!==state.generation)return;
  state.fixtures=data.fixtures;state.selected=null;state.analysis=null;
  $('#fixture-count').textContent=data.fixtures.length;
  $('#competition-filter').innerHTML='<option value="">All competitions</option>'+[...new Set(data.fixtures.map(f=>f.competition))].map(c=>`<option value="${esc(c)}">${esc(names[c]||c)}</option>`).join('');
  renderFixtures();
  $('#analysis-content').innerHTML='<div class="analysis-empty"><div class="field-icon">⌁</div><h3>Start with a match.</h3><p>Select a fixture to explore probabilities, supporting evidence and available odds.</p></div>';
  if(!data.api_configured)notice('Connect your football-data API key in Data & coverage to load live fixtures. Historical research can run without it.');
  $('#date-label').textContent=new Date(data.date+'T12:00:00').toLocaleDateString('en-NG',{weekday:'short',day:'numeric',month:'short'});
}
function renderFixtures(){
  const comp=$('#competition-filter').value;const items=state.fixtures.filter(f=>!comp||f.competition===comp);
  if(!items.length){$('#fixture-list').innerHTML='<div class="empty-state"><h3>No fixtures loaded for this date.</h3><p>Connect your data source and refresh. Only matches actually returned by the provider will appear.</p><button class="secondary" data-go-coverage>Open data & coverage ↗</button></div>';return;}
  const groups={};items.forEach(f=>(groups[f.competition]??=[]).push(f));
  $('#fixture-list').innerHTML=Object.entries(groups).map(([c,rows])=>`<div class="league-label">${esc(names[c]||c)}</div>${rows.map(f=>`<button class="fixture ${state.selected?.id===f.id?'selected':''}" data-fixture="${esc(f.id)}"><span class="fixture-time">${esc(time(f.kickoff))}<br><small>${f.status==='SCHEDULED'?'':esc(f.status.toLowerCase())}</small></span><span class="team-stack"><span class="team-line"><span class="club">${esc(initials(f.home))}</span>${esc(f.home)}</span><span class="team-line"><span class="club">${esc(initials(f.away))}</span>${esc(f.away)}</span></span><span class="fixture-chevron">›</span></button>`).join('')}`).join('');
}
function selectFixture(id){
  const f=state.fixtures.find(f=>f.id===id);if(!f)return;state.selected=f;state.analysis=null;renderFixtures();
  $('#analysis-content').innerHTML=`<div class="analysis-head"><h3>${esc(f.home)}<br>vs ${esc(f.away)}</h3><p>${esc(names[f.competition]||f.competition)} · ${esc(time(f.kickoff))} · Regulation time</p><label for="market-filter" class="small muted">Market to analyse</label><select id="market-filter"><option value="all">All six market groups</option><option value="over15">Over 1.5 goals</option><option value="under45">Under 4.5 goals</option><option value="home05">Home team to score</option><option value="away05">Away team to score</option><option value="dc_">Double chance</option><option value="btts_">Both teams to score</option></select><button id="analyse-selected" class="primary wide">Analyse this match ↗</button></div><div id="market-results" class="analysis-body"><p class="small muted">Data quality and validation are checked before any probabilities are shown.</p></div>`;
  if(innerWidth<621) $('.analysis-panel').scrollIntoView({behavior:'smooth',block:'start'});
}
function probabilityCard(m,showMatch=false){
  const ref=m.value.reference;const value=m.value.expected_return;
  return `<article class="prob-card">${showMatch?`<div class="result-match">${esc(m.fixture.home)} vs ${esc(m.fixture.away)} · ${esc(time(m.fixture.kickoff))}</div>`:''}<div class="prob-top"><div><h3>${esc(m.label)}</h3><span class="small muted">${esc(m.description||'')}</span></div><span class="badge ${m.candidate?'good':'neutral'}">${m.candidate?'Probability candidate':'Below threshold'}</span></div><div class="prob-number">${(m.probability*100).toFixed(1)}<small>%</small></div><div class="prob-label">Estimated probability · historically evaluated</div><div class="prob-track"><progress value="${m.probability}" max="1" aria-label="Estimated probability"></progress></div><div class="value-line"><span>${esc(m.value.label)}</span><span>${value==null?'—':(value*100).toFixed(1)+'% expected return'}</span></div>${ref?`<p class="small muted">${esc(ref.bookmaker)}: ${ref.price.toFixed(2)} · ${ref.verified?'verified available price':'reference price; local availability unverified'}</p>`:''}<details><summary>Why this estimate?</summary><ul class="evidence">${m.evidence.map(e=>`<li>${esc(e)}</li>`).join('')}</ul><p>Model ${esc(m.model_id.slice(0,10))} · Updated ${esc(new Date(m.created_at).toLocaleString())}</p><p>Related selections from the same fixture are correlated.</p></details></article>`;
}
function renderAnalysis(){
  const result=state.analysis;if(!result)return;
  const selected=$('#market-filter').value;const markets=result.markets.filter(m=>selected==='all'||m.market===selected||m.market.startsWith(selected));
  $('#market-results').innerHTML=markets.length?markets.map(m=>probabilityCard(m)).join(''):`<div class="withheld"><h3>Not enough evidence to publish an estimate.</h3><ul>${(result.reasons.length?result.reasons:['This market has not passed validation or its probability band has too few historical examples.']).map(r=>`<li>${esc(r)}</li>`).join('')}</ul></div>`;
  if(result.withheld?.length)$('#market-results').insertAdjacentHTML('beforeend',`<p class="small muted">Withheld: ${result.withheld.map(esc).join(', ')}.</p>`);
}
function invalidateEstimates(message='Run analysis again to see current candidates.'){
  state.generation++;state.candidates=[];state.analysis=null;state.selected=null;
  $('#shortlist-content').innerHTML=`<div class="empty-state">${esc(message)}</div>`;
  $('#analysis-content').innerHTML='<div class="analysis-empty"><h3>Select a match to analyse.</h3><p>Current data is checked before estimates are shown.</p></div>';
  return state.generation;
}
function expireEstimates(){
  const shown=[...state.candidates,...(state.analysis?.markets||[])];
  if(shown.some(m=>!(Date.parse(m.expires_at)>Date.now())||Date.parse(m.fixture.kickoff)<=Date.now())){
    invalidateEstimates('Estimates expired. Refresh fixtures and run analysis again.');
    renderFixtures();
  }
}
setInterval(expireEstimates,5000);
document.addEventListener('visibilitychange',expireEstimates);
async function loadCoverage(){
  const data=await api('/coverage');state.timezone=data.timezone;
  $('#connection-title').textContent=data.api_configured?'Fixture API key configured':'Connect your fixture source';
  $('#coverage-content').innerHTML=data.competitions.map(c=>`<article class="coverage-card"><span class="eyebrow">${esc(c.code)}</span><h3>${esc(c.name)}</h3><div class="coverage-number">${c.history_count.toLocaleString()}</div><p>historical results imported</p><span class="badge ${c.enabled_markets.length?'good':'neutral'}">${c.enabled_markets.length?`${c.enabled_markets.length} validated outcomes`:'Validation pending or withheld'}</span><p>${c.enabled_markets.length?c.enabled_markets.map(k=>esc(labels[k]||k)).join(' · '):'Predictions stay hidden until the model passes its checks.'}</p>${c.validation?`<details><summary class="small">Evaluation details</summary><p>${c.validation.error?esc(c.validation.error):`${c.validation.training_n} training · ${c.validation.calibration_n} calibration · ${c.validation.test_n} test matches`}</p></details>`:''}</article>`).join('');
}
async function loadHistory(){
  const data=await api('/history');
  $('#history-content').innerHTML=data.predictions.length?data.predictions.map(p=>`<div class="history-row"><div>${esc(p.fixture.home)} vs ${esc(p.fixture.away)}<small>${esc(p.created_at.slice(0,10))} · Model ${esc(p.model_id.slice(0,8))}</small></div><div>${esc(labels[p.market]||p.market)}</div><strong>${percent(p.probability)}</strong><span class="badge ${p.won===true?'good':'neutral'}">${p.won===true?'Won':p.won===false?'Lost':p.valid?'Pending':'Invalidated'}</span></div>`).join(''):'<div class="empty-state"><h3>Your prediction record starts here.</h3><p>Validated analyses will be saved with their original probabilities and settled against regulation-time results.</p></div>';
}
document.addEventListener('click',event=>{
  const target=event.target.closest('button');if(!target)return;
  if(target.dataset.view)switchView(target.dataset.view);
  if(target.hasAttribute('data-go-coverage'))switchView('coverage');
  if(target.id==='update-model')busy(target,async()=>{invalidateEstimates();notice('Updating current results and checking model accuracy. This can take a minute.');const r=await api('/model-refresh','POST');await loadCoverage();notice(`${r.evaluated} competitions evaluated; ${r.sync.updated} new results. ${r.status==='partial'?'Update incomplete: some data or model checks failed; unsupported predictions remain withheld.':''}`);});
  if(target.dataset.fixture)selectFixture(target.dataset.fixture);
  if(target.id==='analyse-selected')busy(target,async()=>{const generation=state.generation,id=state.selected.id;const result=await api(`/fixtures/${encodeURIComponent(id)}/analyse`,'POST');if(generation!==state.generation||id!==state.selected?.id)return;state.analysis=result;renderAnalysis();expireEstimates();});
});
document.addEventListener('change',e=>{if(e.target.id==='market-filter')renderAnalysis();});
$('#competition-filter').addEventListener('change',renderFixtures);
$('#match-date').value=new Intl.DateTimeFormat('en-CA',{timeZone:state.timezone,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
$('#match-date').addEventListener('change',()=>loadFixtures().catch(e=>notice(e.message,true)));
$('#refresh').addEventListener('click',e=>busy(e.currentTarget,async()=>{invalidateEstimates();const r=await api(`/refresh?day=${$('#match-date').value}`,'POST');await loadFixtures();notice(`${r.count} fixtures loaded from the provider.`);}));
$('#analyse-all').addEventListener('click',e=>busy(e.currentTarget,async()=>{const generation=state.generation;const r=await api(`/analyse-day?day=${$('#match-date').value}`,'POST');if(generation!==state.generation)return;state.candidates=r.candidates;$('#shortlist-content').innerHTML=r.candidates.length?r.candidates.map(m=>probabilityCard(m,true)).join(''):`<div class="empty-state"><h3>No qualifying candidates.</h3><p>${r.evaluated} fixtures evaluated. Missing evidence, failed validation or probabilities below the threshold may exclude a match.</p></div>`;notice(`${r.evaluated} fixtures evaluated · ${r.qualifying} matches with qualifying candidates.`);switchView('shortlist');expireEstimates();}));
$('#token-form').addEventListener('submit',e=>{e.preventDefault();const button=e.target.querySelector('button');busy(button,async()=>{await api('/settings/token','POST',{token:$('#api-token').value});$('#api-token').value='';await loadCoverage();notice('API key saved locally. Return to Today’s matches and refresh fixtures.');});});
$('#logout').addEventListener('click',async()=>{await fetch('/logout',{method:'POST',headers:{'X-CSRF-Token':csrf}});location.href='/login';});
loadFixtures().catch(e=>notice(e.message,true));
