# Original evidence and citation provenance

New chunks carry `source_version` (the PDF SHA-256; a tagged text hash for synthetic/text documents), original `source_block_ids`, and `evidence_spans`. Each span holds block-local half-open character offsets, exact text, page, heading, bounding box when available, and line ranges when the block has a line origin. This is the local migration contract, not the source registry planned in Issue 04: `document_id` plus content hash identifies the current original; it does not allocate a business source/version UUID.

All three chunkers use one offset-preserving splitter. Offsets travel with the original pieces rather than searching for output strings, so overlaps and repeated text retain their real positions. Children have their own spans/pages instead of inheriting the parent's first page. Empty/generated-heading-only fragments are not indexed. `page_number` remains a compatibility first-page field; `evidence_spans`/`page_numbers` describe multi-page coverage. The splitter uses token budgets and original Unicode character boundaries. Corrected boundaries can differ from the historical splitters; every new experiment arm must use this same revision.

Original table text/rows are retained in `chunk.text` for generation. Captions go in a separate `retrieval_text` alongside originals and are used by **both** vector and BM25 retrieval. Generated descriptions of images without extractable text are explicitly marked and spans use `kind=generated`; these do not count as original textual evidence in benchmark recall. Numerical claims need original evidence or review of the original visual asset. The generator's prompt records document/version and all available pages.

Chroma round-trips the entire chunk payload, including original text and spans; parent/child pickles also retain it. Existing artifacts can load without re-embedding, but missing provenance remains `migration_required` with `legacy_document_id`, null version and no fabricated spans. Rebuild explicitly from verified parsed caches to obtain corrected evidence; historical caption-only artifacts cannot support provenance promotion gates. The existing registry/atomic-publication limitations remain deferred to Issues 04/05.

`citations` contains only source numbers actually referenced by the answer. `retrieved_contexts` contains all retrieved cards. Sparse footnotes retain their original `source_number`; invalid footnote numbers remain in `invalid_citations` for scoring. CLI, API and UI do not turn uncited retrieval into answer citations. API citations expose document ID/name, version, span list and migration status. The Streamlit UI labels answer citations and retrieved context separately. `candidates` retains the fused child top-20 from the same retrieval call for benchmark scoring; no second embedding search is performed.

Run the focused offline checks:

```sh
python -m pytest tests/unit/test_chunkers.py tests/unit/test_generator_query.py tests/unit/test_rag_service.py tests/unit/test_benchmark.py tests/integration/test_api.py tests/integration/test_ingestion.py -q
```
