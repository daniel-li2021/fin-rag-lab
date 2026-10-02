"""
Fin-RAG Lab — Streamlit frontend (local application).

Run from repo root:
    streamlit run app/streamlit_app.py

UI only — all RAG logic lives in RAGService.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env", override=True)

INDEX_DIR = str(ROOT / "index")
CACHE_ROOT = str(ROOT / "cache")
UPLOAD_DIR = ROOT / "data" / "uploads"

SAMPLE_QUESTIONS = [
    ("Wells Fargo net income", "What was Wells Fargo's Q4 2025 net income?"),
    ("Tesla production", "What was Tesla's vehicle production in Q1 2026?"),
    ("AMD data center", "What was AMD's data center revenue?"),
]

_CSS = """
<style>
/* Layout */
.block-container {
  padding-top: 1.25rem !important;
  padding-bottom: 2rem !important;
  max-width: 880px !important;
}
header[data-testid="stHeader"] { background: transparent; }

/* Compact metrics strip */
div[data-testid="stMetric"] {
  background: #f8f9fb;
  border: 1px solid #e8eaee;
  border-radius: 8px;
  padding: 0.55rem 0.75rem;
}
div[data-testid="stMetricValue"] { font-size: 1rem !important; font-weight: 600 !important; }
div[data-testid="stMetricLabel"] { font-size: 0.72rem !important; color: #6b7280 !important; }
div[data-testid="stMetricDelta"] { display: none; }

/* Sample chips — shrink the default Streamlit buttons in that row */
div[data-testid="stHorizontalBlock"]:has(button[kind="secondary"]) button[kind="secondary"] {
  font-size: 0.78rem !important;
  padding: 0.2rem 0.65rem !important;
  min-height: 1.85rem !important;
  border-radius: 999px !important;
  border: 1px solid #d1d5db !important;
  background: #fff !important;
  color: #374151 !important;
  font-weight: 500 !important;
}
div[data-testid="stHorizontalBlock"]:has(button[kind="secondary"]) button[kind="secondary"]:hover {
  border-color: #9ca3af !important;
  background: #f9fafb !important;
}

/* Tighter expanders */
div[data-testid="stExpander"] {
  border: 1px solid #e8eaee;
  border-radius: 8px;
  margin-bottom: 0.45rem;
}
div[data-testid="stExpander"] details summary p {
  font-size: 0.9rem !important;
}

/* Sidebar denser */
section[data-testid="stSidebar"] .block-container { padding-top: 1rem !important; }
</style>
"""


def _snippet(text: str, n: int = 140) -> str:
    t = re.sub(r"\s+", " ", (text or "")).strip()
    if len(t) <= n:
        return t
    return t[: n - 1].rstrip() + "…"


def _cited_indices(answer: str, n_sources: int) -> list[int]:
    """Map model [^n] tags to 1-based source indices (clamped to available sources)."""
    found = [int(x) for x in re.findall(r"\[\^(\d+)\]", answer or "")]
    ordered: list[int] = []
    for n in found:
        if 1 <= n <= max(n_sources, 1) and n not in ordered:
            ordered.append(n)
    if ordered:
        return ordered
    # Fallback: show all citation cards in order
    return list(range(1, n_sources + 1))


def _answer_html(answer: str) -> str:
    """Render answer with clean clickable [1], [2] links to source anchors."""
    shown = html.escape(answer or "").replace("$", "&#36;")

    def _link(m: re.Match) -> str:
        n = m.group(1)
        return (
            f'<a href="#src-{n}" '
            f'style="color:#1d4ed8;text-decoration:none;font-weight:600;'
            f'font-size:0.85em">[{n}]</a>'
        )

    shown = re.sub(r"\[\^(\d+)\]", _link, shown)
    shown = shown.replace("\n", "<br>")
    return (
        f"<div style='font-size:1.12rem;line-height:1.65;color:#111827;"
        f"padding:0.15rem 0 0.35rem'>{shown}</div>"
    )


@st.cache_resource
def get_service(index_dir: str, cache_root: str):
    from src.services import RAGService
    import os
    if os.getenv('DATABASE_URL'):
        from src.services.persistent_service import PersistentRAGService
        svc = PersistentRAGService(os.environ['DATABASE_URL'],owner=os.getenv('FINRAG_OWNER','default'),
                                   index_dir=index_dir,cache_root=cache_root)
    else:
        svc = RAGService(index_dir=index_dir, cache_root=cache_root)
    svc.load_index()
    return svc


def _ensure_session_defaults() -> None:
    defaults = {
        "last_result": None,
        "last_error": None,
        "question": "",
        "pending_question": None,
        "do_ask": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    pending = st.session_state.pop("pending_question", None)
    if pending is not None:
        st.session_state.question = pending


def _set_sample(question: str) -> None:
    st.session_state.pending_question = question
    st.session_state.do_ask = False


def _doc_label(source_path: str) -> str:
    return Path(source_path).name if source_path else "document"


def _render_sidebar(svc) -> None:
    from src.core.config import settings

    if hasattr(svc,'registry'):
        _render_registry_sidebar(svc)
        return

    status = svc.status()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    with st.sidebar:
        st.markdown("**Corpus**")
        if status.ready:
            st.success(
                f"Ready · {status.n_documents} docs · "
                f"{status.n_children:,} chunks"
            )
        else:
            st.warning("No index — ingest PDFs below.")

        if not settings.has_openai_key:
            st.error("OPENAI_API_KEY missing in `.env`")

        if status.documents:
            for doc in status.documents:
                name = _doc_label(doc["source_path"])
                st.caption(
                    f"{name} · {doc['n_pages']} pages · {doc['n_children']} chunks"
                )

        st.divider()
        st.markdown("**Ingest**")
        st.caption("Rebuilds the full index from the selected files.")

        available = [p.name for p in svc.list_available_pdfs()]
        selected = st.multiselect(
            "PDFs in data/uploads/",
            options=available,
            default=available[:3] if available else [],
            label_visibility="collapsed",
        )
        uploaded = st.file_uploader(
            "Upload PDF(s)",
            type=["pdf"],
            accept_multiple_files=True,
        )
        max_pages = st.number_input("Max pages (0 = all)", 0, value=0, step=1)

        if st.button("Rebuild index", type="primary", use_container_width=True):
            paths: list[Path] = [UPLOAD_DIR / n for n in selected]
            if uploaded:
                for uf in uploaded:
                    dest = UPLOAD_DIR / uf.name
                    dest.write_bytes(uf.getvalue())
                    paths.append(dest)
            paths = list(dict.fromkeys(p.resolve() for p in paths))

            if not paths:
                st.error("Select or upload at least one PDF.")
            elif not settings.has_openai_key:
                st.error("Set OPENAI_API_KEY in `.env` first.")
            else:
                with st.spinner(f"Ingesting {len(paths)} PDF(s)…"):
                    try:
                        get_service.clear()
                        from src.services import RAGService

                        fresh = RAGService(
                            index_dir=INDEX_DIR, cache_root=CACHE_ROOT
                        )
                        result = fresh.ingest_and_index(
                            paths,
                            max_pages=max_pages or None,
                            reset=True,
                            verbose=False,
                        )
                        get_service.clear()
                        st.session_state.last_result = None
                        st.session_state.last_error = None
                        cost = "unknown" if result["cost_usd"] is None else f"${result['cost_usd']:.4f}"
                        st.success(
                            f"{result['n_documents']} docs · "
                            f"{result['n_children']} chunks · {cost}"
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Ingest failed: {e}")

        st.divider()
        cost = svc.cost_report()
        st.caption(f"Session cost · ${cost.get('total_usd', 0):.4f}")


def _render_registry_sidebar(svc):
    import json
    with st.sidebar:
        st.markdown('**Sources**')
        sources=svc.registry.list(svc.owner)
        for source in sources:
            st.caption(f"{source['title']} · {source['kind']} · {source['status']}")
        query_scope=st.selectbox('Query scope',['All active sources']+[str(s['source_id']) for s in sources if s['active_build_id']],
            format_func=lambda key: next((s['title'] for s in sources if str(s['source_id'])==key),key))
        st.session_state.source_filters={} if query_scope=='All active sources' else {'source_id':query_scope}
        existing=st.selectbox('Source', ['New source']+[str(s['source_id']) for s in sources],
                              format_func=lambda key: next((s['title'] for s in sources if str(s['source_id'])==key),key))
        selected=next((s for s in sources if str(s['source_id'])==existing),None)
        kind=selected['kind'] if selected else st.selectbox('Format',['pdf','text','markdown','url'])
        title=st.text_input('Title',value=selected['title'] if selected else '')
        url=st.text_input('URL',value=selected['locator'] or '' if selected else '') if kind=='url' else None
        upload=st.file_uploader('Content',type=['pdf','txt','md']) if kind!='url' else None
        metadata=st.text_area('Confirmed metadata (JSON)',value=json.dumps(selected['metadata'] if selected else {},indent=2))
        if st.button('Save source'):
            try:
                if selected:
                    svc.registry.update_metadata(svc.owner,selected['source_id'],json.loads(metadata))
                else:
                    svc.register(kind=kind,title=title,locator=url,metadata=json.loads(metadata))
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if selected and st.button('Fetch snapshot' if kind=='url' else 'Ingest content'):
            try:
                with st.spinner('Processing source…'):
                    if kind=='url':
                        job=svc.snapshot(selected['source_id']);svc.process_job(job['job']['job_id'])
                    elif upload:
                        svc.ingest_bytes(selected['source_id'],upload.getvalue())
                    else:
                        raise ValueError('Select content to upload')
                st.session_state.last_result=None
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if selected and st.button('Archive source'):
            svc.registry.archive(svc.owner,selected['source_id'])
            st.session_state.last_result=None
            st.rerun()


def _render_sources(citations: list[dict], title="Answer citations") -> None:
    st.markdown(f"##### {title}")
    if not citations:
        st.caption("No sources for this answer.")
        return

    for i, c in enumerate(citations, start=1):
        i = c.get("source_number") or i
        doc = c.get("document_name") or "Document"
        page = c.get("page_number")
        body = c.get("text") or c.get("text_preview") or ""
        excerpt = _snippet(body, 130)

        page_bit = f" · p.{page}" if page else ""
        summary = f"[{i}]  {doc}{page_bit}  —  {excerpt}"

        # Anchor target for answer citation links
        anchor = "src" if title == "Answer citations" else "context"
        st.markdown(f'<div id="{anchor}-{i}"></div>', unsafe_allow_html=True)
        with st.expander(summary, expanded=False):
            meta_bits = [doc]
            if page is not None:
                meta_bits.append(f"Page {page}")
            heading = " › ".join(c.get("heading_path") or [])
            if heading:
                meta_bits.append(heading)
            st.caption(" · ".join(meta_bits))
            st.markdown(
                f"<div style='font-size:0.92rem;line-height:1.5;color:#1f2937'>"
                f"{html.escape(_snippet(body, 420)).replace('$', '&#36;')}"
                f"</div>",
                unsafe_allow_html=True,
            )


def _render_hallucination(hall: dict) -> None:
    st.markdown("##### Verification")
    score = hall.get("faithfulness_score", 0) or 0
    st.caption(
        f"Faithfulness {score:.0%} · "
        f"entailed {hall.get('n_entailed', 0)} · "
        f"unsupported {hall.get('n_unsupported', 0)} · "
        f"refuted {hall.get('n_refuted', 0)}"
    )
    for claim in hall.get("claims", []):
        verdict = claim.get("verdict", "")
        color = {
            "entailed": "#15803d",
            "unsupported": "#a16207",
            "refuted": "#b91c1c",
        }.get(verdict, "#374151")
        claim_text = html.escape(claim.get("claim", "") or "").replace("$", "&#36;")
        reason = html.escape(claim.get("reasoning", "") or "").replace("$", "&#36;")
        st.markdown(
            f"<div style='border-left:3px solid {color};padding:0.35rem 0.7rem;"
            f"margin:0.35rem 0;background:#fafafa;border-radius:4px'>"
            f"<span style='color:{color};font-size:0.7rem;font-weight:700;"
            f"letter-spacing:0.04em;text-transform:uppercase'>{html.escape(verdict)}</span>"
            f"<div style='margin-top:0.2rem;font-size:0.92rem'>{claim_text}</div>"
            f"<div style='color:#6b7280;font-size:0.8rem;margin-top:0.15rem'>{reason}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )


def _render_debug(result: dict) -> None:
    with st.expander("Technical details", expanded=False):
        stages = result.get("stages") or []
        st.markdown("**Pipeline**")
        st.code(" → ".join(stages) if stages else "(none)", language=None)

        st.markdown("**Retrieved context** (parent chunks sent to the model)")
        retrieved = result.get("retrieved_context") or []
        if not retrieved:
            # Older session payloads may lack this field — fall back to citations
            retrieved = [
                {
                    "chunk_id": c.get("chunk_id"),
                    "page_number": c.get("page_number"),
                    "text": c.get("text") or c.get("text_preview"),
                    "document_id": c.get("document_id"),
                    "heading_path": c.get("heading_path"),
                }
                for c in (result.get("citations") or [])
            ]

        if not retrieved:
            st.caption("No retrieved chunks.")
        else:
            for i, chunk in enumerate(retrieved, start=1):
                page = chunk.get("page_number")
                cid = chunk.get("chunk_id") or "—"
                heading = " › ".join(chunk.get("heading_path") or [])
                label = f"Chunk {i} · {cid}"
                if page is not None:
                    label += f" · p.{page}"
                if heading:
                    label += f" · {heading[:50]}"
                st.markdown(
                    f"<div style='font-size:0.8rem;font-weight:600;color:#374151;"
                    f"margin-top:0.6rem;margin-bottom:0.2rem'>{html.escape(label)}</div>",
                    unsafe_allow_html=True,
                )
                st.code(chunk.get("text") or "", language=None)

        breakdown = result.get("cost_breakdown") or {}
        if breakdown:
            st.markdown("**Cost by stage**")
            st.json({k: round(v, 6) for k, v in breakdown.items()})


def _render_result(result: dict) -> None:
    answer = result.get("answer", "") or ""
    question = result.get("query", "") or ""
    citations = result.get("citations") or []

    # ---- Answer (hero) ----
    st.markdown("#### Answer")
    if result.get("outcome"):
        st.caption(result["outcome"].replace("_", " "))
    if question:
        st.caption(question)

    if result.get("refused"):
        st.warning(
            re.sub(r"\[\^(\d+)\]", r"[\1]", answer).replace("$", r"\$")
        )
    else:
        st.markdown(_answer_html(answer), unsafe_allow_html=True)

    # ---- Compact metrics ----
    latency_s = (result.get("latency_ms") or 0) / 1000.0
    route = (result.get("query_type") or "—").replace("_", " ")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Latency", f"{latency_s:.1f}s")
    m2.metric("Citations", len(citations))
    cost = result.get("cost_usd")
    m3.metric("Cost estimate", "unknown" if cost is None else f"${cost:.4f}")
    m4.metric("Route", route)

    # ---- User-facing sources (collapsed) ----
    # Prefer cited indices; still show all citation cards for grounding
    _ = _cited_indices(answer, len(citations))
    _render_sources(citations)
    with st.expander("Retrieved context (not answer citations)"):
        _render_sources(result.get("retrieved_contexts") or [], "Retrieved context")

    # ---- Optional verification ----
    hall = result.get("hallucination")
    if hall:
        _render_hallucination(hall)

    # ---- Developer details ----
    _render_debug(result)


def main() -> None:
    st.set_page_config(
        page_title="Fin-RAG Lab",
        page_icon="📄",
        layout="centered",
        initial_sidebar_state="expanded",
    )
    _ensure_session_defaults()
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown("## Fin-RAG Lab")
    st.caption("Ask questions over indexed financial filings.")

    svc = get_service(INDEX_DIR, CACHE_ROOT)
    _render_sidebar(svc)

    if not svc.is_ready():
        st.info(
            "No index loaded. Use the sidebar to ingest PDFs, "
            "or run `python scripts/build_index.py`."
        )
        return

    qcols = st.columns([5, 1], gap="small")
    with qcols[0]:
        question = st.text_input(
            "Question",
            key="question",
            label_visibility="collapsed",
            placeholder="Ask a question about the indexed filings…",
        )
    with qcols[1]:
        ask_clicked = st.button("Ask", type="primary", use_container_width=True)

    # Chip-style samples
    scols = st.columns(len(SAMPLE_QUESTIONS), gap="small")
    for i, (label, full_q) in enumerate(SAMPLE_QUESTIONS):
        scols[i].button(
            label,
            key=f"sample_{i}",
            use_container_width=True,
            on_click=_set_sample,
            args=(full_q,),
            help=full_q,
        )

    verify = st.checkbox(
        "Verify claims (extra cost)",
        value=False,
        help="Optional hallucination check. Not part of normal queries.",
    )

    if ask_clicked or st.session_state.do_ask:
        st.session_state.do_ask = False
        q = (st.session_state.get("question") or question or "").strip()
        if not q:
            st.session_state.last_error = "Enter a question first."
            st.session_state.last_result = None
        else:
            with st.spinner("Generating answer…"):
                try:
                    options={'filters':st.session_state.get('source_filters',{})} if hasattr(svc,'registry') else {}
                    result = svc.query(q, verify_hallucination=verify, **options)
                    st.session_state.last_result = result.to_display_dict()
                    st.session_state.last_error = None
                except Exception as e:
                    st.session_state.last_result = None
                    st.session_state.last_error = str(e)

    if st.session_state.last_error:
        st.error(st.session_state.last_error)

    if st.session_state.last_result:
        st.divider()
        _render_result(st.session_state.last_result)


if __name__ == "__main__":
    main()
