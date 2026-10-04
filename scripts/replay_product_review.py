"""Replay a named development review; never infer semantic support from locators."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def metric(passes):
    return {'passed': sum(passes), 'denominator': len(passes),
            'value': sum(passes) / len(passes) if passes else None}


def wilson_interval(passed, n):
    if not n:
        return None
    p, z = passed / n, 1.959963984540054
    center = (p + z*z/(2*n)) / (1 + z*z/n)
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1 + z*z/n)
    return [center-half, center+half]


def replay(folder, labels_path):
    folder, labels_path = Path(folder), Path(labels_path)
    review = json.loads((folder / 'review.json').read_text())
    results_path = folder / review.get('results_file', 'results.jsonl')
    if (review['results_sha256'] != digest(results_path)
            or review['labels_sha256'] != digest(labels_path)):
        raise ValueError('Review is not bound to these results and labels')
    labels = json.loads(labels_path.read_text())['cases']
    rows = [json.loads(line) for line in results_path.read_text().splitlines()]
    audits = review['cases']
    ids = [c['case_id'] for c in labels]
    if ([r['case_id'] for r in rows] != ids or [a['case_id'] for a in audits] != ids
            or len(set(ids)) != len(ids) or not review.get('reviewer')):
        raise ValueError('Every case needs one named review in frozen order')
    scores, numeric, support, evidence, operands, failures = [], [], [], [], [], Counter()
    groups = {}
    for case, row, audit in zip(labels, rows, audits):
        result = row['result']
        if digest_result(result) != audit['result_sha256']:
            raise ValueError('Reviewed result changed')
        for key in ('rubric_pass', 'original_binding_support', 'safe_outcome'):
            if type(audit.get(key)) is not bool:
                raise ValueError('Missing semantic review stays unassessable')
        claims = result.get('claims', [])
        if len(audit['claim_support']) != len(claims) or any(type(v) is not bool for v in audit['claim_support']):
            raise ValueError('Every issued narrative claim needs semantic review')
        expected_ids = {o['observation_id'] for o in case['expected']['observations']}
        cited_ids = set(result.get('citations', {}))
        if expected_ids:
            numeric.append(audit['original_binding_support'] and expected_ids <= cited_ids
                           and row['checks'].get('numeric_original_bindings', False))
            evidence.extend(o in cited_ids for o in expected_ids)
        support.extend(audit['claim_support'])
        for calc in result.get('calculations', []):
            operands.extend(bool(c['evidence']) and c['source'] in result['manifest']
                            for c in calc['citations'])
        # Rubric review includes completeness, requested distinctions and precise gaps.
        passed = (all(row['checks'].values()) and audit['rubric_pass']
                  and audit['original_binding_support'] and audit['safe_outcome']
                  and all(audit['claim_support']))
        scores.append(passed)
        groups.setdefault(case['primary_slice'], []).append(passed)
        for failure in audit['failures']:
            failures[failure] += 1
    subgroups = {tag: metric([s for c, s in zip(labels, scores) if tag in c['tags']])
                 for tag in ('narrative', 'answerable_cross_company')}
    multi = [s for a, s in zip(audits, scores) if len(set(a['required_report_families'])) >= 2]
    return {'qualification': review['qualification'], 'reviewer': review['reviewer'],
            'strict_authentic_development': metric(scores), 'slices': {k: metric(v) for k, v in groups.items()},
            'strict_wilson_95_interval': wilson_interval(sum(scores), len(scores)),
            'uncertainty_note': 'Descriptive case-level interval only; reused report families make cases correlated. Not a population accuracy guarantee.',
            'subgroups': subgroups, 'distinct_required_multi_document': metric(multi),
            'numeric_accuracy': metric(numeric), 'narrative_claim_support': metric(support),
            'required_numeric_cell_coverage': metric(evidence), 'issued_operand_coverage': metric(operands),
            'failure_classes': dict(failures), 'independent_release_reviews': 0,
            'holdout': 'not_accessed', 'release_decision': 'held',
            'coverage_limits': review['coverage_limits']}


def digest_result(result):
    return hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('--labels', type=Path, default=Path('docs/fixtures/product/development_cases.v1.json'))
    args = parser.parse_args()
    print(json.dumps(replay(args.folder, args.labels), indent=2))
