#!/usr/bin/env python3
"""Validate a frozen, named original review before saving immutable development cards."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def reviewed_cards(review, receipts):
    from src.financial.models import FinancialObservation
    if review['reviewer'] != 'Codex' or review['review_revision'] != 'Codex-original-financial-review-20261003-v1':
        raise ValueError('This development import requires its named original review')
    sources = {r['source_id']: r for r in receipts['reports'] if r['status'] == 'ready'}
    cards = [FinancialObservation.model_validate(o) for o in review['observations']]
    if len({c.observation_id for c in cards}) != len(cards):
        raise ValueError('Reviewed card identities must be unique')
    for card in cards:
        source = sources.get(card.source.source_id)
        if not source or (card.source.version_id, card.source.build_id, card.source.source_hash) != (
                source['version_id'], source['build_id'], source['source_sha256']):
            raise ValueError('Card source is outside the authentic development receipt')
        if card.verification_status != 'reviewed' or card.review_revision != review['review_revision']:
            raise ValueError('Card lacks the frozen named review revision')
    return cards


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--save', action='store_true')
    args = parser.parse_args()
    fixture = ROOT / 'docs/fixtures/product'
    review = json.loads((fixture / 'reviewed_observations.v1.json').read_text())
    receipts = json.loads((fixture / 'ingestion_receipts.v1.json').read_text())
    cards = reviewed_cards(review, receipts)
    from dotenv import dotenv_values
    from src.storage.registry import Registry
    from src.financial.observations import validate_observation
    registry = Registry(dotenv_values(ROOT / 'index/product-local/runtime.env')['DATABASE_URL'])
    snapshots = {}
    for card in cards:
        pin = card.source
        if pin.build_id not in snapshots:
            snapshots[pin.build_id] = registry.research_snapshot(receipts['owner'], [
                {'source_id': pin.source_id, 'version_id': pin.version_id, 'build_id': pin.build_id}])
        snapshot = snapshots[pin.build_id]
        validate_observation(card, snapshot['blocks'][pin.build_id], snapshot['sources'])
    # No writes occur before every original locator and pin has validated.
    if args.save:
        for card in cards:
            registry.save_observation(receipts['owner'], card)
    print(json.dumps({'validated': len(cards), 'saved': len(cards) if args.save else 0,
                      'reviewer': review['reviewer'], 'independent_release_review': 'held', 'model_calls': 0}))


if __name__ == '__main__':
    main()
