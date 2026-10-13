"""Read-only export of preserved development results; no financial recomputation."""
import hashlib
import json
from pathlib import Path
import shutil
import fitz

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = Path(__file__).resolve().parents[1] / 'public'
HERO = ROOT / 'docs/benchmarks/20261004-release-demonstrations/heroes'
GROUPS = [
    ('equity', 'Common-equity comparison', 'Two companies. One definition.', 'common-equity', ['Rank Q2 2025']),
    ('recast', 'Recast-aware research', 'The revision is part of the answer.', 'recast-quarters', ['Latest reviewed', 'As reported']),
    ('partial', 'Useful partial answers', 'Show what is supported. Explain the gap.', 'partial-coverage', ['Supported facts', 'Difference withheld', 'Ranking withheld']),
    ('narrative', 'Period-aware narrative', 'Every claim belongs to a period.', 'period-narrative', ['Q1 & Q2 2025']),
]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def export():
    for name, expected in json.loads((HERO / 'integrity.json').read_text()).items():
        assert digest(HERO / name) == expected, name
    scenarios, artifacts = [], {}
    for key, title, subtitle, folder, labels in GROUPS:
        path = HERO / folder / 'results.jsonl'
        artifacts[str(path.relative_to(ROOT))] = digest(path)
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        scenarios.append(dict(id=key, title=title, subtitle=subtitle, steps=[dict(label=label,
            case_id=row['case_id'], artifact=str(path.relative_to(ROOT)), result=row['result']) for label, row in zip(labels, rows, strict=True)]))
    path = HERO / 'source-change/result.json'
    artifacts[str(path.relative_to(ROOT))] = digest(path)
    transition = json.loads(path.read_text())
    scenarios.append(dict(id='change', title='Source change & saved history', subtitle='A new version. A separate answer.',
        qualification=transition['qualification'], changes=transition['after_source_change'], diff=transition['reviewed_rerun']['diff'],
        steps=[dict(label=label, case_id=key, artifact=str(path.relative_to(ROOT)), result=result) for label, key, result in [
            ('Saved original', 'baseline', transition['baseline']),
            ('After metadata review · saved rerun', 'reviewed_rerun', transition['reviewed_rerun']['result']),
            ('Pinned old version', 'pinned_old_query', transition['pinned_old_query'])]]))
    path = ROOT / 'docs/benchmarks/20261004-authentic-gaps/core/results.jsonl'
    artifacts[str(path.relative_to(ROOT))] = digest(path)
    row = next(json.loads(line) for line in path.read_text().splitlines() if json.loads(line)['case_id'] == 'dev-09')
    calculation = dict(label='AMD revenue growth', case_id=row['case_id'], artifact=str(path.relative_to(ROOT)), result=row['result'])
    receipts_path = ROOT / 'docs/fixtures/product/acquisition_receipts.v1.json'
    artifacts[str(receipts_path.relative_to(ROOT))] = digest(receipts_path)
    receipts = {r['sha256']: r for r in json.loads(receipts_path.read_text())['reports']}
    originals = {}
    for result in [step['result'] for scenario in scenarios for step in scenario['steps']] + [calculation['result']]:
        for pin in result['manifest']:
            source_hash = pin['source_hash']
            receipt = receipts[source_hash]
            raw = ROOT / 'data/product_corpus' / receipt['file_name']
            assert digest(raw) == source_hash, raw
            originals[source_hash] = dict(url=receipt['url'], file=receipt['file_name'], report_id=receipt['report_id'],
                local_url='/originals/' + receipt['file_name'], sha256=source_hash)
    (PUBLIC / 'originals').mkdir(exist_ok=True)
    for item in originals.values():
        shutil.copyfile(ROOT / 'data/product_corpus' / item['file'], PUBLIC / 'originals' / item['file'])
    pages = {}
    (PUBLIC / 'pages').mkdir(exist_ok=True)
    for result in [step['result'] for scenario in scenarios for step in scenario['steps']] + [calculation['result']]:
        for citation in result['citations'].values():
            source_hash = citation['source']['source_hash']
            value = next((e for e in citation.get('evidence', []) if e['role'] == 'value'), {})
            page = value.get('page_number', citation.get('page_number'))
            key = f'{source_hash}:{page}'
            if page and key not in pages:
                name = f'{source_hash[:16]}-{page}.png'
                with fitz.open(ROOT / 'data/product_corpus' / originals[source_hash]['file']) as pdf:
                    pdf[page-1].get_pixmap(matrix=fitz.Matrix(1.3, 1.3)).save(PUBLIC / 'pages' / name)
                pages[key] = '/pages/' + name
    payload = dict(pages=pages, scope='Preserved FinRAG development captures; read-only visual prototypes; no fresh inference',
        artifacts=artifacts, scenarios=scenarios, calculation=calculation, originals=originals)
    (PUBLIC / 'fixtures.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    print(f"Exported five Hero scenarios, {sum(len(s['steps']) for s in scenarios)} steps, one calculation and {len(originals)} hash-checked originals")

if __name__ == '__main__':
    export()
