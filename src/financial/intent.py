"""Small explicit question templates; ambiguous dimensions never become defaults."""
import re

from src.financial.models import FinancialPeriod


METRICS = {'revenue': 'revenue', 'net income': 'net_income', 'gross profit': 'gross_profit',
           'operating income': 'operating_income', 'gross margin': 'gross_margin',
           'vehicle production': 'vehicle_production', 'vehicle deliveries': 'vehicle_deliveries',
           'net income attributable to parent': 'net_income_parent', 'net interest income': 'net_interest_income',
           'net income attributable to common': 'net_income_common',
           'provision for credit losses': 'provision_credit_losses'}
PERIOD = r'(?:Q[1-4]\s+(?:19|20|21)\d{2}|FY\s*(?:19|20|21)\d{2})'


def parse_question(question, inventory):
    """Return a validated-plan candidate or a fact-free safe outcome; no model call."""
    def stop(outcome, answer):
        return {'outcome': outcome, 'answer': answer, 'coverage': [], 'citations': {},
                'usage': {'planner_calls': 0, 'generator_calls': 0, 'embedding_calls': 0, 'cost_usd': '0'}}
    text = question.strip().rstrip('?').strip()
    text = re.sub(r'^(?:what (?:was|is|were)|lookup)\s+', 'show ', text, flags=re.I)
    trend = re.fullmatch(r'How did (.+?) for (.+?) change from (.+)', text, re.I)
    if trend:
        text = f'change {trend[1]} for {trend[2]} in {trend[3]}'
    text = re.sub(r'\bnet revenue\b', 'revenue', text, flags=re.I)
    metrics = '|'.join(re.escape(m) for m in METRICS)
    # ponytail: finite templates, explicit tasks for questions outside this grammar; planner stays gated.
    pattern = (rf'(?P<action>show|compare|rank|growth|change|margin|delivery ratio|production gap)\s+(?P<basis>GAAP|non-GAAP|operating)\s+'
               rf'(?P<scope>consolidated|continuing_operations|automotive|segment:[a-z0-9_-]+)\s+(?P<metric>{metrics})\s+for\s+'
               rf'(?P<companies>.+?)\s+in\s+(?P<periods>{PERIOD}(?:\s+to\s+{PERIOD})?)')
    match = re.fullmatch(pattern, text, re.I)
    if not match:
        return stop('clarify', 'Specify company, metric, reporting period, scope and GAAP/non-GAAP basis. '
                    'For example: "compare GAAP consolidated revenue for Tesla and AMD in Q1 2026". '
                    'Use explicit research tasks for other questions.')
    aliases = {}
    for source in inventory:
        metadata = source['metadata']
        if metadata.get('review_status') != 'confirmed' or not metadata.get('company_id'):
            continue
        for alias in (metadata['company_id'], metadata.get('company_name')):
            if alias:
                aliases.setdefault(alias.casefold(), set()).add(metadata['company_id'])
    companies = []
    for alias in re.split(r'\s+(?:and|vs\.?|versus)\s+|\s*,\s*', match['companies'], flags=re.I):
        candidates = aliases.get(alias.strip().casefold(), set())
        if not candidates:
            return stop('refuse', f'Company "{alias.strip()}" is absent from the confirmed selected inventory.')
        if len(candidates) != 1:
            return stop('clarify', f'Company alias "{alias.strip()}" is ambiguous; use its confirmed company ID.')
        company = next(iter(candidates))
        if company in companies:
            return stop('clarify', 'List each requested company once.')
        companies.append(company)
    period_labels = [re.sub(r'\s+', ' ', p.upper()).replace('FY ', 'FY')
                     for p in re.split(r'\s+to\s+', match['periods'], flags=re.I)]
    metric = METRICS[match['metric'].lower()]
    basis = {'gaap': 'GAAP', 'non-gaap': 'non-GAAP', 'operating': 'operating'}[match['basis'].casefold()]
    scope = match['scope'].lower()
    if len(companies) > 3 or len(companies) * len(period_labels) > 6:
        return stop('clarify', 'Narrow the request to at most three companies and six required tasks.')
    action = match['action'].lower()
    if action in ('growth', 'change') and (len(companies) != 1 or len(period_labels) != 2):
        return stop('clarify', 'A trend requires one company and two explicit reporting periods.')
    if action in ('show', 'compare', 'rank') and len(period_labels) != 1:
        return stop('clarify', 'Use one reporting period for this lookup, comparison or ranking.')
    task_metrics = [metric]
    if action in ('margin', 'delivery ratio', 'production gap'):
        if len(companies) != 1 or len(period_labels) != 1:
            return stop('clarify', 'A ratio or operating gap requires one company and one reporting period.')
        if action == 'margin':
            if metric not in ('gross_profit', 'operating_income', 'net_income', 'net_income_parent'):
                return stop('clarify', 'Choose gross profit, operating income or net income as the margin numerator.')
            task_metrics.append('revenue')
        else:
            if metric != 'vehicle_deliveries' or basis != 'operating':
                return stop('clarify', 'Use operating vehicle deliveries and production for this calculation.')
            task_metrics.append('vehicle_production')
    return {'action': action, 'companies': companies, 'period_labels': period_labels,
            'metric': metric, 'task_metrics': task_metrics, 'basis': basis, 'scope': scope}


def question_filters(parsed):
    return [{'company_id': company, 'metric_id': metric, 'scope': parsed['scope'],
             'basis': parsed['basis'], 'period_label': label}
            for company in parsed['companies'] for label in parsed['period_labels'] for metric in parsed['task_metrics']]


def resolve_question(question, selections, inventory, observations, parsed=None):
    parsed = parsed or parse_question(question, inventory)
    if 'outcome' in parsed:
        return parsed
    action, metric, scope, basis = (parsed[k] for k in ('action', 'metric', 'scope', 'basis'))
    tasks = []
    for company in parsed['companies']:
        for label in parsed['period_labels']:
            for metric in parsed['task_metrics']:
                periods = {o.period.identity(): o.period for o in observations
                           if o.company_id == company and o.metric_id == metric and o.scope == scope and o.basis == basis
                           and re.sub(r'\s+', ' ', o.period.fiscal_label.upper()).replace('FY ', 'FY') == label}
                if len(periods) > 1:
                    return {'outcome': 'clarify', 'answer': f'{company} has multiple actual intervals labeled {label}; select explicit dates.',
                            'coverage': [], 'citations': {}, 'usage': {'planner_calls': 0, 'generator_calls': 0, 'embedding_calls': 0, 'cost_usd': '0'}}
                period = next(iter(periods.values())) if periods else FinancialPeriod(
                    kind='annual' if label.startswith('FY') else 'quarter', calendar='unresolved', fiscal_label=label)
                tasks.append({'task_id': f'task-{len(tasks) + 1}', 'company_id': company, 'metric_id': metric,
                              'period': period.model_dump(mode='json'), 'scope': scope, 'basis': basis})
    calculations = []
    if action in ('growth', 'change'):
        operation = 'growth' if action == 'growth' else 'percentage_point_change' if parsed['metric'].endswith('_margin') else 'difference'
        calculations = [{'operation': operation, 'start_task_id': tasks[0]['task_id'], 'end_task_id': tasks[1]['task_id']}]
    if action in ('margin', 'delivery ratio', 'production gap'):
        operation = {'margin': 'margin', 'delivery ratio': 'delivery_to_production', 'production gap': 'difference'}[action]
        calculations = [{'operation': operation, 'start_task_id': tasks[0]['task_id'], 'end_task_id': tasks[1]['task_id']}]
    return {'request': {'question': question, 'selections': selections, 'tasks': tasks,
                        'mode': 'ranking' if action == 'rank' else 'comparison' if action == 'compare' else 'lookup',
                        'calculations': calculations}}
