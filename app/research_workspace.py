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
    with st.expander('Save a collection'):
        name = st.text_input('Collection name')
        kind = 'collection'
        st.caption('Saved selections do not monitor or refresh sources.')
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
    actions = {'show': 'Lookup', 'compare': 'Compare', 'rank': 'Rank', 'growth': 'Revenue / value growth',
               'change': 'Value / percentage-point change', 'margin': 'Profit margin',
               'delivery ratio': 'Deliveries / production', 'production gap': 'Production minus deliveries',
               'original passages': 'Evidence search'}
    action = st.selectbox('Research', list(actions), format_func=actions.get)
    st.caption('At most three companies, three periods and six required tasks. Ratios use one company/period.')
    requested = st.multiselect('Companies', companies, default=companies[:1])
    custom_question = st.text_input('Question (optional)', placeholder='What was GAAP consolidated revenue for AMD in Q1 2025?') if action != 'original passages' else ''
    if action == 'original passages':
        terms = st.text_input('Evidence to find', placeholder='risk factors, Instinct ramp, market outlook…')
        period = st.text_input('Document period (optional)', help='Filters the report label; passage reporting time still requires review.')
        synthesize = st.checkbox('Draft a cited narrative', help='One bounded model call. Generated claims remain subject to semantic review.')
    else:
        metric_options = ['vehicle deliveries'] if action in ('delivery ratio', 'production gap') else (
            ['gross profit', 'operating income', 'net income', 'net income attributable to parent'] if action == 'margin' else list(METRICS))
        metric = st.selectbox('Metric', metric_options)
        operating = metric in ('vehicle deliveries', 'vehicle production')
        basis = st.selectbox('Basis', ['operating'] if operating else ['GAAP', 'non-GAAP'])
        scope = st.selectbox('Scope', ['consolidated', 'continuing_operations', 'automotive', 'segment'])
        if scope == 'segment':
            scope = 'segment:' + st.text_input('Reviewed segment definition', placeholder='client_gaming_2025').strip()
        period = st.text_input('Reporting period', placeholder='Q1 2026 or Q4 2024 to Q4 2025')
    relaxed_duration = st.checkbox('Compare reporting kinds when durations differ', value=False,
        help='Explicit trend policy; the receipt discloses unequal durations. Dates and missing operands still require review.') if action in ('growth', 'change') else False
    if st.button('Run and save research', disabled=not selected or not requested, type='primary'):
        try:
            selections = [{'source_id': key} for key in selected]
            if action == 'original passages':
                body = {'question': terms, 'selections': selections, 'synthesize': synthesize, 'tasks': [
                    {'task_id': f'evidence-{i}', 'company_id': company, 'query': terms,
                     'document_period_label': period or None} for i, company in enumerate(requested)]}
                result = svc.research_evidence(body, save=True, collection_id=collection)
            else:
                question = custom_question.strip() or f'{action} {basis} {scope} {metric} for {" and ".join(requested)} in {period}'
                result = svc.research_question(question, None if collection else selections, collection, save=True,
                    period_policy='reporting_kind' if relaxed_duration else 'exact_duration')
            st.session_state.research_result = result
            st.session_state.pop('research_diff', None)
        except (ValueError, LookupError) as exc:
            st.error(str(exc))
    render_history(svc)
    render_result()


def render_history(svc):
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
            st.session_state.pop('research_diff', None)
        if st.button('Rerun with current sources'):
            try:
                rerun = svc.rerun_research(saved['run_id'])
                st.session_state.research_result = rerun['result']
                st.session_state.research_diff = rerun['diff']
            except (ValueError, LookupError) as exc:
                st.error(str(exc))


def render_result():
    result = st.session_state.get('research_result')
    if result:
        st.caption(result['outcome'].replace('_', ' '))
        st.text(result['answer'])
        tasks = {t['task_id']: t for t in result['request'].get('tasks', [])}
        _table([{'Company': tasks.get(c['task_id'], {}).get('company_id', ''),
                 'Period': tasks.get(c['task_id'], {}).get('period', {}).get('fiscal_label', ''),
                 'Metric': tasks.get(c['task_id'], {}).get('metric_id', c['task_id']).replace('_', ' '),
                 'Status': c['status'].replace('_', ' '), 'Reason': c['reason']} for c in result['coverage']])
        for receipt in result.get('calculations', []):
            st.write(receipt['displayed_result'])
            with st.expander('Formula and cited operands'):
                st.write(receipt['formula'])
                st.write('Operands: ' + ' → '.join(receipt['normalized_operands']) + ' · ' + receipt['unit'])
                for limitation in receipt['limitations']:
                    st.caption(limitation)
        for passage in result.get('passages', []):
            with st.expander(f'{passage["task_id"]} · page {passage["page_number"] or "unknown"}'):
                st.text(passage['text'])
        for claim in result.get('claims', []):
            with st.expander(f'Claim support · {claim["task_id"]} · original page {claim["page_number"]}'):
                st.text(claim['quote'])
                st.caption('Semantic review: ' + claim['review_status'].replace('_', ' '))
        titles = {s['source_id']: s['title'] for s in result.get('inventory', [])}
        for key, citation in result.get('citations', {}).items():
            source = citation['source']
            with st.expander(f'{key} · {titles.get(source["source_id"], source["company_id"])}'):
                st.caption('Published: ' + str(source.get('publication_date') or 'Unknown'))
                for evidence in citation.get('evidence', []):
                    st.caption(f'{evidence["role"].replace("_", " ")} · original page {evidence.get("page_number") or "unknown"}')
                    st.text(evidence['text'])
        diff = st.session_state.get('research_diff')
        if diff:
            if diff.get('refresh_failed'):
                st.warning('Refresh failed; this rerun retains last-good evidence.')
            st.write('Evidence changed' if diff.get('evidence_changed') else 'Evidence unchanged')
            st.write('Result changed' if diff['answer_changed'] else 'Result unchanged')
            st.caption(f'{diff["previous_outcome"]} → {diff["current_outcome"]}')
        with st.expander('Diagnostics and saved trace'):
            st.json(result.get('citations', {}))
            if st.session_state.get('research_diff'):
                st.json(st.session_state.research_diff)
        st.download_button('Export research', json.dumps(result, indent=2), 'research.json', 'application/json')


def render_library(svc):
    st.subheader('Source Library')
    st.caption('Source metadata review and financial fact review are separate. Indexed page counts do not certify full report coverage.')
    rows = svc.registry.library(svc.owner)
    _table([{'Report': s['title'], 'Company': s['metadata'].get('company_id') or 'Unknown',
        'Period': s['metadata'].get('period_label') or 'Unknown',
        'Published': s['metadata'].get('publication_date') or 'Unknown',
        'Metadata': s['metadata']['review_status'], 'Readiness': s['build_status'] or s['status'],
        'Indexed PDF pages': s['indexed_pages'], 'Children': s['children'], 'Reviewed cards': s['fact_cards'],
        'Refresh': s['last_error'] or 'No recorded failure'} for s in rows])
    for source in rows:
        with st.expander(source['title'] + ' · indexed coverage'):
            manifest = source['manifest'] or {}
            st.write('Selected page window: ' + str(manifest.get('page_range') or 'No explicit window'))
            st.write('Build page cap: ' + str(manifest.get('max_pages') or 'Unknown'))
            st.caption('A capped parse is not proof of full coverage. Review the selected financial, MD&A and footnote pages.')


def render_administration(svc):
    st.caption('Trusted owner administration. This local app is not a public access-control boundary.')
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
