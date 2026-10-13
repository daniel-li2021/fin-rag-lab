'use client';

import { useEffect, useState } from 'react';
import { Group, Panel, Separator } from 'react-resizable-panels';
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUpRight, BookOpen, Check, CheckCheck, ChevronDown, ChevronRight, Clock3, Columns3, Download, FileText, Fingerprint, FlaskConical, FolderOpen, GripVertical, History, Layers3, LibraryBig, ListFilter, Search, ShieldCheck, Sparkles, Table2, TriangleAlert } from 'lucide-react';

const names = { TSLA: 'Tesla', WFC: 'Wells Fargo', AMD: 'AMD' };
const nav = [['research', 'Research', Search], ['library', 'Library', LibraryBig], ['history', 'History', History], ['heroes', 'Hero Scenarios', FlaskConical]];
const metricName = id => ({net_income_common: 'Common-stockholder net income', revenue: 'Reported revenue'})[id] || id;
const tidy = str => String(str ?? '').replaceAll('_', ' ');
const short = str => String(str ?? '').slice(0, 12);
// Only add digit grouping to the preserved decimal string; do not round financial values.
const exact = value => { const [integer, fraction] = String(value).split('.'); return integer.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + (fraction === undefined ? '' : '.' + fraction); };
const units = o => o.scale === '1000000' ? `${o.currency || o.unit} millions` : `${o.currency || o.unit} × ${o.scale}`;
const supportedFacts = r => (r.observations || []).filter(o => Object.hasOwn(r.citations || {}, o.observation_id));
const citedIds = r => r.contract_version === 'evidence-search-v1' ? [...new Set((r.claims || []).map(c=>c.evidence_id))] : Object.keys(r.citations || {});
const stamp = r => r.execution?.timestamp ? new Date(r.execution.timestamp).toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric', timeZone:'UTC'}) : 'Preserved capture';

function Badge({children, tone = ''}) { return <span className={`badge ${tone}`}>{children}</span>; }
function Citation({id, index, onSelect, selected}) { return <button className={`cite ${selected === id ? 'selected' : ''}`} title="Inspect original evidence" aria-label={`Inspect citation ${index}`} onClick={() => onSelect(id)}>[{index}]</button>; }
function exportJSON(result) { const blob = new Blob([JSON.stringify(result, null, 2)], {type:'application/json'}); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href=url; a.download=`finrag-${result.run_id}.json`; a.click(); URL.revokeObjectURL(url); }

export default function Workspace() {
  const [data, setData] = useState(null), [loadError, setLoadError] = useState('');
  const [direction, setDirection] = useState(''), [view, setView] = useState('research');
  const [scenarioId, setScenarioId] = useState('equity'), [stepIndex, setStepIndex] = useState(0), [calcMode, setCalcMode] = useState(false);
  const [selected, setSelected] = useState(''), [inspectorTab, setInspectorTab] = useState('excerpts');
  const [query, setQuery] = useState(''), [companyFilter, setCompanyFilter] = useState('all'), [historyPage, setHistoryPage] = useState(0);
  const [mobileEvidence, setMobileEvidence] = useState(false), [ready, setReady] = useState(false);
  useEffect(() => {
    const readURL = () => { const q = new URLSearchParams(location.search); setDirection(['folio','terminal'].includes(q.get('direction')) ? q.get('direction') : ''); setView(nav.some(n=>n[0]===q.get('view')) ? q.get('view') : 'research'); setScenarioId(q.get('scenario') || 'equity'); setStepIndex(Number(q.get('step')) || 0); setCalcMode(q.get('example') === 'calculation'); setQuery(''); };
    readURL(); setReady(true); addEventListener('popstate',readURL);
    fetch('/fixtures.json').then(r=> { if (!r.ok) throw Error('Saved results unavailable'); return r.json(); }).then(setData).catch(e=>setLoadError(e.message));
    return ()=>removeEventListener('popstate',readURL);
  }, []);
  useEffect(() => {
    if (!ready) return;
    const q = new URLSearchParams(); if(direction) q.set('direction',direction); q.set('view',view); q.set('scenario',scenarioId); q.set('step',String(stepIndex)); if(calcMode) q.set('example','calculation');
    history.replaceState(null, '', '?' + q.toString());
  }, [direction, view, scenarioId, stepIndex, calcMode, ready]);
  useEffect(() => { document.getElementById('main-content')?.scrollTo({top:0}); }, [scenarioId, stepIndex, calcMode, view]);
  if(loadError) return <div className="loading"><TriangleAlert/><h1>Saved results unavailable</h1><p>{loadError}</p><button onClick={()=>location.reload()}>Retry</button></div>;
  if(!data) return <div className="loading"><Fingerprint size={32}/><h1>Opening the research archive</h1><p>Loading preserved results and original evidence…</p></div>;
  const scenario = data.scenarios.find(s=>s.id===scenarioId) || data.scenarios[0];
  const step = calcMode ? data.calculation : scenario.steps[Math.min(Math.max(stepIndex,0),scenario.steps.length-1)];
  const r = step.result;
  const citationIds = citedIds(r);
  const activeId = citationIds.includes(selected) ? selected : citationIds[0];
  const facts = supportedFacts(r);
  const selectEvidence = id => {setSelected(id);setInspectorTab('excerpts');setMobileEvidence(true);};
  const openScenario = (id, index=0) => {setScenarioId(id);setStepIndex(index);setCalcMode(false);setView('research');setSelected('');setQuery('');setMobileEvidence(false);};
  const navigate = name => {setView(name);setQuery('');setHistoryPage(0);setMobileEvidence(false);};
  const allRuns = [...data.scenarios.flatMap(s=>s.steps.map((step,index)=>({...step,scenario:s,index}))), {...data.calculation,scenario:{id:'calculation',title:'Exact calculation'},index:0}].sort((a,b)=>(b.result.execution?.timestamp || '').localeCompare(a.result.execution?.timestamp || ''));
  const openRun = row => {if(row.scenario.id==='calculation'){setCalcMode(true);setView('research');setSelected('');}else openScenario(row.scenario.id,row.index);};
  const sourceMap = new Map();
  for(const row of allRuns) for(const item of row.result.inventory || []) {const pin = row.result.manifest.find(p=>p.source_id===item.source_id);if(pin && citedIds(row.result).some(id=>row.result.citations[id].source.source_hash===pin.source_hash)) sourceMap.set(pin.source_hash,{...item,pin,row});}
  const sources = Array.from(sourceMap.values()).filter(item => (companyFilter==='all' || item.metadata.company_id===companyFilter) && `${item.title} ${item.metadata.company_id} ${item.metadata.period_label}`.toLowerCase().includes(query.toLowerCase()));
  const savedRuns = allRuns.filter(row=>row.result.execution);
  const localResults = savedRuns.filter(row=>`${row.result.request.question} ${row.scenario.title} ${row.label} ${row.result.run_id}`.toLowerCase().includes(query.toLowerCase()));
  const inspectSource = item => {openRun(item.row);const id = citedIds(item.row.result).find(key=>item.row.result.citations[key].source.source_hash===item.pin.source_hash);if(id) {setSelected(id);setInspectorTab('excerpts');}setView('library');setMobileEvidence(true);};
  const inspect = <EvidenceInspector result={r} id={activeId} data={data} tab={inspectorTab} setTab={setInspectorTab} onSelect={selectEvidence} close={()=>setMobileEvidence(false)} />;
  if(!direction) return <DesignLab onChoose={setDirection} data={data} />;
  return <div className={`workspace ${direction}`}>
    <a className="skip-link" href="#main-content">Skip to research</a>
    <header className="topbar">
      <a className="wordmark" href="/" onClick={e=>{e.preventDefault();setDirection('');}}><span className="brand-mark"><Layers3 size={20}/></span>FinRAG<span className="wordmark-tag">RESEARCH WORKSPACE</span></a>
      {direction==='terminal' && <nav className="topnav" aria-label="Main navigation">{nav.map(([id,label,Icon])=><button key={id} className={view===id?'active':''} onClick={()=>navigate(id)}><Icon size={16}/>{label}</button>)}</nav>}
      <div className="top-actions"><span className="archive-status"><span className="status-dot"/>Preserved research</span><div className="direction-switch" aria-label="Visual direction"><button aria-pressed={direction==='folio'} onClick={()=>setDirection('folio')}>A · Folio</button><button aria-pressed={direction==='terminal'} onClick={()=>setDirection('terminal')}>B · Meridian</button></div><span className="avatar" title="Private research workspace">DL</span></div>
    </header>
    <div className="app-body">
      <aside className="sidebar">
        <div className="workspace-label"><span className="workspace-monogram">F</span><div>Financial research<small>Private workspace</small></div><ChevronDown size={14}/></div>
        {direction==='folio' && <nav aria-label="Main navigation">{nav.map(([id,label,Icon])=><button key={id} className={view===id?'active':''} onClick={()=>navigate(id)}><Icon size={17}/>{label}{id==='research'&&<span className="nav-dot"/>}</button>)}</nav>}
        <div className="sidebar-section"><span className="eyebrow">RESEARCH COLLECTIONS</span><button onClick={()=>openScenario('equity')}><FolderOpen size={15}/>Common equity</button><button onClick={()=>openScenario('recast')}><FolderOpen size={15}/>Revision-aware research</button><button onClick={()=>{setCalcMode(true);setView('research');setSelected('');setQuery('');}}><FolderOpen size={15}/>AMD · Revenue growth</button></div>
        <div className="sidebar-section hero-links"><span className="eyebrow">FIVE HERO SCENARIOS</span>{data.scenarios.map((s,i)=><button key={s.id} onClick={()=>openScenario(s.id)} className={!calcMode&&s.id===scenario.id?'current':''}><span className="scenario-num">0{i+1}</span>{s.title}</button>)}</div>
        <div className="sidebar-bottom"><ShieldCheck size={18}/><strong>Evidence, kept intact.</strong><p>Originals. Exact values.<br/>Immutable research.</p><a href="/?" onClick={e=>{e.preventDefault();setDirection('');}}>View design comparison <ArrowUpRight size={14}/></a><span className="prototype-label">LOCAL DESIGN PROTOTYPE</span></div>
      </aside>
      <section className="main-shell">
        <div className="contextbar"><span><BookOpen size={14}/>Workspace<ChevronRight size={12}/><strong>{nav.find(n=>n[0]===view)?.[1]}</strong></span><span className="context-note">{direction==='folio'?'A / Editorial research desk':'B / Analyst workbench'}<span className="divider-dot">·</span>Saved development evidence</span></div>
        <div className="mobile-nav">{nav.map(([id,label])=><button className={view===id?'active':''} key={id} onClick={()=>navigate(id)}>{label}</button>)}</div>
        <Group orientation="horizontal" className={`panel-group ${mobileEvidence?'show-mobile-evidence':''}`} id="research-evidence">
          <Panel id="results" defaultSize={direction==='folio'?'66%':'68%'} minSize="40%" className="result-panel">
            <main id="main-content" className="content-scroll">
              {view==='research' && <>
                <div className="page-heading"><div><span className="eyebrow">{calcMode?'CALCULATION NOTE':`RESEARCH NOTE / 0${data.scenarios.indexOf(scenario)+1}`}</span><h1>{calcMode?'Revenue growth, precisely.':scenario.title}</h1><p>{calcMode?'From reported operands to an auditable result.':scenario.subtitle}</p></div><button className="icon-button" aria-label="Export preserved result as JSON" onClick={()=>exportJSON(r)}><Download size={18}/></button></div>
                <div className="query-card"><div className="query-label"><Search size={16}/><span>RESEARCH QUESTION</span><Badge>Saved execution</Badge></div><p>{r.request.question}</p><div className="query-meta"><span>{[...new Set(r.manifest.map(p=>p.company_id))].join(' + ')}</span><span>{r.manifest.length} pinned sources</span><span>{tidy(r.request.revision_policy || 'period-bound narrative')}</span></div></div>
                {!calcMode && scenario.steps.length>1 && <div className="step-switch" aria-label="Scenario steps">{scenario.steps.map((s,i)=><button aria-pressed={stepIndex===i} key={s.case_id} onClick={()=>{setStepIndex(i);setSelected('');}}>{s.label}</button>)}</div>}
                {scenario.id==='change'&&!calcMode && <div className="source-change-banner"><History size={18}/><div><strong>{stepIndex===0?'This saved answer has a newer source version.':stepIndex===1?'A separate, parent-linked rerun.':'The original version remains queryable.'}</strong><p>{stepIndex===0?'The original answer stays unchanged. Open the preserved rerun to compare the reviewed recast.':stepIndex===1?'Reopened from the controlled source-change capture. The predecessor is retained.':'Explicit old-version pin. The reviewed recast does not overwrite this result.'}</p></div>{stepIndex===0&&<button onClick={()=>{setStepIndex(1);setSelected('');}}>Open saved rerun <ArrowRight size={15}/></button>}</div>}
                {scenario.id==='change'&&!calcMode && <div className="saved-comparison">{scenario.steps.slice(0,2).map((saved,i)=>{const fact=supportedFacts(saved.result)[0];return <button className={stepIndex===i?'active':''} key={saved.result.run_id} onClick={()=>{setStepIndex(i);setSelected('');}}><span>{i===0?'Saved original':'Reviewed saved rerun'}</span><strong>{exact(fact.value)} <small>{units(fact)}</small></strong><code>{short(saved.result.run_id)}</code><span>{i===0?'Original history retained':'Parent-linked execution'}</span></button>;})}</div>}
                {scenario.id==='change'&&!calcMode && <p className="small-note">Controlled local source-change capture · Saved lifecycle replay · No live URL refresh</p>}
                <div className="result-heading"><div><span className="eyebrow">RESEARCH RESULT</span><h2>{calcMode?'Reported revenue':r.claims?.length?'Reported operating-income headwinds':metricName(facts[0]?.metric_id || 'Supported financial evidence')}</h2></div><Badge tone={r.outcome==='answer'?'positive':'caution'}>{r.outcome==='answer'?<Check size={12}/>:<TriangleAlert size={12}/>} {r.outcome==='answer'?'Supported result':tidy(r.outcome)}</Badge></div>
                {facts.length>0 && <>
                  <div className="metric-cards">{facts.map((o,i)=><button key={o.observation_id} className={`metric-card ${o.observation_id===activeId?'selected':''}`} onClick={()=>selectEvidence(o.observation_id)}><div className="metric-top"><span className={`ticker ticker-${o.company_id}`}>{o.company_id}</span><span>{o.period.fiscal_label}<ArrowUpRight size={13}/></span></div><div className="metric-value">{exact(o.value)}<span className="inline-cite">[{citationIds.indexOf(o.observation_id)+1}]</span></div><div className="metric-bottom"><span>{units(o)}</span><span>{o.basis} · {o.scope}</span></div></button>)}</div>
                  <div className="data-layout"><FinancialTable facts={facts} result={r} selected={activeId} select={selectEvidence}/><Chart facts={facts} selected={activeId} select={selectEvidence}/></div>
                </>}
                {(r.claims || []).map((claim,i)=>{const task=r.request.tasks.find(t=>t.task_id===claim.task_id);return <article className="narrative-card" key={`${claim.task_id}-${claim.evidence_id}`}><div className="narrative-period"><span className="ticker ticker-TSLA">TSLA</span><h3>{task?.document_period_label || tidy(claim.task_id)}</h3><Badge tone="caution">Generated · unreviewed</Badge></div><p>{claim.text} <Citation id={claim.evidence_id} index={citationIds.indexOf(claim.evidence_id)+1} onSelect={selectEvidence} selected={activeId}/></p><button className="text-button" onClick={()=>selectEvidence(claim.evidence_id)}>Read exact original passage <ArrowRight size={14}/></button></article>;})}
                {r.claims?.length>0 && <p className="small-note">Preserved narrative draft. Original quotes are available for inspection; the draft does not establish the cause of a quarter-to-quarter change.</p>}
                {(r.calculations || []).map((calc,i)=><section className="calculation-card" key={i}><div className="section-title"><span><Fingerprint size={16}/>Calculation receipt</span><Badge>Backend Decimal</Badge></div><div className="calculation-value">{calc.displayed_result}<span>{tidy(calc.operation)}</span></div><code>{calc.formula}</code><div className="operand-list">{calc.observation_ids.map((id,index)=><div key={id}><span>{index===0?'Start operand':'End operand'}</span><strong>{exact(calc.normalized_operands[index])}</strong><Citation id={id} index={citationIds.indexOf(id)+1} onSelect={selectEvidence} selected={activeId}/></div>)}</div><details><summary>Full precision & policy</summary><div className="mono wrap">{calc.result}</div><p>{calc.policy_version} · {calc.period_policy} · {calc.unit}</p></details>{calc.limitations.map((x,i)=><p className="small-note" key={i}>{x}</p>)}</section>)}
                <Coverage result={r}/>
                {r.ranking?.length>0 && <div className="ranking-note"><CheckCheck size={18}/><div><strong>Complete, comparable ranking</strong><p>{r.ranking.map(taskId=>names[r.request.tasks.find(t=>t.task_id===taskId)?.company_id] || taskId).join(' → ')} · Order returned by the backend.</p></div></div>}
                <div className="reproducibility"><span><Fingerprint size={14}/>Immutable result <code>{short(r.run_id)}</code></span><span>{stamp(r)}<span className="divider-dot">·</span>{step.case_id}</span></div>
                <details className="raw-result"><summary>View preserved answer & provenance</summary><pre>{r.answer}</pre><p>Capture: <code>{step.artifact}</code></p><p>Run: <code>{r.run_id}</code></p><button className="text-button" onClick={()=>exportJSON(r)}>Export exact saved JSON <Download size={14}/></button></details>
              </>}
              {view==='library' && <>
                <div className="page-heading"><div><span className="eyebrow">YOUR EVIDENCE BASE</span><h1>Source Library</h1><p>Research begins with an original.</p></div><Badge>{sourceMap.size} preserved source versions</Badge></div>
                <div className="library-summary"><FileText size={30}/><div><strong>Official reports. Pinned versions.</strong><p>This prototype shows only sources used by the saved examples. Private ingestion and review stay in Streamlit.</p></div></div>
                <div className="filterbar"><label className="search-input"><Search size={16}/><input aria-label="Search source library" placeholder="Search reports, companies, periods…" value={query} onChange={e=>setQuery(e.target.value)}/></label><select aria-label="Filter source company" value={companyFilter} onChange={e=>setCompanyFilter(e.target.value)}><option value="all">All companies</option>{Object.entries(names).map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></div>
                <div className="source-list">{sources.map(item=><article className="source-card" key={item.pin.source_hash}><div className="file-icon"><FileText size={23}/></div><div className="source-info"><h3>{tidy(item.title)}</h3><p>{item.metadata.period_label} · {tidy(item.metadata.document_type)} · Published {item.pin.publication_date}</p><div><Badge tone="positive"><ShieldCheck size={11}/>Confirmed metadata</Badge><span className="small-note">Version {short(item.pin.version_id)}</span></div></div><button className="text-button" onClick={()=>inspectSource(item)}>Inspect <ArrowUpRight size={15}/></button></article>)}</div>{!sources.length&&<Empty text="No preserved sources match your filters."/>}
              </>}
              {view==='history' && <>
                <div className="page-heading"><div><span className="eyebrow">THE RESEARCH RECORD</span><h1>Saved History</h1><p>Reopen the answer as it was. Every time.</p></div><History size={28}/></div>
                <div className="history-banner"><Fingerprint size={20}/><div><strong>Immutable answers, separate reruns.</strong><p>{savedRuns.length} preserved saved executions. Source changes never rewrite a saved result.</p></div></div>
                <label className="search-input"><Search size={16}/><input aria-label="Search saved history" placeholder="Search saved questions, scenarios or run IDs…" value={query} onChange={e=>{setQuery(e.target.value);setHistoryPage(0);}}/></label>
                <div className="history-list">{localResults.slice(historyPage*5,historyPage*5+5).map(row=><button className="history-card" onClick={()=>openRun(row)} key={row.result.run_id}><div className="history-date"><Clock3 size={16}/><span>{stamp(row.result)}</span></div><div className="history-info"><span className="eyebrow">{row.scenario.title}</span><h3>{row.result.request.question}</h3><div><Badge tone={row.result.outcome==='answer'?'positive':'caution'}>{tidy(row.result.outcome)}</Badge><span>{row.label}</span>{row.result.execution?.parent_run_id&&<Badge><History size={11}/>Parent-linked rerun</Badge>}</div><code>{short(row.result.run_id)}</code></div><ArrowUpRight size={18}/></button>)}</div>{!localResults.length&&<Empty text="No saved questions match this search."/>}
                <div className="pagination"><span>{localResults.length} matching saved results</span><button disabled={historyPage===0} onClick={()=>setHistoryPage(p=>p-1)}><ArrowLeft size={14}/>Previous</button><span>Page {historyPage+1} of {Math.max(1,Math.ceil(localResults.length/5))}</span><button disabled={(historyPage+1)*5>=localResults.length} onClick={()=>setHistoryPage(p=>p+1)}>Next<ArrowRight size={14}/></button></div>
              </>}
              {view==='heroes' && <>
                <div className="page-heading"><div><span className="eyebrow">FINRAG IN PRACTICE</span><h1>Five research stories</h1><p>A workspace built around evidence, not conversation.</p></div><FlaskConical size={30}/></div>
                <p className="intro-copy">Explore preserved development results. Compare exact metrics, trace a recast, inspect a reported claim, and reopen a result after its source changes.</p>
                <div className="hero-grid">{data.scenarios.map((s,i)=><button className="hero-card" key={s.id} onClick={()=>openScenario(s.id)}><span className="hero-number">0{i+1}</span><div><h2>{s.title}</h2><p>{s.subtitle}</p><span className="hero-meta">{s.steps.length} preserved {s.steps.length===1?'step':'steps'}<span>Original evidence</span></span></div><ArrowUpRight size={21}/></button>)}</div><div className="small-note">These five scenarios reuse existing development cases. They are not five new accuracy cases or independent financial review.</div>
              </>}
              <footer className="page-footer"><span><ShieldCheck size={13}/>Read-only design prototype</span><span>Preserved development captures · No fresh generation</span></footer>
            </main>
          </Panel>
          <Separator aria-label="Resize Evidence Inspector" className="resize-handle"><GripVertical size={12}/></Separator>
          <Panel id="evidence" defaultSize={direction==='folio'?'34%':'32%'} minSize="25%" maxSize="55%" className="evidence-panel">{inspect}</Panel>
        </Group>
        <button className="mobile-evidence-button" onClick={()=>setMobileEvidence(v=>!v)}><BookOpen size={16}/>{mobileEvidence?'Return to results':'Inspect evidence'}</button>
      </section>
    </div>
  </div>;
}

function FinancialTable({facts, result, selected, select}) {
  const ids=citedIds(result);
  return <section className="financial-table"><div className="section-title"><span><Table2 size={16}/>Reported facts</span><span className="small-note">Exact values</span></div><div className="table-scroll"><table><thead><tr><th>Company / period</th><th className="numeric">Amount</th><th>Original</th></tr></thead><tbody>{facts.map(o=><tr key={o.observation_id} className={selected===o.observation_id?'selected':''}><td><strong>{names[o.company_id] || o.company_id}</strong><small>{o.period.fiscal_label}</small><small>{o.period.start} — {o.period.end}</small><small>{o.period.calendar} · {o.scope} · {o.basis}</small></td><td className="numeric"><strong>{exact(o.value)}</strong><small>{units(o)}</small></td><td><Citation id={o.observation_id} index={ids.indexOf(o.observation_id)+1} onSelect={select} selected={selected}/><small>p. {o.evidence.find(e=>e.role==='value')?.page_number ?? '—'}</small></td></tr>)}</tbody></table></div></section>;
}
function Chart({facts, selected, select}) {
  // Number conversion is solely pixel geometry. Exact values remain preserved strings.
  if(facts.length<2 || new Set(facts.map(o=>`${o.metric_id}:${o.unit}:${o.currency}:${o.scale}:${o.basis}:${o.scope}`)).size!==1) return null;
  const max=Math.max(...facts.map(o=>Math.abs(Number(o.value)))); if(!Number.isFinite(max)||max===0||facts.some(o=>Number(o.value)<0)) return null;
  return <section className="chart-card"><div className="section-title"><span>Reported amounts</span><span className="small-note">{units(facts[0])}</span></div><div className="chart-grid" aria-label="Reported amounts chart; zero baseline">{facts.map(o=><button className={`chart-row ${selected===o.observation_id?'selected':''}`} key={o.observation_id} onClick={()=>select(o.observation_id)} title={`${o.company_id} ${o.period.fiscal_label}: ${exact(o.value)} ${units(o)}`}><span className="chart-label">{o.company_id}<small>{o.period.fiscal_label}</small></span><div className="bar-track"><span className={`bar bar-${o.company_id}`} style={{width:`${Math.abs(Number(o.value))/max*100}%`}}/></div><strong>{exact(o.value)}</strong></button>)}</div><div className="chart-axis"><span>0</span><span>{exact(String(max))}</span></div><p className="small-note">Select a bar to inspect its original. No inferred trend or growth.</p></section>;
}
function Coverage({result}) {
  const coverage=result.coverage || [], gaps=result.calculation_gaps || [];
  return <section className="coverage-card"><div className="section-title"><span><ShieldCheck size={16}/>Evidence coverage</span><span>{coverage.filter(c=>c.status==='supported').length} / {coverage.length} tasks supported</span></div>{coverage.map(c=>{const task=result.request.tasks.find(t=>t.task_id===c.task_id);return <div className="coverage-row" key={c.task_id}><span className={`coverage-icon ${c.status==='supported'?'positive':'caution'}`}>{c.status==='supported'?<Check size={14}/>:<TriangleAlert size={14}/>}</span><div><strong>{names[task?.company_id] || task?.company_id} · {task?.period?.fiscal_label || task?.document_period_label || c.task_id}</strong><p>{c.reason}</p></div><Badge tone={c.status==='supported'?'positive':'caution'}>{tidy(c.status)}</Badge></div>;})}{gaps.map((g,i)=><div className="gap-row" key={i}><TriangleAlert size={15}/><span><strong>{tidy(g.operation)} withheld.</strong> {g.reason}</span></div>)}</section>;
}
function Empty({text}) {return <div className="empty-state"><Search size={28}/><h3>{text}</h3><p>Try another term or clear the filter.</p></div>;}

function EvidenceInspector({result:r, id, data, tab, setTab, onSelect, close}) {
  const citation=r.citations?.[id], ids=citedIds(r), index=ids.indexOf(id)+1;
  if(!citation) return <aside className="inspector"><div className="inspector-heading"><BookOpen size={17}/><strong>Evidence Inspector</strong></div><Empty text="No cited original in this result."/></aside>;
  const observation=(r.observations || []).find(o=>o.observation_id===id);
  const source=citation.source, inventory=r.inventory.find(item=>item.source_id===source.source_id), original=data.originals[source.source_hash];
  const valueEvidence=citation.evidence?.find(e=>e.role==='value');
  const page=valueEvidence?.page_number ?? citation.page_number;
  const claim=(r.claims || []).find(c=>c.evidence_id===id);
  const evidence=citation.evidence || [{role:'original passage',text:citation.text,page_number:citation.page_number,block_id:citation.block_id,char_start:citation.char_start,char_end:citation.char_end}];
  return <aside className="inspector" aria-label="Evidence Inspector">
    <div className="inspector-heading"><span><BookOpen size={17}/><strong>Evidence Inspector</strong></span><button className="icon-button mobile-close" onClick={close} aria-label="Return to research"><ArrowLeft size={17}/></button><Badge>ORIGINAL</Badge></div>
    <div className="citation-selector"><span className="eyebrow">CITED EVIDENCE{r.passages?.length ? ` · ${r.passages.length} candidates in saved export` : ''}</span><div>{ids.map((key,i)=><button key={key} aria-pressed={key===id} aria-label={`Select citation ${i+1}`} onClick={()=>onSelect(key)}>[{i+1}]</button>)}</div></div>
    <div className="inspector-source"><span className={`ticker ticker-${source.company_id}`}>{source.company_id}</span><h2>{tidy(inventory?.title || 'Original report')}</h2><p>{tidy(inventory?.metadata?.document_type)} · {inventory?.metadata?.period_label} · Page {page ?? '—'}</p><div><Badge tone={observation?'positive':'caution'}>{observation?<ShieldCheck size={12}/>:<TriangleAlert size={12}/>} {observation?'Reviewed fact binding':'Generated claim · unreviewed'}</Badge></div></div>
    <div className="inspector-tabs" aria-label="Evidence view">{[['excerpts','Excerpts'],['page','Source page'],['provenance','Provenance']].map(([key,label])=><button key={key} aria-pressed={tab===key} onClick={()=>setTab(key)}>{label}</button>)}</div>
    <div className="inspector-scroll" key={id+'-'+tab}>
      {tab==='excerpts' && <>
        <div className="original-excerpts"><div className="paper-heading"><FileText size={14}/><span>EXACT ORIGINAL EXCERPTS</span><span>[{index}]</span></div>{observation && <div className="bound-value"><span>{observation.original_label}</span><strong>{exact(observation.value)}</strong><small>{units(observation)} · {observation.period.fiscal_label}</small></div>}
          {evidence.map((e,i)=><div className={`evidence-excerpt role-${e.role}`} key={i}><div><span>{tidy(e.role)}</span><span>p. {e.page_number ?? '—'}</span></div><blockquote>{e.text}</blockquote><small>{e.row_index!==null && e.row_index!==undefined ? `Row ${e.row_index}, column ${e.column_index} · ` : e.char_start!==null&&e.char_start!==undefined ? `Characters ${e.char_start}–${e.char_end} · ` : ''}{e.block_id}</small></div>)}</div>
        <div className="inspector-note"><ShieldCheck size={16}/><p>{observation?'The value, row label, period, unit, scope and basis have separate original bindings. Review provenance is available in the next tab.':'This original supports a preserved generated draft. Inspect the period and quote; source location alone does not prove semantic correctness.'}</p></div>
        {observation?.supersedes_observation_ids?.length>0 && <section className="lineage"><h3><History size={15}/>Reviewed revision lineage</h3><p>Supersedes {observation.supersedes_observation_ids.map(short).join(', ')}</p>{(observation.revision_evidence || []).map((e,i)=><blockquote key={i}>{e.text}</blockquote>)}</section>}
        {claim&&<details><summary>Preserved claim quote</summary><blockquote>{claim.quote}</blockquote><p>Review status: {tidy(claim.review_status || r.synthesis_review_status)}</p></details>}
      </>}
      {tab==='page' && <><p className="small-note">Retained original bytes · Page {page ?? 'not specified'} · SHA-256 checked during fixture export.</p>{data.pages?.[`${source.source_hash}:${page}`] && <a className="page-preview" href={`${original.local_url}#page=${page}`} target="_blank" rel="noreferrer"><img src={data.pages[`${source.source_hash}:${page}`]} alt={`Retained original report page ${page}: ${inventory?.title}`}/></a>}<a className="primary-button original-link" href={`${original.local_url}#page=${page || 1}`} target="_blank" rel="noreferrer">Open retained original PDF <ArrowUpRight size={15}/></a><p className="small-note">Original page image; no synthetic highlight or reconstructed table.</p></>}
      {tab==='provenance' && <><div className="provenance-card"><Fingerprint size={24}/><h3>Pinned, traceable evidence</h3><p>These identities belong to the saved result. They do not follow the active source pointer.</p></div><dl className="provenance-list">{Object.entries({source_id:source.source_id,version_id:source.version_id,build_id:source.build_id,sha256:source.source_hash,publication_date:source.publication_date,observation_id:observation?.observation_id,review_revision:observation?.review_revision,run_id:r.run_id,parent_run_id:r.execution?.parent_run_id}).filter(([,v])=>v).map(([k,v])=><div key={k}><dt>{tidy(k)}</dt><dd>{v}</dd></div>)}</dl><div className="small-note">Named Codex development review; no independent release review.</div></>}
    </div>
    <div className="inspector-footer"><span><Fingerprint size={13}/>{short(source.source_hash)}</span><a href={`${original.local_url}#page=${page || 1}`} target="_blank" rel="noreferrer">Open original <ArrowUpRight size={13}/></a></div>
  </aside>;
}

function DesignLab({onChoose, data}) {
  return <div className="design-lab"><header><span className="wordmark"><span className="brand-mark"><Layers3 size={20}/></span>FinRAG</span><span className="eyebrow">DESIGN INVESTIGATION / OCTOBER 2026</span></header><main><span className="eyebrow">TWO DIRECTIONS. ONE EVIDENCE STANDARD.</span><h1>A better place to<br/>do financial research.</h1><p className="lab-intro">A structured research workspace with the original always in reach. Explore two functional directions, using FinRAG’s preserved results.</p><div className="design-options">{[['folio','A','Folio','The editorial research desk.','Warm paper, deep green, generous reading rhythm. A financial research note with a persistent evidence margin.'],['terminal','B','Meridian','The analyst workbench.','Midnight slate, cool blue, compact typography. Exact tables, comparison charts and source bindings at working density.']].map(([id,letter,title,subtitle,desc])=><button className={`design-option option-${id}`} key={id} onClick={()=>onChoose(id)}><div className="direction-title"><span>{letter}</span><h2>{title}</h2><ArrowUpRight size={24}/></div><div className="mock-preview"><div className="mock-sidebar">F<small>Research</small><small>Library</small><small>History</small></div><div className="mock-body"><small>RESEARCH NOTE</small><strong>Common-equity comparison</strong><div className="mock-values"><span>1,172<small>TSLA · USD m</small></span><span>5,214<small>WFC · USD m</small></span></div><div className="mock-lines"><i/><i/><i/></div></div><div className="mock-evidence"><small>ORIGINAL EVIDENCE</small><div>Net income<br/>applicable to<br/>common stock</div><strong>5,214</strong><small>p. 58</small></div></div><h3>{subtitle}</h3><p>{desc}</p><span className="design-open">Open functional prototype <ArrowRight size={17}/></span></button>)}</div><section className="lab-principles"><div><BookOpen size={20}/><h3>Evidence stays beside you</h3><p>Resize the inspector. Open any citation. Read exact excerpts and retained original pages.</p></div><div><Fingerprint size={20}/><h3>Precision has a visible shape</h3><p>Financial values, fiscal intervals, Decimal receipts and review qualifications stay explicit.</p></div><div><History size={20}/><h3>History keeps its promise</h3><p>A source can change. A saved result stays intact. Reruns have their own provenance.</p></div></section><p className="small-note">Read-only prototypes · {data.scenarios.length} preserved Hero scenarios · Existing development evidence · No new financial inference</p></main></div>;
}
