#!/usr/bin/env python3
"""Offline Phase 3 input integrity and corpus readiness; never scores model answers."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / 'docs/fixtures/phase3/manifest.json'
SLICES = ('multi_document', 'temporal_scope', 'calculations_units', 'clarification',
          'conflicts_revisions', 'missing_evidence')


def scoped_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError(f'Artifact path escapes repository: {relative}')
    return path


def check_cases(cases: list[dict]) -> tuple[list[str], dict]:
    errors, ids, owners = [], set(), {}
    counts = Counter()
    numeric_holdout = 0
    for case in cases:
        identity = case.get('id')
        if not identity or identity in ids:
            errors.append(f'Duplicate or absent case identity: {identity}')
        ids.add(identity)
        split, primary = case.get('split'), case.get('primary_slice')
        if split not in ('development', 'holdout') or primary not in SLICES:
            errors.append(f'{identity}: invalid split or primary slice')
            continue
        if not isinstance(case.get('authentic'), bool):
            errors.append(f'{identity}: authentic must be an explicit boolean')
        for dimension in ('report_families', 'company_period_keys', 'revision_lineages'):
            groups = case.get(dimension, [])
            if not groups:
                errors.append(f'{identity}: missing {dimension}')
            if not isinstance(groups, list) or any(not isinstance(g, str) or not g for g in groups):
                errors.append(f'{identity}: malformed {dimension}')
                continue
            for group in groups:
                key = (dimension, group)
                if key in owners and owners[key] != split:
                    errors.append(f'{identity}: {dimension} overlaps development/holdout: {group}')
                owners[key] = split
        if split == 'holdout':
            label = case.get('frozen_label', {})
            required = {'expected_outcome', 'source_hashes', 'evidence_locators',
                        'periods', 'definitions', 'required_observation_ids',
                        'expected_gaps', 'semantic_rubric', 'review_revision'}
            if not required <= label.keys():
                errors.append(f'{identity}: incomplete frozen holdout label')
            if set(case.get('cross_tags', [])) & {'numeric', 'calculated'}:
                if not {'operands', 'expected_result', 'tolerance'} <= label.keys():
                    errors.append(f'{identity}: incomplete numeric holdout label')
        if case.get('authentic') is True:
            counts[(split, primary)] += 1
            if split == 'holdout' and set(case.get('cross_tags', [])) & {'numeric', 'calculated'}:
                numeric_holdout += 1
    readiness = {
        'authentic_development': sum(counts[('development', s)] for s in SLICES),
        'authentic_holdout': sum(counts[('holdout', s)] for s in SLICES),
        'authentic_numeric_holdout': numeric_holdout,
        'by_slice': {s: {split: counts[(split, s)] for split in ('development', 'holdout')} for s in SLICES},
    }
    ready = all(counts[(split, s)] == 8 for s in SLICES for split in ('development', 'holdout')) and numeric_holdout >= 20
    readiness['status'] = 'ready_for_label_review' if ready and not errors else 'not_assessable'
    return errors, readiness


def validate_manifest(manifest: dict, root: Path = ROOT) -> dict:
    errors = []
    def read(relative: str) -> bytes:
        return scoped_path(root, relative).read_bytes()
    immutable = manifest.get('immutable_files', {})
    if not immutable:
        errors.append('Missing immutable file hashes')
    for relative, expected in immutable.items():
        try:
            actual = hashlib.sha256(read(relative)).hexdigest()
            if actual != expected:
                errors.append(f'Hash mismatch: {relative}')
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
    regression = manifest.get('regression_identity', {})
    for kind in ('golden', 'labels'):
        relative = regression.get(f'{kind}_path')
        if not relative or immutable.get(relative) != regression.get(f'{kind}_sha256'):
            errors.append(f'Missing/inconsistent frozen regression {kind} identity')
    if manifest.get('design', {}).get('slices') != list(SLICES):
        errors.append('Primary slice design differs from phase3-design-v1')
    design = manifest.get('design', {})
    if any(design.get(k) != v for k, v in {
        'development_per_slice': 8, 'holdout_per_slice': 8,
        'minimum_authentic_numeric_holdout': 20, 'report_family_disjoint': True,
        'company_period_disjoint': True, 'revision_lineage_disjoint': True,
    }.items()):
        errors.append('Frozen split or numeric gate changed')
    for source in manifest.get('corpus', []):
        try:
            if hashlib.sha256(read(source['path'])).hexdigest() != source['sha256']:
                errors.append(f"Corpus hash mismatch: {source['path']}")
        except (OSError, ValueError, KeyError) as exc:
            errors.append(str(exc))
    try:
        for key in ('cases_path', 'observations_path'):
            if manifest[key] not in immutable:
                errors.append(f'{key} must be hash-bound')
        cases = json.loads(read(manifest['cases_path']))['cases']
        case_errors, readiness = check_cases(cases)
        errors.extend(case_errors)
        sidecar = json.loads(read(manifest['observations_path']))
        retained = {}
        blocks = {row['block']['block_id']: row for row in sidecar['blocks']}
        for bid, item in blocks.items():
            origin = item['retained_origin']
            if origin['path'] not in immutable:
                errors.append(f'{bid}: retained original capture is not hash-bound')
            if origin['path'] not in retained:
                retained[origin['path']] = {r['id']: r for r in map(json.loads, read(origin['path']).splitlines())}
            context = retained[origin['path']][origin['question_id']]['result'][origin['field']][origin['context_index']]
            span = context['evidence_spans'][origin['span_index']]
            b = item['block']
            if (span['kind'] != 'original' or span['char_start'] != 0 or
                span['char_end'] != len(span['text']) or span['block_id'] != bid or
                span['text'] != b['text'] or span['page_number'] != b['page_number'] or
                span['source_version'] != item['source_hash'] or context['document_id'] != item['source_id']):
                errors.append(f'{bid}: retained original locator mismatch')
        captured_pins = set()
        for capture in retained.values():
            for row in capture.values():
                for field in ('retrieved_contexts', 'candidates'):
                    for context in row['result'][field]:
                        meta = context.get('metadata') or {}
                        if all(meta.get(k) for k in ('source_id', 'version_id', 'build_id')):
                            captured_pins.add((meta['source_id'], meta['version_id'],
                                               meta['build_id'], context['source_version']))
        observations = sidecar['observations']
        seen_observations = set()
        for observation in observations:
            oid = observation['observation_id']
            if oid in seen_observations:
                errors.append(f'Duplicate observation: {oid}')
            seen_observations.add(oid)
            pin = observation['source']
            if tuple(pin[k] for k in ('source_id', 'version_id', 'build_id', 'source_hash')) not in captured_pins:
                errors.append(f'{oid}: source/version/build pin differs from retained capture')
            if not Decimal(observation['value']).is_finite():
                errors.append(f'{oid}: nonfinite amount')
            for link in observation['evidence']:
                item = blocks[link['block_id']]
                if (item['source_id'] != observation['source']['source_id'] or
                    item['source_hash'] != observation['source']['source_hash'] or
                    not 0 <= link['char_start'] < link['char_end'] <= len(item['block']['text']) or
                    item['block']['text'][link['char_start']:link['char_end']] != link['text'] or
                    item['block']['page_number'] != link['page_number']):
                    errors.append(f'{oid}: evidence link mismatch')
            status = observation['verification_status']
            if status not in ('unverified', 'reviewed'):
                errors.append(f'{oid}: invalid verification status')
            if status == 'reviewed':
                roles = {link['role'] for link in observation['evidence']}
                period = observation['period']
                if roles != {'value', 'row_label', 'column_period', 'unit', 'basis', 'scope'} or not observation.get('review_revision'):
                    errors.append(f'{oid}: incomplete reviewed binding')
                if period.get('calendar') == 'unresolved' or not period.get('end') or (period.get('kind') != 'instant' and not period.get('start')):
                    errors.append(f'{oid}: unresolved reviewed period')
                else:
                    end = date.fromisoformat(period['end'])
                    if period.get('start') and date.fromisoformat(period['start']) > end:
                        errors.append(f'{oid}: reversed reviewed period')
                if observation.get('binding_review', {}).get('eligibility_gaps'):
                    errors.append(f'{oid}: promoted with unresolved binding gaps')
        for case in cases:
            if not set(case.get('observation_ids', [])) <= seen_observations:
                errors.append(f"{case['id']}: unknown observation")
        ready_observations = sum(o['verification_status'] == 'reviewed' for o in observations) if not errors else 0
    except (OSError, ValueError, KeyError, TypeError, IndexError, InvalidOperation) as exc:
        errors.append(f'Malformed evaluation artifact: {exc}')
        readiness, ready_observations = {'status': 'not_assessable'}, 0
    return {'integrity': 'passed' if not errors else 'failed', 'errors': errors,
            'corpus_gate': readiness, 'eligible_authentic_observations': ready_observations,
            'release_decision': 'held', 'answer_accuracy': 'not_assessable',
            'cost_latency': 'not_assessable',
            'unfulfilled_release_requirements': manifest.get('unfulfilled_release_requirements', [])}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    try:
        report = validate_manifest(json.loads(args.manifest.read_text()))
    except (OSError, ValueError) as exc:
        report = {'integrity': 'failed', 'errors': [str(exc)], 'release_decision': 'held'}
    print(json.dumps(report, indent=2))
    return 0 if report['integrity'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
