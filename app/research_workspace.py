"""Local trusted-owner workspace over the existing persistent service."""
import json
import streamlit as st

from src.financial.intent import METRICS


def _table(rows):
    if not rows:
        return
    columns = list(rows[0])
    def cell(value):
        return str(value if value is not None else '').replace('|', '\\|').replace('\n', ' ')
    # Small inventories (18 sources / 6 tasks) need no Arrow/pandas rendering dependency.
    lines = [' | '.join(columns), ' | '.join('---' for _ in columns)]
    lines.extend(' | '.join(cell(row.get(column)) for column in columns) for row in rows)
    st.markdown('\n'.join(lines))


def render_research(svc):
    st.subheader('Financial research')
    st.caption('Reviewed facts and original passages. Missing evidence stays visible; saved answers retain their source versions.')
    sources = svc.registry.list(svc.owner)
    labels = {str(s['source_id']): s['title'] for s in sources}
    collections = svc.registry.collections(svc.owner)
    collection = st.selectbox('Collection', [None] + [str(c['collection_id']) for c in collections],
        format_func=lambda key: 'Choose sources' if key is None else next(c['name'] for c in collections if str(c['collection_id']) == key))
    selected = st.multiselect('Sources', list(labels), format_func=lambda key: labels[key], disabled=collection is not None)
    if collection:
        selected = next(c['source_ids'] for c in collections if str(c['collection_id']) == collection)
    with st.expander('Save a collection or watchlist'):
        name = st.text_input('Collection name')
        kind = st.selectbox('Selection type', ['collection', 'watchlist'])
        if st.button('Save selection', disabled=not selected or not name.strip()):
            try:
                svc.registry.create_collection(svc.owner, {'name': name, 'kind': kind, 'source_ids': selected})
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    chosen_sources = [s for s in sources if str(s['source_id']) in selected]
    inventory = [{'Source': s['title'], 'Company': s['metadata'].get('company_id') or 'Unknown',
        'Period': s['metadata'].get('period_label') or 'Unknown', 'Metadata review': s['metadata'].get('review_status'),
        'Availability': s['status'], 'Refresh error': s['last_error'] or ''} for s in chosen_sources]
    if inventory:
        _table(inventory)
    companies = sorted({s['metadata']['company_id'] for s in chosen_sources if s['metadata'].get('company_id')
                        and s['metadata'].get('review_status') == 'confirmed'})
    action = st.selectbox('Research', ['show', 'compare', 'rank', 'growth', 'change', 'original passages'])
    requested = st.multiselect('Companies', companies, default=companies[:1])
    if action == 'original passages':
        terms = st.text_input('Evidence to find', placeholder='risk factors, Instinct ramp, market outlook…')
        period = st.text_input('Document period (optional)', help='Filters the report label; passage reporting time still requires review.')
    else:
        metric = st.selectbox('Metric', list(METRICS))
        basis = st.selectbox('Accounting basis', ['GAAP', 'non-GAAP'])
        scope = st.selectbox('Scope', ['consolidated', 'automotive'])
        period = st.text_input('Reporting period', placeholder='Q1 2026 or Q4 2024 to Q4 2025')
    if st.button('Run and save research', disabled=not selected or not requested, type='primary'):
        try:
            selections = [{'source_id': key} for key in selected]
            if action == 'original passages':
                body = {'question': terms, 'selections': selections, 'tasks': [
                    {'task_id': f'evidence-{i}', 'company_id': company, 'query': terms,
                     'document_period_label': period or None} for i, company in enumerate(requested)]}
                result = svc.research_evidence(body, save=True, collection_id=collection)
            else:
                question = f'{action} {basis} {scope} {metric} for {" and ".join(requested)} in {period}'
                result = svc.research_question(question, None if collection else selections, collection, save=True)
            st.session_state.research_result = result
        except (ValueError, LookupError) as exc:
            st.error(str(exc))
    with st.expander('Import a reviewed observation'):
        st.caption('Only import a personally reviewed fact card with resolved dates and original evidence links. Import never certifies model-written bindings.')
        upload = st.file_uploader('Reviewed fact card', type=['json'], key='reviewed_fact')
        reviewed = st.checkbox('I reviewed the metric, dates, scope, basis and original row/column association.')
        if st.button('Store reviewed fact', disabled=upload is None or not reviewed):
            try:
                saved = svc.registry.save_observation(svc.owner, json.loads(upload.getvalue()))
                st.success(f'Stored {saved["original_label"]}; prior observations are retained.')
            except (ValueError, LookupError) as exc:
                st.error(str(exc))
    history = svc.registry.research_runs(svc.owner)
    if history:
        saved = st.selectbox('Saved research', history, format_func=lambda row: f'{row["question"]} · {row["created_at"]:%Y-%m-%d %H:%M}')
        row = svc.registry.research_run(svc.owner, saved['run_id'])
        changes = svc.registry.research_changes(svc.owner, row['payload'])
        if changes['potentially_stale']:
            st.warning('Sources or metadata changed. This saved answer retains its original evidence.')
        elif changes['changes']:
            st.warning('A source refresh failed; the saved answer and last-good sources are retained.')
        if st.button('Open saved answer'):
            st.session_state.research_result = row['payload']
        if st.button('Rerun with current sources'):
            try:
                rerun = svc.rerun_research(saved['run_id'])
                st.session_state.research_result = rerun['result']
                st.session_state.research_diff = rerun['diff']
            except (ValueError, LookupError) as exc:
                st.error(str(exc))
    result = st.session_state.get('research_result')
    if result:
        st.caption(result['outcome'].replace('_', ' '))
        st.text(result['answer'])
        _table([{'Task': c['task_id'], 'Status': c['status'], 'Reason': c['reason']} for c in result['coverage']])
        for receipt in result.get('calculations', []):
            st.write(receipt['displayed_result'])
            with st.expander('Formula and cited operands'):
                st.json(receipt)
        for passage in result.get('passages', []):
            with st.expander(f'{passage["task_id"]} · page {passage["page_number"] or "unknown"}'):
                st.text(passage['text'])
        with st.expander('Original citations and saved trace'):
            st.json(result.get('citations', {}))
            if st.session_state.get('research_diff'):
                st.json(st.session_state.research_diff)
        st.download_button('Export research', json.dumps(result, indent=2), 'research.json', 'application/json')
