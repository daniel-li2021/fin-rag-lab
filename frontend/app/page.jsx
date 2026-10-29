"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "../lib/client.mjs";
import OriginalPage from "./components/pdf-page";
import { Group, Panel, Separator } from "react-resizable-panels";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Download,
  FileText,
  Fingerprint,
  FlaskConical,
  FolderOpen,
  GripVertical,
  History,
  Layers3,
  LibraryBig,
  Search,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import {
  Badge,
  EvidenceInspector,
  ResultView,
  citedIds,
  exact,
  exportJSON,
  short,
  supportedFacts,
  tidy,
} from "./components/results";

const navigation = [
  ["research", "Research", Search],
  ["library", "Library", LibraryBig],
  ["history", "History", History],
  ["heroes", "Hero Scenarios", FlaskConical],
];
export default function Workspace() {
  const [archive, setArchive] = useState(null),
    [view, setView] = useState("research");
  const [archiveStatus, setArchiveStatus] = useState("loading"),
    [retryRead, setRetryRead] = useState(null),
    [openingRun, setOpeningRun] = useState(false);
  const [sources, setSources] = useState([]),
    [collections, setCollections] = useState([]),
    [connection, setConnection] = useState("Connecting");
  const [modes, setModes] = useState({ research: "demo", library: "demo", history: "demo", collections: "demo", evidence: "demo" });
  const [live, setLive] = useState(null),
    [hero, setHero] = useState(null),
    [heroStep, setHeroStep] = useState(0);
  const [selected, setSelected] = useState(""),
    [tab, setTab] = useState("excerpts"),
    [mobileEvidence, setMobileEvidence] = useState(false);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [query, setQuery] = useState("");
  const [rows, setRows] = useState([]),
    [offset, setOffset] = useState(0),
    [historyQuery, setHistoryQuery] = useState(""),
    [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(""),
    [historyRetry, setHistoryRetry] = useState(0);
  const [librarySource, setLibrarySource] = useState(null),
    [pins, setPins] = useState({}),
    [collectionId, setCollectionId] = useState("");
  const [comparison, setComparison] = useState(null),
    [composer, setComposer] = useState(true),
    [initialized, setInitialized] = useState(false);
  const locked = useRef(false);
  const urlRequest = useRef(null), evidenceTrigger = useRef(null);
  const result = composer ? null : hero
    ? hero === "calculation"
      ? archive?.calculation.result
      : archive?.scenarios.find((s) => s.id === hero)?.steps[
          Math.min(
            heroStep,
            (archive?.scenarios.find((s) => s.id === hero)?.steps.length || 1) -
              1,
          )
        ]?.result
    : live?.payload;
  const scenario = archive?.scenarios.find((s) => s.id === hero);
  const stepIndex = Math.min(heroStep, Math.max(0, (scenario?.steps.length || 1) - 1));
  const ids = result ? citedIds(result) : [];
  const activeId = ids.includes(selected) ? selected : ids[0];
  function openInspector() {
    if (!mobileEvidence) evidenceTrigger.current = document.activeElement;
    setMobileEvidence(true);
  }
  function closeInspector() {
    setMobileEvidence(false);
    if (matchMedia("(max-width: 760px)").matches)
      requestAnimationFrame(() => evidenceTrigger.current?.focus());
  }
  const openEvidence = (id) => {
    setSelected(id);
    setTab("excerpts");
    openInspector();
  };
  function route(nextView, values = {}) {
    urlRequest.current?.abort();
    setOpeningRun(false);
    setView(nextView);
    setQuery("");
    setMobileEvidence(false);
    const q = new URLSearchParams({ view: nextView, ...values });
    history.pushState(null, "", "?" + q);
  }
  function startResearch() {
    setHero(null);
    setLive(null);
    setSelected("");
    setComparison(null);
    setLibrarySource(null);
    setComposer(true);
    navigate("research");
  }
  function showLive(row, diff = null, writeURL = true) {
    setLive(row);
    setHero(null);
    setSelected("");
    setTab("excerpts");
    setComparison(diff);
    setComposer(false);
    setLibrarySource(null);
    if (writeURL)
      route(
        "research",
        row.payload.execution ? { run: row.payload.run_id } : {},
      );
    else setView("research");
  }
  function showHero(id, index = 0) {
    setHero(id);
    setHeroStep(index);
    setSelected("");
    setComparison(null);
    setLibrarySource(null);
    setComposer(false);
    route("research", { hero: id, step: String(index) });
  }
  async function action(operation, retry = null) {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setError("");
    setRetryRead(null);
    try {
      await operation();
    } catch (e) {
      setError(e.message);
      setRetryRead(() => retry);
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }
  async function reopen(run, writeURL = true) {
    await action(async () =>
      showLive(await api(`research/runs/${run}`), null, writeURL),
      () => reopen(run, writeURL),
    );
  }
  function navigate(next) {
    setError("");
    setRetryRead(null);
    route(next);
  }
  function reconnect() {
    action(connect, reconnect);
  }
  async function connect() {
    const health = await api("health");
    setModes(health.capabilities);
    setConnection(Object.values(health.capabilities).includes("live") ? "Demo + private live" : "Saved public demo");
    const [s, c] = await Promise.allSettled([
      api("sources"),
      api("research/collections"),
    ]);
    if (s.status === "fulfilled") setSources(s.value);
    if (c.status === "fulfilled") setCollections(c.value);
    if (s.status === "rejected" || c.status === "rejected")
      throw Error("A workspace capability is unavailable. Preserved research stories remain available; reconnect to reload sources and collections.");
  }
  async function loadArchive(signal) {
    setArchiveStatus("loading");
    try {
      const response = await fetch("/fixtures.json", { signal });
      if (!response.ok) throw Error("Archive unavailable");
      setArchive(await response.json());
      setArchiveStatus("ready");
    } catch (e) {
      if (e.name !== "AbortError") setArchiveStatus("error");
    }
  }
  useEffect(() => {
    const controller = new AbortController();
    loadArchive(controller.signal);
    connect().catch((e) => {
      setConnection("Backend unavailable");
      setError(e.message);
      setRetryRead(() => reconnect);
    });
    async function readURL() {
      urlRequest.current?.abort();
      const request = new AbortController();
      urlRequest.current = request;
      const q = new URLSearchParams(location.search),
        next = q.get("view");
      setView(navigation.some((n) => n[0] === next) ? next : "research");
      setQuery("");
      setMobileEvidence(false);
      setLive(null);
      setHero(null);
      setSelected("");
      setComparison(null);
      setLibrarySource(null);
      setError("");
      setRetryRead(null);
      setComposer(true);
      setOpeningRun(false);
      if (
        [
          "equity",
          "recast",
          "partial",
          "narrative",
          "change",
          "calculation",
        ].includes(q.get("hero"))
      ) {
        setHero(q.get("hero"));
        setHeroStep(Math.max(0, Math.min(2, Number(q.get("step")) || 0)));
        setComposer(false);
      } else if (q.get("run")) {
        setComposer(false);
        setOpeningRun(true);
        try {
          const row = await api(`research/runs/${encodeURIComponent(q.get("run"))}`, undefined, request.signal);
          if (!request.signal.aborted) showLive(row, null, false);
        } catch (e) {
          if (request.signal.aborted) return;
          setError(e.message);
          setRetryRead(() => () => reopen(q.get("run")));
        } finally {
          if (!request.signal.aborted) setOpeningRun(false);
        }
      }
      else {
        setHero(!next ? "equity" : null);
        setComposer(Boolean(next));
      }
    }
    readURL().finally(() => setInitialized(true));
    addEventListener("popstate", readURL);
    return () => {
      controller.abort();
      urlRequest.current?.abort();
      removeEventListener("popstate", readURL);
    };
  }, []);
  useEffect(() => {
    if (view !== "history" || !initialized) return;
    const c = new AbortController();
    setHistoryLoading(true);
    setHistoryError("");
    setRows([]);
    const timer = setTimeout(
      () =>
        api(
          `research/runs?offset=${offset}&search=${encodeURIComponent(historyQuery)}`,
          undefined,
          c.signal,
        )
          .then(setRows)
          .catch((e) => {
            if (!c.signal.aborted) setHistoryError(e.message);
          })
          .finally(() => {
            if (!c.signal.aborted) setHistoryLoading(false);
          }),
      250,
    );
    return () => {
      c.abort();
      clearTimeout(timer);
    };
  }, [view, offset, historyQuery, initialized, historyRetry]);
  useEffect(() => {
    if (!mobileEvidence || !matchMedia("(max-width: 760px)").matches) return;
    document.querySelector(".evidence-panel .mobile-close")?.focus();
    const escape = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        closeInspector();
      }
    };
    addEventListener("keydown", escape);
    return () => removeEventListener("keydown", escape);
  }, [mobileEvidence]);
  useEffect(() => {
    document.getElementById("main-content")?.scrollTo({ top: 0 });
  }, [view, result?.run_id]);

  async function rerun() {
    await action(async () => {
      const previous = result,
        response = await api(`research/runs/${result.run_id}/rerun`, {});
      const row = await api(`research/runs/${response.result.run_id}`);
      showLive(row, {
        previous,
        current: response.result,
        diff: response.diff,
      });
    });
  }
  function useSource(source, version = "") {
    setCollectionId("");
    setPins((p) => ({ ...p, [source.source_id]: version }));
    setHero(null);
    setComposer(true);
    route("research");
  }
  const liveSources = sources.filter((s) =>
    `${s.title} ${s.metadata.company_id || ""} ${s.metadata.period_label || ""}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  const inspector =
    librarySource && view === "library" ? (
      <SourceInspector
        key={librarySource.source_id}
        source={librarySource}
        onUse={useSource}
        close={closeInspector}
      />
    ) : result ? (
      <EvidenceInspector
        result={result}
        id={activeId}
        data={hero || live?.demo ? archive : null}
        tab={tab}
        setTab={setTab}
        onSelect={openEvidence}
        close={closeInspector}
      />
    ) : (
      <aside className="inspector inspector-welcome">
        <BookOpen size={26} />
        <h2>Your evidence, within reach.</h2>
        <p>
          Run a research question or open a saved result. Every citation leads
          to its pinned original.
        </p>
        <span className="small-note">
          Exact saved values and calculations, preserved from FastAPI.
        </span>
      </aside>
    );

  return (
    <div className="workspace terminal">
      <a className="skip-link" href="#main-content">
        Skip to research
      </a>
      <header className="topbar">
        <a
          className="wordmark"
          href="/"
          onClick={(e) => {
            e.preventDefault();
            navigate("research");
          }}
        >
          <span className="brand-mark">
            <Layers3 size={20} />
          </span>
          FinRAG<span className="wordmark-tag">RESEARCH WORKSPACE</span>
        </a>
        <nav className="topnav" aria-label="Main navigation">
          {navigation.map(([id, label, Icon]) => (
            <button
              key={id}
              disabled={busy}
              aria-current={view === id ? "page" : undefined}
              className={view === id ? "active" : ""}
              onClick={() => navigate(id)}
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </nav>
        <div className="top-actions">
          <span className="connection-status">
            <span
              className={`status-dot ${connection.includes("unavailable") ? "offline" : ""}`}
            />
            {connection}
          </span>
          <span className="avatar" title="FinRAG portfolio demonstration">
            F
          </span>
        </div>
      </header>
      <div className="app-body">
        <aside className="sidebar">
          <div className="workspace-label">
            <span className="workspace-monogram">F</span>
            <div>
              Financial research<small>Meridian · Public demonstration</small>
            </div>
          </div>
          <button
            className="new-research"
            disabled={busy}
            onClick={startResearch}
          >
            <Search size={15} />
            {modes.research === "live" ? "New research" : "Explore research"}
          </button>
          <div className="sidebar-section">
            <span className="eyebrow">COLLECTIONS · {modes.collections.toUpperCase()}</span>
            {collections.map((c) => (
              <button
                key={c.collection_id}
                disabled={busy}
                onClick={() => {
                  setCollectionId(c.collection_id);
                  setPins({});
                  setHero(null);
                  setComposer(true);
                  route("research");
                }}
              >
                <FolderOpen size={14} />
                {c.name}
              </button>
            ))}
            {!collections.length && (
              <p className="small-note">
                Named collections are available in the private live workspace.
              </p>
            )}
          </div>
          <div className="sidebar-section hero-links">
            <span className="eyebrow">RESEARCH STORIES</span>
            {archive?.scenarios.map((s, i) => (
              <button
                key={s.id}
                disabled={busy}
                onClick={() => showHero(s.id)}
                className={hero === s.id ? "current" : ""}
              >
                <span className="scenario-num">0{i + 1}</span>
                {s.title}
              </button>
            ))}
          </div>
          <div className="sidebar-bottom">
            <ShieldCheck size={18} />
            <strong>Evidence, kept intact.</strong>
            <p>
              Originals. Exact values.
              <br />
              Immutable research.
            </p>
            <span className="small-note">
              Private administration stays in Streamlit.
            </span>
          </div>
        </aside>
        <section className="main-shell">
          <div className="contextbar">
            <span>
              <BookOpen size={14} />
              Workspace
              <strong> / {navigation.find((n) => n[0] === view)?.[1]}</strong>
            </span>
            <span className="context-note">
              {hero && view === "research"
                ? "Preserved development walkthrough"
                : `${modes[view] || "demo"} · ${modes[view] === "live" ? "Private access required" : "Preserved public evidence"}`}
            </span>
          </div>
          <div className="mobile-nav">
            {navigation.map(([id, label]) => (
              <button
                disabled={busy}
                className={view === id ? "active" : ""}
                key={id}
                onClick={() => navigate(id)}
              >
                {label}
              </button>
            ))}
          </div>
          <Group
            orientation="horizontal"
            className={`panel-group ${mobileEvidence ? "show-mobile-evidence" : ""}`}
            id="research-evidence"
          >
            <Panel
              id="results"
              defaultSize="66%"
              minSize="40%"
              className="result-panel"
            >
              <main id="main-content" className="content-scroll" tabIndex={-1}>
                {archiveStatus === "error" && (
                  <div className="error-banner" role="alert">
                    <TriangleAlert size={18} />
                    <div><strong>Saved stories could not load</strong><p>Retry the archive. Library and History remain available.</p></div>
                    <button disabled={busy} onClick={() => loadArchive()}>Retry archive</button>
                  </div>
                )}
                {error && (
                  <div className="error-banner" role="alert">
                    <TriangleAlert size={18} />
                    <div>
                      <strong>Request could not complete</strong>
                      <p>{error}</p>
                    </div>
                    {retryRead && <button disabled={busy} onClick={retryRead}>Retry loading</button>}
                    <button
                      aria-label="Dismiss error"
                      onClick={() => setError("")}
                    >
                      ×
                    </button>
                  </div>
                )}
                {busy && (
                  <p className="pending-message" role="status">
                    Request in progress. Your current view and selections are retained.
                  </p>
                )}
                {view === "research" && (
                  <>
                    <div className="page-heading">
                      <div>
                        <span className="eyebrow">
                          {hero
                            ? "PRESERVED RESEARCH STORY"
                            : "FINANCIAL RESEARCH"}
                        </span>
                        <h1>
                          {hero === "calculation"
                            ? "Revenue growth, precisely."
                            : scenario?.title || "The research desk"}
                        </h1>
                        <p>
                          {scenario?.subtitle ||
                            "Exact answers. Inspectable evidence. A record you can trust."}
                        </p>
                      </div>
                      {!composer && (
                        <button
                          className="text-button new-question"
                          disabled={busy}
                          onClick={startResearch}
                        >
                          {modes.research === "live" ? "New research" : "Explore research"} <Search size={14} />
                        </button>
                      )}
                      {result && (
                        <button
                          className="icon-button"
                          aria-label="Export exact result JSON"
                          onClick={() => exportJSON(result)}
                        >
                          <Download size={18} />
                        </button>
                      )}
                    </div>
                    <details className="workflow-guide">
                      <summary>How to use this workspace</summary>
                      <ol>
                        <li><strong>Choose a story.</strong> Explore a saved comparison, revision, partial answer or narrative. Private live access is required for new questions.</li>
                        <li><strong>Check the evidence.</strong> Select an amount or numbered citation to read its exact source excerpts. Use Provenance for source and version identities.</li>
                        <li><strong>Follow the record.</strong> Open History to revisit the original answer. A rerun has its own identity; it never replaces the original.</li>
                      </ol>
                      <p className="small-note">These are saved development examples. Opening them creates no fresh execution. Generated narrative drafts remain unreviewed.</p>
                    </details>
                    {openingRun && <p role="status">Opening saved research…</p>}
                    {composer && modes.research === "demo" && (
                      <div className="archive-notice"><FlaskConical size={18} /><div>
                        <strong>Explore preserved research</strong>
                        <p>Choose a research story below. New questions, AI generation and reruns require private live access; opening a demo creates no new execution.</p>
                      </div><button onClick={() => navigate("heroes")}>All five scenarios <ArrowRight size={14} /></button></div>
                    )}
                    {composer && modes.research === "live" && (
                      <ResearchComposer
                        sources={sources}
                        collections={collections}
                        pins={pins}
                        setPins={setPins}
                        collectionId={collectionId}
                        setCollectionId={setCollectionId}
                        busy={busy}
                        onSubmit={(body) =>
                          action(async () => {
                            const { mode, ...request } = body;
                            const payload = await api(
                              mode === "evidence"
                                ? "research/evidence/runs"
                                : "research/questions",
                              request,
                            );
                            showLive(
                              payload.execution
                                ? await api(`research/runs/${payload.run_id}`)
                                : { payload },
                            );
                          })
                        }
                      />
                    )}
                    {hero && result && (
                      <>
                        <div className="archive-notice">
                          <FlaskConical size={17} />
                          <div>
                            <strong>Preserved development result</strong>
                            <p>
                              This walkthrough reopens the original capture. It
                              does not execute a new question or alter live
                              sources.
                            </p>
                          </div>
                          <button
                            className="text-button"
                            onClick={startResearch}
                          >
                            {modes.research === "live" ? "Start private research" : "Explore research"} <ArrowRight size={14} />
                          </button>
                        </div>
                        {scenario?.steps.length > 1 && (
                          <div className="scenario-progress">
                            <div className="step-switch" aria-label="Scenario steps">
                              {scenario.steps.map((s, i) => (
                                <button key={s.case_id} aria-pressed={stepIndex === i} onClick={() => showHero(hero, i)}>
                                  {s.label}
                                </button>
                              ))}
                            </div>
                            <div className="scenario-pagination">
                              <span role="status">Step {stepIndex + 1} of {scenario.steps.length}</span>
                              <button disabled={stepIndex === 0} onClick={() => showHero(hero, stepIndex - 1)}><ArrowLeft size={14} /> Previous step</button>
                              <button disabled={stepIndex >= scenario.steps.length - 1} onClick={() => showHero(hero, stepIndex + 1)}>Next step <ArrowRight size={14} /></button>
                            </div>
                          </div>
                        )}
                        {scenario?.id === "change" && (
                          <>
                            <Comparison
                              previous={scenario.steps[0].result}
                              current={scenario.steps[1].result}
                            />
                            <p className="small-note">
                              Controlled local original-byte transition; no live
                              URL refresh. The original execution remains
                              unchanged.
                            </p>
                          </>
                        )}
                      </>
                    )}
                    {result && (
                      <>
                        <div className="query-card">
                          <div className="query-label">
                            <Search size={16} />
                            <span>RESEARCH QUESTION</span>
                            <Badge>
                              {hero || live?.demo
                                ? "Preserved capture"
                                : result.execution
                                  ? "Saved execution"
                                  : "Unsaved result"}
                            </Badge>
                          </div>
                          <p>{result.request.question}</p>
                          <div className="query-meta">
                            <span>
                              {[
                                ...new Set(
                                  (result.manifest || []).map(
                                    (p) => p.company_id,
                                  ),
                                ),
                              ].join(" + ")}
                            </span>
                            <span>
                              {result.manifest?.length || 0} pinned sources
                            </span>
                            <span>
                              {tidy(
                                result.request.revision_policy ||
                                  result.request.period_policy ||
                                  "period-bound evidence",
                              )}
                            </span>
                          </div>
                        </div>
                        {!hero &&
                          live?.source_changes &&
                          (live.source_changes.potentially_stale ||
                            live.source_changes.changes.length > 0) && (
                            <div className="source-change-banner">
                              <TriangleAlert size={18} />
                              <div>
                                <strong>
                                  {live.source_changes.potentially_stale
                                    ? "Sources changed since this execution"
                                    : "A source refresh failed"}
                                </strong>
                                {live.source_changes.changes.map((c) => (
                                  <p key={c.source_id}>
                                    {short(c.source_id)}:{" "}
                                    {c.reasons.map(tidy).join(", ")}
                                    {c.refresh_error
                                      ? " · Refresh failed; last-good data retained"
                                      : ""}
                                  </p>
                                ))}
                              </div>
                            </div>
                          )}
                        {!hero && result.execution && (
                          <div className="result-actions">
                            <button disabled={busy || live?.demo || modes.research !== "live"} onClick={rerun}>
                              <History size={15} />
                              Run again using current sources
                            </button>
                            {result.execution.parent_run_id && (
                              <button
                                disabled={busy}
                                onClick={() =>
                                  reopen(result.execution.parent_run_id)
                                }
                              >
                                Open parent execution <ArrowUpRight size={14} />
                              </button>
                            )}
                            <span className="small-note">
                              {live?.demo ? "Preserved history · new reruns require private live access." : "Creates a separate saved execution."}
                            </span>
                          </div>
                        )}
                        {comparison && (
                          <>
                            <Comparison
                              previous={comparison.previous}
                              current={comparison.current}
                            />
                            <div className="history-banner">
                              <Fingerprint size={17} />
                              <p>
                                {comparison.diff.answer_changed
                                  ? "Answer changed"
                                  : "Answer unchanged"}{" "}
                                ·{" "}
                                {comparison.diff.evidence_changed
                                  ? "Evidence changed"
                                  : "Evidence unchanged"}{" "}
                                · Backend comparison
                              </p>
                            </div>
                          </>
                        )}
                        <ResultView
                          r={result}
                          step={{
                            case_id: hero || (live?.demo ? "Preserved archive" : "Live FastAPI"),
                            artifact: hero || live?.demo
                              ? "Hash-bound preserved development capture"
                              : "Owner-scoped FastAPI response",
                          }}
                          data={hero || live?.demo ? archive : null}
                          selected={activeId}
                          selectEvidence={openEvidence}
                          calcMode={hero === "calculation"}
                        />
                        {result.contract_version === "evidence-search-v1" &&
                          !result.claims?.length && (
                            <section className="candidate-list">
                              <h2>Original passage candidates</h2>
                              <p className="small-note">
                                Search matches are evidence candidates, not
                                generated claims.
                              </p>
                              {ids.map((id, i) => {
                                const c = result.citations[id];
                                return (
                                  <button
                                    key={id}
                                    onClick={() => openEvidence(id)}
                                  >
                                    <span>
                                      [{i + 1}] {c.source.company_id} · p.{" "}
                                      {c.page_number}
                                    </span>
                                    <blockquote>{c.text}</blockquote>
                                  </button>
                                );
                              })}
                            </section>
                          )}
                      </>
                    )}
                    {hero && !result && archiveStatus === "loading" && (
                      <p role="status">Opening saved evidence…</p>
                    )}
                    {!result && composer && (
                      <div className="research-intro">
                        <span className="eyebrow">
                          CHOOSE A SAVED STORY
                        </span>
                        <div className="starter-stories">
                          {archive?.scenarios.map((s) => (
                            <button key={s.id} onClick={() => showHero(s.id)}>
                              <strong>{s.title}</strong><span>{s.subtitle}</span><ArrowRight size={16} />
                            </button>
                          ))}
                        </div>
                        <button className="text-button" onClick={() => showHero("calculation")}>
                          Inspect a Decimal calculation <ArrowRight size={16} />
                        </button>
                      </div>
                    )}
                  </>
                )}
                {view === "library" && (
                  <>
                    <div className="page-heading">
                      <div>
                        <span className="eyebrow">YOUR EVIDENCE BASE</span>
                        <h1>Source Library</h1>
                        <p>Official originals, with a version history.</p>
                      </div>
                      <Badge>{sources.length} {modes.library === "demo" ? "preserved" : "live"} sources</Badge>
                    </div>
                    <div className="library-summary">
                      <FileText size={28} />
                      <div>
                        <strong>
                          Review and ingestion stay in private administration.
                        </strong>
                        <p>
                          Inspect versions and reviewed cards here; choose
                          sources for research without modifying the originals.
                        </p>
                      </div>
                    </div>
                    <label className="search-input">
                      <Search size={16} />
                      <input
                        aria-label="Search source library"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Search issuer, report, period…"
                      />
                    </label>
                    <div className="source-list">
                      {liveSources.map((s) => (
                        <article className="source-card" key={s.source_id}>
                          <div className="file-icon">
                            <FileText size={23} />
                          </div>
                          <div className="source-info">
                            <span className="eyebrow">
                              {s.metadata.company_id || "Unknown issuer"}
                            </span>
                            <h3>{s.title}</h3>
                            <p>
                              {s.metadata.period_label || "Unknown period"} ·{" "}
                              {s.metadata.document_type} ·{" "}
                              {s.metadata.publication_date ||
                                "Publication unknown"}
                            </p>
                            <div>
                              <Badge
                                tone={
                                  s.status === "ready" ? "positive" : "caution"
                                }
                              >
                                {tidy(s.status)}
                              </Badge>
                              <Badge>
                                {tidy(s.metadata.review_status)} metadata
                              </Badge>
                              {s.last_error && (
                                <Badge tone="caution">Refresh failed</Badge>
                              )}
                            </div>
                          </div>
                          <button
                            className="text-button"
                            onClick={() => {
                              setLibrarySource(s);
                              openInspector();
                            }}
                          >
                            Inspect <ArrowUpRight size={15} />
                          </button>
                        </article>
                      ))}
                    </div>
                    {!liveSources.length && (
                      <Empty action={query ? () => setQuery("") : reconnect} label={query ? "Clear source search" : "Reload sources"}>
                        {query ? "No sources match this search." : "No sources are available yet."}
                      </Empty>
                    )}
                  </>
                )}
                {view === "history" && (
                  <>
                    <div className="page-heading">
                      <div>
                        <span className="eyebrow">THE RESEARCH RECORD</span>
                        <h1>Saved History</h1>
                        <p>Reopen the answer as it was. Every time.</p>
                      </div>
                      <History size={27} />
                    </div>
                    <div className="history-banner">
                      <Fingerprint size={20} />
                      <div>
                        <strong>Immutable answers, separate reruns.</strong>
                        <p>
                          {modes.history === "demo" ? "Preserved demonstration history." : "Private live owner history."} Original identities, version pins,
                          and parent executions stay intact.
                        </p>
                      </div>
                    </div>
                    <label className="search-input">
                      <Search size={16} />
                      <input
                        maxLength={4000}
                        aria-label="Search saved history"
                        value={historyQuery}
                        onChange={(e) => {
                          setHistoryQuery(e.target.value);
                          setOffset(0);
                        }}
                        placeholder="Search saved research questions…"
                      />
                    </label>
                    {historyError ? (
                      <div className="error-banner" role="alert"><TriangleAlert size={18} /><div><strong>History could not load</strong><p>{historyError}</p></div><button onClick={() => setHistoryRetry((n) => n + 1)}>Retry history</button></div>
                    ) : historyLoading ? (
                      <p role="status">Loading saved executions…</p>
                    ) : (
                      <div className="history-list">
                        {rows.map((row) => (
                          <button
                            className="history-card"
                            disabled={busy}
                            key={row.run_id}
                            onClick={() => reopen(row.run_id)}
                          >
                            <div className="history-date">
                              <History size={16} />
                              <span>
                                {new Date(row.created_at).toLocaleDateString()}
                              </span>
                            </div>
                            <div className="history-info">
                              <h3>{row.question}</h3>
                              <div>
                                <Badge
                                  tone={
                                    row.outcome === "answer"
                                      ? "positive"
                                      : "caution"
                                  }
                                >
                                  {tidy(row.outcome)}
                                </Badge>
                                {row.parent_run_id && (
                                  <Badge>Parent-linked rerun</Badge>
                                )}
                                <code>{short(row.run_id)}</code>
                              </div>
                            </div>
                            <ArrowUpRight size={18} />
                          </button>
                        ))}
                        {!rows.length && (
                          <Empty action={historyQuery ? () => { setHistoryQuery(""); setOffset(0); } : () => navigate("heroes")} label={historyQuery ? "Clear history search" : "Explore saved stories"}>
                            {historyQuery ? "No saved questions match this search." : "No saved executions on this page."}
                          </Empty>
                        )}
                      </div>
                    )}
                    <div className="pagination">
                      <span>
                        Page {offset / 100 + 1} · Up to 100 saved executions per
                        page
                      </span>
                      <button
                        disabled={!offset || historyLoading}
                        onClick={() => setOffset((o) => Math.max(0, o - 100))}
                      >
                        <ArrowLeft size={14} />
                        Previous
                      </button>
                      <button
                        disabled={rows.length < 100 || historyLoading || Boolean(historyError)}
                        onClick={() => setOffset((o) => o + 100)}
                      >
                        Next <ArrowRight size={14} />
                      </button>
                    </div>
                  </>
                )}
                {view === "heroes" && (
                  <>
                    <div className="page-heading">
                      <div>
                        <span className="eyebrow">FINRAG IN PRACTICE</span>
                        <h1>Five research stories</h1>
                        <p>
                          From an exact fact to a traceable research record.
                        </p>
                      </div>
                      <FlaskConical size={29} />
                    </div>
                    {archiveStatus === "loading" && <p role="status">Loading saved stories…</p>}
                    <div className="hero-grid">
                      {archive?.scenarios.map((s, i) => (
                        <button
                          className="hero-card"
                          key={s.id}
                          onClick={() => showHero(s.id)}
                        >
                          <span className="hero-number">0{i + 1}</span>
                          <div>
                            <h2>{s.title}</h2>
                            <p>{s.subtitle}</p>
                            <span className="hero-meta">
                              {s.steps.length} preserved {s.steps.length === 1 ? "step" : "steps"} · Original
                              evidence
                            </span>
                          </div>
                          <ArrowUpRight size={20} />
                        </button>
                      ))}
                    </div>
                    <button
                      className="text-button"
                      onClick={() => showHero("calculation")}
                    >
                      AMD · Exact revenue-growth receipt{" "}
                      <ArrowRight size={15} />
                    </button>
                    <p className="small-note">
                      Preserved development executions. No fresh model calls or
                      additional accuracy cases.
                    </p>
                  </>
                )}
                <footer className="page-footer">
                  <span>
                    <ShieldCheck size={13} />
                    Backend authority · Original evidence
                  </span>
                  <span>
                    {hero || live?.demo ? "Preserved walkthrough" : `${modes[view] || "demo"} capability`}
                  </span>
                </footer>
              </main>
            </Panel>
            <Separator
              aria-label="Resize Evidence Inspector"
              className="resize-handle"
            >
              <GripVertical size={12} />
            </Separator>
            <Panel
              id="evidence"
              defaultSize="34%"
              minSize="25%"
              maxSize="55%"
              className="evidence-panel"
            >
              {inspector}
            </Panel>
          </Group>
          <button
            className="mobile-evidence-button"
            disabled={!result && !(view === "library" && librarySource)}
            aria-expanded={mobileEvidence}
            aria-controls="evidence"
            onClick={() => mobileEvidence ? closeInspector() : openInspector()}
          >
            <BookOpen size={16} />
            {mobileEvidence ? "Return to results" : "Inspect evidence"}
          </button>
        </section>
      </div>
    </div>
  );
}

function Empty({ children, action, label }) {
  return (
    <div className="empty-state">
      <Search size={25} />
      <h3>{children}</h3>
      <p>Try a different search or explore a preserved research story.</p>
      <button className="text-button" onClick={action}>{label} <ArrowRight size={14} /></button>
    </div>
  );
}
function Comparison({ previous, current }) {
  return (
    <div className="saved-comparison">
      {[
        ["Original execution", previous],
        ["Separate rerun", current],
      ].map(([label, r]) => (
        <div key={label}>
          <span>{label}</span>
          {supportedFacts(r).map((o) => (
            <strong key={o.observation_id}>
              {o.company_id} · {o.period.fiscal_label}: {exact(o.value)}{" "}
              <small>
                {o.currency || o.unit} × {o.scale}
              </small>
            </strong>
          ))}
          {!supportedFacts(r).length && <p>{r.answer}</p>}
          <code>{r.run_id}</code>
          <span>
            {r.execution?.parent_run_id
              ? `Parent ${short(r.execution.parent_run_id)}`
              : "Original history retained"}
          </span>
        </div>
      ))}
    </div>
  );
}

function ResearchComposer({
  sources,
  collections,
  pins,
  setPins,
  collectionId,
  setCollectionId,
  busy,
  onSubmit,
}) {
  const [question, setQuestion] = useState(""),
    [mode, setMode] = useState("numeric"),
    [save, setSave] = useState(true),
    [synthesize, setSynthesize] = useState(false),
    [policy, setPolicy] = useState("exact_duration"),
    [filter, setFilter] = useState(""),
    [error, setError] = useState("");
  const [builder, setBuilder] = useState({
    action: "rank",
    basis: "GAAP",
    scope: "consolidated",
    metric: "net income attributable to common",
    companies: "TSLA and WFC",
    period: "Q2 2025",
    end: "Q2 2024",
  });
  async function submit(e) {
    e.preventDefault();
    setError("");
    const selected = Object.entries(pins).map(([source_id, version_id]) => ({
      source_id,
      ...(version_id ? { version_id } : {}),
    }));
    if (!collectionId && !selected.length) {
      setError("Choose a collection or at least one report.");
      return;
    }
    if (selected.length > 18) {
      setError("Narrow the selection to 18 reports.");
      return;
    }
    if (mode === "numeric")
      return onSubmit({
        mode,
        question,
        selections: collectionId ? [] : selected,
        collection_id: collectionId || null,
        save,
        period_policy: policy,
      });
    if (question.length > 1000) {
      setError("Keep passage search queries within 1,000 characters.");
      return;
    }
    const sourceIds = collectionId
      ? collections.find((c) => c.collection_id === collectionId).source_ids
      : selected.map((s) => s.source_id);
    const chosen = sourceIds.map((id) =>
      sources.find((s) => s.source_id === id),
    );
    if (chosen.some((s) => !s?.metadata.company_id)) {
      setError(
        "Evidence search needs identified issuers. Choose confirmed reports.",
      );
      return;
    }
    // Period/company tasks describe selected documents; the backend owns matching and coverage.
    const tasks = [
      ...new Map(
        chosen.map((s) => [
          `${s.metadata.company_id}:${s.metadata.period_label}`,
          s,
        ]),
      ).values(),
    ].map((s, i) => ({
      task_id: `period-${i + 1}`,
      company_id: s.metadata.company_id,
      document_period_label: s.metadata.period_label,
      query: question,
    }));
    if (
      tasks.length > 6 ||
      new Set(tasks.map((t) => t.company_id)).size > 3 ||
      new Set(tasks.map((t) => t.document_period_label)).size > 3
    ) {
      setError(
        "Narrow evidence search to six issuer/period tasks, three issuers and three periods.",
      );
      return;
    }
    if (selected.some((s) => s.version_id)) {
      setError(
        "For period-aware search, select current reports; pinned versions remain available for numeric research and saved reopens.",
      );
      return;
    }
    onSubmit({
      mode,
      question,
      selections: sourceIds.map((source_id) => ({ source_id })),
      tasks,
      synthesize,
    });
  }
  return (
    <form className="composer" onSubmit={submit}>
      <div className="composer-heading">
        <strong>Start from a question and sources</strong>
        <select
          aria-label="Research mode"
          value={mode}
          onChange={(e) => setMode(e.target.value)}
        >
          <option value="numeric">Reviewed financial facts</option>
          <option value="evidence">Original passage research</option>
        </select>
      </div>
      <label className="question-label" htmlFor="research-question">
        Research question
      </label>
      <textarea
        id="research-question"
        required
        minLength={1}
        maxLength={4000}
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Rank GAAP consolidated net income attributable to common for TSLA and WFC in Q2 2025"
      />
      {mode === "numeric" && (
        <details className="question-builder">
          <summary>Build a supported financial question</summary>
          <p className="small-note">
            Select the dimensions explicitly. The backend resolves exact fiscal
            dates, reviewed values and comparability.
          </p>
          <div className="builder-grid">
            {[
              [
                "action",
                "Operation",
                [
                  "show",
                  "compare",
                  "rank",
                  "growth",
                  "change",
                  "margin",
                  "delivery ratio",
                  "production gap",
                ],
              ],
              [
                "metric",
                "Metric",
                [
                  "revenue",
                  "net income",
                  "gross profit",
                  "operating income",
                  "gross margin",
                  "net income attributable to parent",
                  "net income attributable to common",
                  "vehicle production",
                  "vehicle deliveries",
                  "net interest income",
                  "provision for credit losses",
                ],
              ],
              ["basis", "Basis", ["GAAP", "non-GAAP", "operating"]],
              [
                "scope",
                "Scope",
                ["consolidated", "continuing_operations", "automotive"],
              ],
            ].map(([key, label, options]) => (
              <label key={key}>
                {label}
                <select
                  aria-label={`Question ${label.toLowerCase()}`}
                  value={builder[key]}
                  onChange={(e) =>
                    setBuilder((b) => ({ ...b, [key]: e.target.value }))
                  }
                >
                  {options.map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </label>
            ))}
            <label>
              Issuer IDs
              <input
                aria-label="Question issuers"
                value={builder.companies}
                placeholder="TSLA and WFC"
                onChange={(e) =>
                  setBuilder((b) => ({ ...b, companies: e.target.value }))
                }
              />
            </label>
            <label>
              Reporting period
              <input
                aria-label="Question reporting period"
                value={builder.period}
                placeholder="Q2 2025 or FY2024"
                onChange={(e) =>
                  setBuilder((b) => ({ ...b, period: e.target.value }))
                }
              />
            </label>
            {["growth", "change"].includes(builder.action) && (
              <label>
                End period
                <input
                  aria-label="Question end period"
                  value={builder.end}
                  onChange={(e) =>
                    setBuilder((b) => ({ ...b, end: e.target.value }))
                  }
                />
              </label>
            )}
          </div>
          <button
            type="button"
            className="text-button"
            onClick={() =>
              setQuestion(
                `${builder.action} ${builder.basis} ${builder.scope} ${builder.metric} for ${builder.companies} in ${builder.period}${["growth", "change"].includes(builder.action) ? ` to ${builder.end}` : ""}`,
              )
            }
          >
            Use this question <ArrowUpRight size={14} />
          </button>
        </details>
      )}
      <div className="composer-options">
        <label>
          Source collection
          <select
            aria-label="Research collection"
            value={collectionId}
            onChange={(e) => {
              setCollectionId(e.target.value);
              setPins({});
            }}
          >
            <option value="">Select individual reports</option>
            {collections.map((c) => (
              <option key={c.collection_id} value={c.collection_id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        {mode === "numeric" ? (
          <label>
            Calculation periods
            <select
              aria-label="Calculation period policy"
              value={policy}
              onChange={(e) => setPolicy(e.target.value)}
            >
              <option value="exact_duration">Exact duration</option>
              <option value="reporting_kind">Same reporting kind</option>
            </select>
          </label>
        ) : (
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={synthesize}
              onChange={(e) => setSynthesize(e.target.checked)}
            />
            Generate a cited draft (one model call)
          </label>
        )}
      </div>
      {!collectionId && (
        <details
          className="source-picker"
          open={Object.keys(pins).length > 0 || undefined}
        >
          <summary>
            Choose reports · {Object.keys(pins).length} selected / 18
          </summary>
          <input
            aria-label="Filter research sources"
            placeholder="Filter reports…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          <div className="source-options">
            {sources
              .filter((s) =>
                `${s.title} ${s.metadata.period_label}`
                  .toLowerCase()
                  .includes(filter.toLowerCase()),
              )
              .map((s) => (
                <label key={s.source_id}>
                  <input
                    type="checkbox"
                    checked={Object.hasOwn(pins, s.source_id)}
                    disabled={
                      !Object.hasOwn(pins, s.source_id) &&
                      Object.keys(pins).length >= 18
                    }
                    onChange={(e) =>
                      setPins((p) => {
                        const next = { ...p };
                        if (e.target.checked) next[s.source_id] = "";
                        else delete next[s.source_id];
                        return next;
                      })
                    }
                  />
                  <span>
                    {s.title}
                    <small>
                      {s.metadata.review_status} metadata · {s.status}
                      {pins[s.source_id] &&
                        ` · Pinned version ${short(pins[s.source_id])}`}
                    </small>
                  </span>
                </label>
              ))}
          </div>
        </details>
      )}
      <div className="composer-footer">
        {mode === "numeric" ? (
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={save}
              onChange={(e) => setSave(e.target.checked)}
            />
            Save immutable execution
          </label>
        ) : (
          <span className="small-note">
            Evidence search is saved. Drafts remain unreviewed.
          </span>
        )}
        <button className="primary-button" type="submit" disabled={busy}>
          {busy ? "Researching…" : "Run research"}
          <ArrowRight size={15} />
        </button>
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}

function SourceInspector({ source, onUse, close }) {
  const [versions, setVersions] = useState([]),
    [versionId, setVersionId] = useState(""),
    [facts, setFacts] = useState([]),
    [reviews, setReviews] = useState([]),
    [error, setError] = useState(""),
    [tab, setTab] = useState("versions");
  useEffect(() => {
    const c = new AbortController();
    api(`sources/${source.source_id}/versions`, undefined, c.signal)
      .then((v) => {
        setVersions(v);
        setVersionId(source.active_version_id || v.at(-1)?.version_id || "");
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => c.abort();
  }, [source]);
  useEffect(() => {
    if (!versionId) return;
    const c = new AbortController();
    setFacts([]);
    setReviews([]);
    setError("");
    Promise.all([
      api(
        `sources/${source.source_id}/observations?version_id=${versionId}`,
        undefined,
        c.signal,
      ),
      api(
        `sources/${source.source_id}/versions/${versionId}/metadata-reviews`,
        undefined,
        c.signal,
      ),
    ])
      .then(([f, r]) => {
        setFacts(f);
        setReviews(r);
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => c.abort();
  }, [source, versionId]);
  const version = versions.find((v) => v.version_id === versionId),
    effectiveMetadata =
      reviews.at(-1)?.metadata || version?.metadata || source.metadata,
    raw = `/api/backend/sources/${source.source_id}/versions/${versionId}/raw`;
  return (
    <aside className="inspector">
      <div className="inspector-heading">
        <span>
          <BookOpen size={17} />
          <strong>Source Inspector</strong>
        </span>
        <button
          className="icon-button mobile-close"
          onClick={close}
          aria-label="Return to library"
        >
          <ArrowLeft size={17} />
        </button>
      </div>
      <div className="inspector-source">
        <span className="ticker">{source.metadata.company_id}</span>
        <h2>{source.title}</h2>
        <p>
          {effectiveMetadata.period_label} · {effectiveMetadata.review_status}{" "}
          version metadata
        </p>
      </div>
      <div className="inspector-tabs">
        {["versions", "facts", "original"].map((t) => (
          <button key={t} aria-pressed={tab === t} onClick={() => setTab(t)}>
            {t === "facts" ? "Reviewed cards" : tidy(t)}
          </button>
        ))}
      </div>
      <div className="inspector-scroll">
        {error && <p role="alert">{error}</p>}
        <label className="version-select">
          Original version
          <select
            aria-label="Source version"
            disabled={!versions.length}
            value={versionId}
            onChange={(e) => setVersionId(e.target.value)}
          >
            {versions.map((v) => (
              <option key={v.version_id} value={v.version_id}>
                Version {v.number}
                {v.version_id === source.active_version_id
                  ? " · active"
                  : ""} · {short(v.sha256)}
              </option>
            ))}
          </select>
        </label>
        {source.demo && <p className="small-note">Captured version identities; complete registry ordinals and review logs are private.</p>}
        {version && (
          <>
            {tab === "versions" && (
              <>
                <dl className="provenance-list">
                  {Object.entries({
                    source_id: source.source_id,
                    version_id: version.version_id,
                    build_id: version.active_build_id,
                    sha256: version.sha256,
                    media_type: version.media_type,
                    size_bytes: version.size_bytes,
                    publication_date: version.metadata.publication_date,
                    supersedes_version_id: version.supersedes_version_id,
                  }).map(([k, v]) => (
                    <div key={k}>
                      <dt>{tidy(k)}</dt>
                      <dd>{v ?? "Unknown"}</dd>
                    </div>
                  ))}
                </dl>
                <details>
                  <summary>
                    {source.demo ? "Registry review logs are private" : `Version metadata review history (${reviews.length})`}
                  </summary>
                  {reviews.map((r) => (
                    <pre key={r.review_id}>{JSON.stringify(r, null, 2)}</pre>
                  ))}
                </details>
              </>
            )}
            {tab === "facts" && (
              <>
                <p className="small-note">
                  {facts.length} immutable reviewed cards {source.demo ? "in saved captures for" : "in"} this version.
                  Original role bindings are retained below.
                </p>
                {facts.map((o) => (
                  <article className="library-fact" key={o.observation_id}>
                    <h3>
                      {tidy(o.metric_id)} · {o.period.fiscal_label}
                    </h3>
                    <strong>
                      {exact(o.value)} {o.currency || o.unit} × {o.scale}
                    </strong>
                    <p>
                      {o.scope} · {o.basis} · {o.period.start} — {o.period.end}
                    </p>
                    <details>
                      <summary>Original bindings and review provenance</summary>
                      <pre>{JSON.stringify(o, null, 2)}</pre>
                    </details>
                  </article>
                ))}
              </>
            )}
            {tab === "original" && (
              source.demo ? <p className="small-note">Full report previews stay private. Open the official source below; archived citations retain exact original excerpts and physical page references.</p> : <OriginalPage url={raw} hash={version.sha256} />
            )}
            <button
              className="primary-button original-link"
              disabled={!version.active_build_id || source.demo}
              onClick={() => onUse(source, versionId)}
            >
              {source.demo ? "New research requires private live access" : "Use this pinned version"} <ArrowRight size={15} />
            </button>
            <a
              className="text-button"
              href={source.demo ? version.official_url : raw}
              target="_blank"
              rel="noreferrer"
            >
              {source.demo ? "Open official source" : "Open original document"} <ArrowUpRight size={14} />
            </a>
          </>
        )}
      </div>
      <div className="inspector-footer">
        <Fingerprint size={13} />
        {short(version?.sha256)}
      </div>
    </aside>
  );
}
