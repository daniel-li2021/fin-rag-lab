"use client";
import OriginalPage from "./pdf-page";

import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  CheckCheck,
  Download,
  FileText,
  Fingerprint,
  History,
  Search,
  ShieldCheck,
  Table2,
  TriangleAlert,
} from "lucide-react";

const names = { TSLA: "Tesla", WFC: "Wells Fargo", AMD: "AMD" };
const metricName = (id) =>
  ({
    net_income_common: "Common-stockholder net income",
    revenue: "Reported revenue",
  })[id] || tidy(id);
const tidy = (str) => String(str ?? "").replaceAll("_", " ");
const short = (str) => String(str ?? "").slice(0, 12);
// Only add digit grouping to the preserved decimal string; do not round financial values.
const exact = (value) => {
  const [integer, fraction] = String(value).split(".");
  return (
    integer.replace(/\B(?=(\d{3})+(?!\d))/g, ",") +
    (fraction === undefined ? "" : "." + fraction)
  );
};
const units = (o) =>
  o.scale === "1000000"
    ? `${o.currency || o.unit} millions`
    : `${o.currency || o.unit} × ${o.scale}`;
const supportedFacts = (r) =>
  (r.observations || []).filter((o) =>
    Object.hasOwn(r.citations || {}, o.observation_id),
  );
const citedIds = (r) =>
  r.contract_version === "evidence-search-v1" && r.claims?.length
    ? [...new Set(r.claims.map((c) => c.evidence_id))]
    : [
        ...new Set([
          ...supportedFacts(r).map((o) => o.observation_id),
          ...Object.keys(r.citations || {}).sort(),
        ]),
      ];
const stamp = (r) =>
  r.execution?.timestamp
    ? new Date(r.execution.timestamp).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        timeZone: "UTC",
      })
    : "Preserved capture";

function Badge({ children, tone = "" }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
function Citation({ id, index, onSelect, selected }) {
  return (
    <button
      className={`cite ${selected === id ? "selected" : ""}`}
      title="Inspect original evidence"
      aria-label={`Inspect citation ${index}`}
      onClick={() => onSelect(id)}
    >
      [{index}]
    </button>
  );
}
function exportJSON(result) {
  const blob = new Blob([JSON.stringify(result, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `finrag-${result.run_id}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

export function ResultView({
  r,
  step = {},
  data,
  selected,
  selectEvidence,
  calcMode = false,
}) {
  const facts = supportedFacts(r),
    citationIds = citedIds(r),
    activeId = selected;
  return (
    <>
      {!facts.length && !r.claims?.length && (
        <section className="answer-text" aria-label="Backend answer">
          <pre>{r.answer}</pre>
        </section>
      )}
      <div className="result-heading">
        <div>
          <span className="eyebrow">RESEARCH RESULT</span>
          <h2>
            {calcMode
              ? "Reported revenue"
              : r.claims?.length
                ? "Cited research findings"
                : new Set(facts.map((o) => o.metric_id)).size > 1
                  ? "Financial inputs"
                  : metricName(
                      facts[0]?.metric_id || "Supported financial evidence",
                    )}
          </h2>
        </div>
        <Badge tone={r.outcome === "answer" ? "positive" : "caution"}>
          {r.outcome === "answer" ? (
            <Check size={12} />
          ) : (
            <TriangleAlert size={12} />
          )}{" "}
          {r.outcome === "answer" ? "Supported result" : tidy(r.outcome)}
        </Badge>
      </div>
      {facts.length > 0 && (
        <>
          <div className="metric-cards">
            {facts.map((o, i) => (
              <button
                key={o.observation_id}
                className={`metric-card ${o.observation_id === activeId ? "selected" : ""}`}
                onClick={() => selectEvidence(o.observation_id)}
              >
                <div className="metric-top">
                  <span className={`ticker ticker-${o.company_id}`}>
                    {o.company_id}
                  </span>
                  <span>
                    {o.period.fiscal_label}
                    <ArrowUpRight size={13} />
                  </span>
                </div>
                <div className="metric-value">
                  {exact(o.value)}
                  <span className="inline-cite">
                    [{citationIds.indexOf(o.observation_id) + 1}]
                  </span>
                </div>
                <div className="metric-bottom">
                  <span>{units(o)}</span>
                  <span>
                    {o.basis} · {o.scope}
                  </span>
                </div>
                <small className="metric-definition">
                  {metricName(o.metric_id)}
                </small>
              </button>
            ))}
          </div>
          <div className="data-layout">
            <FinancialTable
              facts={facts}
              result={r}
              selected={activeId}
              select={selectEvidence}
            />
            <Chart facts={facts} selected={activeId} select={selectEvidence} />
          </div>
        </>
      )}
      {(r.claims || []).map((claim, i) => {
        const task = (r.request.tasks || []).find(
          (t) => t.task_id === claim.task_id,
        );
        return (
          <article
            className="narrative-card"
            key={`${claim.task_id}-${claim.evidence_id}`}
          >
            <div className="narrative-period">
              <span className="ticker">{task?.company_id}</span>
              <h3>{task?.document_period_label || tidy(claim.task_id)}</h3>
              <Badge tone="caution">Generated · unreviewed</Badge>
            </div>
            <p>
              {claim.text}{" "}
              <Citation
                id={claim.evidence_id}
                index={citationIds.indexOf(claim.evidence_id) + 1}
                onSelect={selectEvidence}
                selected={activeId}
              />
            </p>
            <button
              className="text-button"
              onClick={() => selectEvidence(claim.evidence_id)}
            >
              Read exact original passage <ArrowRight size={14} />
            </button>
          </article>
        );
      })}
      {r.claims?.length > 0 && (
        <p className="small-note">
          Generated draft · unreviewed. Read each claimed period and exact
          original quote together; source location alone does not certify a
          claim.
        </p>
      )}
      {(r.calculations || []).map((calc, i) => (
        <section className="calculation-card" key={i}>
          <div className="section-title">
            <span>
              <Fingerprint size={16} />
              Calculation receipt
            </span>
            <Badge>Backend Decimal</Badge>
          </div>
          <div className="calculation-value">
            {calc.displayed_result}
            <span>{tidy(calc.operation)}</span>
          </div>
          <code>{calc.formula}</code>
          <div className="operand-list">
            {calc.observation_ids.map((id, index) => (
              <div key={id}>
                <span>{index === 0 ? "Start operand" : "End operand"}</span>
                <strong>{exact(calc.normalized_operands[index])}</strong>
                <Citation
                  id={id}
                  index={citationIds.indexOf(id) + 1}
                  onSelect={selectEvidence}
                  selected={activeId}
                />
              </div>
            ))}
          </div>
          <details>
            <summary>Full precision & policy</summary>
            <div className="mono wrap">{calc.result}</div>
            <p>
              {calc.policy_version} · {calc.period_policy} · {calc.unit}
            </p>
          </details>
          {(calc.limitations || []).map((x, i) => (
            <p className="small-note" key={i}>
              {x}
            </p>
          ))}
        </section>
      ))}
      <Coverage result={r} />
      {r.ranking?.length > 0 && (
        <div className="ranking-note">
          <CheckCheck size={18} />
          <div>
            <strong>Complete, comparable ranking</strong>
            <p>
              {r.ranking
                .map(
                  (taskId) =>
                    names[
                      (r.request.tasks || []).find((t) => t.task_id === taskId)
                        ?.company_id
                    ] || taskId,
                )
                .join(" → ")}{" "}
              · Order returned by the backend.
            </p>
          </div>
        </div>
      )}
      <div className="reproducibility">
        <span>
          <Fingerprint size={14} />
          Result identity <code>{short(r.run_id)}</code>
        </span>
        <span>
          {stamp(r)}
          <span className="divider-dot">·</span>
          {step.case_id}
        </span>
      </div>
      <details className="raw-result">
        <summary>Execution & usage receipt</summary>
        <pre>
          {JSON.stringify({ execution: r.execution, usage: r.usage }, null, 2)}
        </pre>
      </details>
      <details className="raw-result">
        <summary>View full provenance</summary>
        <pre>{r.answer}</pre>
        <p>
          Origin: <code>{step.artifact}</code>
        </p>
        <p>
          Run: <code>{r.run_id}</code>
        </p>
        <button className="text-button" onClick={() => exportJSON(r)}>
          Export exact saved JSON <Download size={14} />
        </button>
      </details>
    </>
  );
}
function FinancialTable({ facts, result, selected, select }) {
  const ids = citedIds(result);
  return (
    <section className="financial-table">
      <div className="section-title">
        <span>
          <Table2 size={16} />
          Reported facts
        </span>
        <span className="small-note">Exact values</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Company / period</th>
              <th className="numeric">Amount</th>
              <th>Original</th>
            </tr>
          </thead>
          <tbody>
            {facts.map((o) => (
              <tr
                key={o.observation_id}
                className={selected === o.observation_id ? "selected" : ""}
              >
                <td>
                  <strong>{names[o.company_id] || o.company_id}</strong>
                  <small>{metricName(o.metric_id)}</small>
                  <small>{o.period.fiscal_label}</small>
                  <small>
                    {o.period.start} — {o.period.end}
                  </small>
                  <small>
                    {o.period.calendar} · {o.scope} · {o.basis}
                  </small>
                </td>
                <td className="numeric">
                  <strong>{exact(o.value)}</strong>
                  <small>{units(o)}</small>
                </td>
                <td>
                  <Citation
                    id={o.observation_id}
                    index={ids.indexOf(o.observation_id) + 1}
                    onSelect={select}
                    selected={selected}
                  />
                  <small>
                    p.{" "}
                    {o.evidence.find((e) => e.role === "value")?.page_number ??
                      "—"}
                  </small>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
function Chart({ facts, selected, select }) {
  // Number conversion is solely pixel geometry. Exact values remain preserved strings.
  if (
    facts.length < 2 ||
    new Set(
      facts.map(
        (o) =>
          `${o.metric_id}:${o.unit}:${o.currency}:${o.scale}:${o.basis}:${o.scope}`,
      ),
    ).size !== 1
  )
    return null;
  const max = Math.max(...facts.map((o) => Math.abs(Number(o.value))));
  if (
    !Number.isFinite(max) ||
    max === 0 ||
    facts.some((o) => Number(o.value) < 0)
  )
    return null;
  return (
    <section className="chart-card">
      <div className="section-title">
        <span>Reported amounts</span>
        <span className="small-note">{units(facts[0])}</span>
      </div>
      <div
        className="chart-grid"
        aria-label="Reported amounts chart; zero baseline"
      >
        {facts.map((o) => (
          <button
            className={`chart-row ${selected === o.observation_id ? "selected" : ""}`}
            key={o.observation_id}
            onClick={() => select(o.observation_id)}
            title={`${o.company_id} ${o.period.fiscal_label}: ${exact(o.value)} ${units(o)}`}
          >
            <span className="chart-label">
              {o.company_id}
              <small>{o.period.fiscal_label}</small>
            </span>
            <div className="bar-track">
              <span
                className={`bar bar-${o.company_id}`}
                style={{ width: `${(Math.abs(Number(o.value)) / max) * 100}%` }}
              />
            </div>
            <strong>{exact(o.value)}</strong>
          </button>
        ))}
      </div>
      <div className="chart-axis">
        <span>0</span>
        <span>{exact(String(max))}</span>
      </div>
      <p className="small-note">
        Select a bar to inspect its original. No inferred trend or growth.
      </p>
    </section>
  );
}
function Coverage({ result }) {
  const coverage = result.coverage || [],
    gaps = result.calculation_gaps || [];
  return (
    <section className="coverage-card">
      <div className="section-title">
        <span>
          <ShieldCheck size={16} />
          Evidence coverage
        </span>
        <span>
          {coverage.filter((c) => c.status === "supported").length} /{" "}
          {coverage.length} tasks supported
        </span>
      </div>
      {coverage.map((c) => {
        const task = (result.request.tasks || []).find(
          (t) => t.task_id === c.task_id,
        );
        return (
          <div className="coverage-row" key={c.task_id}>
            <span
              className={`coverage-icon ${c.status === "supported" ? "positive" : "caution"}`}
            >
              {c.status === "supported" ? (
                <Check size={14} />
              ) : (
                <TriangleAlert size={14} />
              )}
            </span>
            <div>
              <strong>
                {names[task?.company_id] || task?.company_id} ·{" "}
                {task?.period?.fiscal_label ||
                  task?.document_period_label ||
                  c.task_id}
              </strong>
              <p>{c.reason}</p>
            </div>
            <Badge tone={c.status === "supported" ? "positive" : "caution"}>
              {tidy(c.status)}
            </Badge>
          </div>
        );
      })}
      {gaps.map((g, i) => (
        <div className="gap-row" key={i}>
          <TriangleAlert size={15} />
          <span>
            <strong>{tidy(g.operation)} withheld.</strong> {g.reason}
          </span>
        </div>
      ))}
    </section>
  );
}
function Empty({ text }) {
  return (
    <div className="empty-state">
      <Search size={28} />
      <h3>{text}</h3>
      <p>Try another term or clear the filter.</p>
    </div>
  );
}

function EvidenceInspector({
  result: r,
  id,
  data,
  tab,
  setTab,
  onSelect,
  close,
}) {
  const citation = r.citations?.[id],
    ids = citedIds(r),
    index = ids.indexOf(id) + 1;
  if (!citation)
    return (
      <aside className="inspector">
        <div className="inspector-heading">
          <BookOpen size={17} />
          <strong>Evidence Inspector</strong>
        </div>
        <Empty text="No cited original in this result." />
      </aside>
    );
  const observation = (r.observations || []).find(
    (o) => o.observation_id === id,
  );
  const source = citation.source,
    inventory = (r.inventory || []).find(
      (item) => item.source_id === source.source_id,
    ),
    original = data?.originals?.[source.source_hash];
  const originalURL = original
    ? `/api/archive/${source.source_hash}`
    : `/api/backend/sources/${source.source_id}/versions/${source.version_id}/raw`;
  const pageImage =
    data?.pages?.[
      `${source.source_hash}:${citation.evidence?.find((e) => e.role === "value")?.page_number ?? citation.page_number}`
    ];
  const valueEvidence = citation.evidence?.find((e) => e.role === "value");
  const page = valueEvidence?.page_number ?? citation.page_number;
  const claim = (r.claims || []).find((c) => c.evidence_id === id);
  const evidence = citation.evidence || [
    {
      role: "original passage",
      text: citation.text,
      page_number: citation.page_number,
      block_id: citation.block_id,
      char_start: citation.char_start,
      char_end: citation.char_end,
    },
  ];
  return (
    <aside className="inspector" aria-label="Evidence Inspector">
      <div className="inspector-heading">
        <span>
          <BookOpen size={17} />
          <strong>Evidence Inspector</strong>
        </span>
        <button
          className="icon-button mobile-close"
          onClick={close}
          aria-label="Return to research"
        >
          <ArrowLeft size={17} />
        </button>
        <Badge>ORIGINAL</Badge>
      </div>
      <div className="citation-selector">
        <span className="eyebrow">
          {r.contract_version === "evidence-search-v1" && !r.claims?.length
            ? "ORIGINAL CANDIDATES"
            : "CITED EVIDENCE"}
          {r.passages?.length
            ? ` · ${r.passages.length} candidates in saved export`
            : ""}
        </span>
        <div>
          {ids.map((key, i) => (
            <button
              key={key}
              aria-pressed={key === id}
              aria-label={`Select ${r.contract_version === "evidence-search-v1" && !r.claims?.length ? "candidate" : "citation"} ${i + 1}`}
              onClick={() => onSelect(key)}
            >
              [{i + 1}]
            </button>
          ))}
        </div>
      </div>
      <div className="inspector-source">
        <span className={`ticker ticker-${source.company_id}`}>
          {source.company_id}
        </span>
        <h2>{tidy(inventory?.title || "Original report")}</h2>
        <p>
          {tidy(inventory?.metadata?.document_type)} ·{" "}
          {inventory?.metadata?.period_label} · Page {page ?? "—"}
        </p>
        <div>
          <Badge tone={observation ? "positive" : "caution"}>
            {observation ? (
              <ShieldCheck size={12} />
            ) : (
              <TriangleAlert size={12} />
            )}{" "}
            {observation
              ? "Reviewed fact binding"
              : claim
                ? "Generated claim · unreviewed"
                : "Original candidate · not a claim"}
          </Badge>
        </div>
      </div>
      <div className="inspector-tabs" aria-label="Evidence view">
        {[
          ["excerpts", "Excerpts"],
          ["page", "Source page"],
          ["provenance", "Provenance"],
        ].map(([key, label]) => (
          <button
            key={key}
            aria-pressed={tab === key}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="inspector-scroll" key={id + "-" + tab}>
        {tab === "excerpts" && (
          <>
            <div className="original-excerpts">
              <div className="paper-heading">
                <FileText size={14} />
                <span>EXACT ORIGINAL EXCERPTS</span>
                <span>[{index}]</span>
              </div>
              {observation && (
                <div className="bound-value">
                  <span>{observation.original_label}</span>
                  <strong>{exact(observation.value)}</strong>
                  <small>
                    {units(observation)} · {observation.period.fiscal_label}
                  </small>
                </div>
              )}
              {evidence.map((e, i) => (
                <div className={`evidence-excerpt role-${e.role}`} key={i}>
                  <div>
                    <span>{tidy(e.role)}</span>
                    <span>p. {e.page_number ?? "—"}</span>
                  </div>
                  <blockquote>{e.text}</blockquote>
                  <small>
                    {e.row_index !== null && e.row_index !== undefined
                      ? `Row ${e.row_index}, column ${e.column_index} · `
                      : e.char_start !== null && e.char_start !== undefined
                        ? `Characters ${e.char_start}–${e.char_end} · `
                        : ""}
                    {e.block_id}
                  </small>
                </div>
              ))}
            </div>
            <div className="inspector-note">
              <ShieldCheck size={16} />
              <p>
                {observation
                  ? "The value, row label, period, unit, scope and basis have separate original bindings. Review provenance is available in the next tab."
                  : "Inspect the original period and quote. Search candidates and generated drafts do not establish semantic correctness."}
              </p>
            </div>
            {observation?.supersedes_observation_ids?.length > 0 && (
              <section className="lineage">
                <h3>
                  <History size={15} />
                  Reviewed revision lineage
                </h3>
                <p>
                  Supersedes{" "}
                  {observation.supersedes_observation_ids.map(short).join(", ")}
                </p>
                {(observation.revision_evidence || []).map((e, i) => (
                  <blockquote key={i}>{e.text}</blockquote>
                ))}
              </section>
            )}
            {claim && (
              <details>
                <summary>Preserved claim quote</summary>
                <blockquote>{claim.quote}</blockquote>
                <p>
                  Review status:{" "}
                  {tidy(claim.review_status || r.synthesis_review_status)}
                </p>
              </details>
            )}
          </>
        )}
        {tab === "page" && (
          <>
            <p className="small-note">
              Pinned original · Physical page {page ?? "not specified"} ·
              SHA-256 {short(source.source_hash)}
            </p>
            {original ? (
              <div className="inspector-note"><FileText size={18} /><p>Exact saved excerpts are available in the Excerpts tab. The public demo links to the official source; locally retained report pages and full PDFs are not redistributed. Official web pages may use different pagination.</p></div>
            ) : pageImage ? (
              <a
                className="page-preview"
                href={`${originalURL}#page=${page || 1}`}
                target="_blank"
                rel="noreferrer"
              >
                <img
                  src={pageImage}
                  alt={`Original report physical page ${page}`}
                />
              </a>
            ) : (
              <OriginalPage
                url={originalURL}
                hash={source.source_hash}
                initialPage={page || 1}
              />
            )}
            <a
              className="primary-button original-link"
              href={`${originalURL}#page=${page || 1}`}
              target="_blank"
              rel="noreferrer"
            >
              {original ? (original.link_kind === "issuer_directory" ? "Find report at issuer" : "Open official source") : "Open pinned original"} <ArrowUpRight size={15} />
            </a>
            <p className="small-note">
              PDF page numbers use physical pages; printed labels may differ. No
              reconstructed table.
            </p>
          </>
        )}
        {tab === "provenance" && (
          <>
            <div className="provenance-card">
              <Fingerprint size={24} />
              <h3>Pinned, traceable evidence</h3>
              <p>
                These identities belong to the saved result. They do not follow
                the active source pointer.
              </p>
            </div>
            <dl className="provenance-list">
              {Object.entries({
                source_id: source.source_id,
                version_id: source.version_id,
                build_id: source.build_id,
                sha256: source.source_hash,
                publication_date: source.publication_date,
                observation_id: observation?.observation_id,
                review_revision: observation?.review_revision,
                run_id: r.run_id,
                parent_run_id: r.execution?.parent_run_id,
              })
                .filter(([, v]) => v)
                .map(([k, v]) => (
                  <div key={k}>
                    <dt>{tidy(k)}</dt>
                    <dd>{v}</dd>
                  </div>
                ))}
            </dl>
            <details>
              <summary>Complete citation and review binding</summary>
              <pre>{JSON.stringify({ citation, observation }, null, 2)}</pre>
            </details>
            <div className="small-note">
              Review provenance follows the saved binding; no independent
              release review is implied.
            </div>
          </>
        )}
      </div>
      <div className="inspector-footer">
        <span>
          <Fingerprint size={13} />
          {short(source.source_hash)}
        </span>
        <a
          href={`${originalURL}#page=${page || 1}`}
          target="_blank"
          rel="noreferrer"
        >
          Open original <ArrowUpRight size={13} />
        </a>
      </div>
    </aside>
  );
}

export {
  Badge,
  Citation,
  EvidenceInspector,
  exact,
  tidy,
  short,
  citedIds,
  supportedFacts,
  exportJSON,
};
