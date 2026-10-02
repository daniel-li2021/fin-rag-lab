"""Raw usage and request-local cost estimates from a frozen price snapshot."""
from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, field
from threading import Lock
from uuid import uuid4

from src.core.config import settings

_SCOPES = ContextVar('finrag_usage_scopes', default=())


@dataclass
class CostTracker:
    by_stage: dict = field(default_factory=lambda: defaultdict(float))
    by_model: dict = field(default_factory=lambda: defaultdict(float))
    n_calls: dict = field(default_factory=lambda: defaultdict(int))
    reasoning_tokens: dict = field(default_factory=lambda: defaultdict(int))
    events: list = field(default_factory=list)
    pricing: dict = field(default_factory=lambda: deepcopy(settings.pricing_per_1k))
    request_id: str = field(default_factory=lambda: uuid4().hex)
    _lock: Lock = field(default_factory=Lock, repr=False)

    @contextmanager
    def request(self):
        """Nested scopes accumulate into their own receipt and the owning tracker.

        ContextVars propagate through LangChain/LangGraph runnable workers; a
        lock protects process-wide aggregates when independent requests overlap.
        """
        receipt = CostTracker(pricing=deepcopy(self.pricing))
        token = _SCOPES.set((*_SCOPES.get(), (self, receipt)))
        try:
            yield receipt
        finally:
            _SCOPES.reset(token)

    def _publish(self, event):
        targets = [self, *(receipt for owner, receipt in _SCOPES.get() if owner is self)]
        for target in targets:
            with target._lock:
                target.events.append(deepcopy(event))
                stage, model = event['stage'], event['model']
                cost = event['cost_usd']
                previous_stage, previous_model = target.by_stage[stage], target.by_model[model]
                target.by_stage[stage] = previous_stage + cost if previous_stage is not None and cost is not None else None
                target.by_model[model] = previous_model + cost if previous_model is not None and cost is not None else None
                target.n_calls[stage] += 1
                target.reasoning_tokens[stage] += event['reasoning_tokens'] or 0

    def record_llm(self, stage, model, input_tokens, output_tokens, reasoning_tokens=0,
                   *, raw_usage=None, usage_source='reported'):
        counts = (input_tokens, output_tokens, reasoning_tokens)
        if any(n is not None and (not isinstance(n, int) or n < 0) for n in counts):
            raise ValueError('Token counts must be nonnegative integers or unknown')
        price = self.pricing.get(model)
        known = input_tokens is not None and output_tokens is not None and price is not None
        # OpenAI completion/output totals ALREADY include reasoning tokens.
        cost = (input_tokens * price['input'] + output_tokens * price['output']) / 1000 if known else None
        self._publish({'stage': stage, 'model': model, 'input_tokens': input_tokens,
                       'output_tokens': output_tokens, 'reasoning_tokens': reasoning_tokens,
                       'raw_usage': deepcopy(raw_usage), 'usage_source': usage_source,
                       'cost_usd': cost, 'pricing_status': 'configured_estimate' if known else 'unknown'})
        return cost

    @staticmethod
    def extract_token_usage(result):
        md = getattr(result, 'response_metadata', None) or {}
        usage = md.get('token_usage') or md.get('usage') or getattr(result, 'usage_metadata', None) or {}
        details = usage.get('completion_tokens_details') or usage.get('output_token_details') or {}
        return {'prompt_tokens': usage.get('prompt_tokens', usage.get('input_tokens')),
                'completion_tokens': usage.get('completion_tokens', usage.get('output_tokens')),
                'reasoning_tokens': details.get('reasoning_tokens', details.get('reasoning', 0)),
                'raw_usage': deepcopy(usage), 'response_model': md.get('model_name') or md.get('model')}

    def record_response(self, stage, model, result):
        u = self.extract_token_usage(result)
        raw = {'usage': u['raw_usage'], 'response_model': u['response_model']}
        return self.record_llm(stage, model, u['prompt_tokens'], u['completion_tokens'], u['reasoning_tokens'],
                               raw_usage=raw, usage_source='reported' if u['raw_usage'] else 'unavailable')

    def record_embedding(self, stage, model, input_tokens, *, raw_usage=None):
        return self.record_llm(stage, model, input_tokens, 0, raw_usage=raw_usage,
                               usage_source='reported' if input_tokens is not None else 'unavailable')

    def record_vlm_image(self, stage='vlm_caption'):
        # Legacy fallback: keep an explicitly labeled estimate, not reported usage.
        cost = settings.vlm_cost_per_image
        self._publish({'stage': stage, 'model': settings.vision_model, 'input_tokens': None,
                       'output_tokens': None, 'reasoning_tokens': 0, 'raw_usage': None,
                       'usage_source': 'flat_image_estimate', 'cost_usd': cost,
                       'pricing_status': 'configured_estimate'})
        return cost

    @property
    def total(self):
        with self._lock:
            return None if any(e['cost_usd'] is None for e in self.events) else sum(self.by_stage.values())

    def report(self):
        with self._lock:
            events = deepcopy(self.events)
        unknown = [e for e in events if e['cost_usd'] is None]
        by_stage, by_model, calls, reasoning = defaultdict(float), defaultdict(float), defaultdict(int), defaultdict(int)
        for e in events:
            by_stage[e['stage']] += e['cost_usd'] or 0
            by_model[e['model']] += e['cost_usd'] or 0
            calls[e['stage']] += 1
            reasoning[e['stage']] += e['reasoning_tokens'] or 0
        def breakdown(values, key):
            return {k: None if any(e[key] == k for e in unknown) else round(v, 6) for k,v in values.items()}
        return {'request_id': self.request_id, 'total_usd': None if unknown else round(sum(by_stage.values()), 6),
                'priced_subtotal_usd': round(sum(by_stage.values()), 6), 'unknown_calls': len(unknown),
                'by_stage': breakdown(by_stage, 'stage'), 'by_model': breakdown(by_model, 'model'),
                'n_calls': dict(calls), 'reasoning_tokens': dict(reasoning),
                'events': events, 'pricing_snapshot': deepcopy(self.pricing),
                'pricing_status': 'unknown' if unknown else 'configured_estimate'}

    def current_report(self):
        receipt = next((r for owner, r in reversed(_SCOPES.get()) if owner is self), self)
        return receipt.report()

    def summary_line(self):
        r = self.report()
        cost = 'unknown' if r['total_usd'] is None else f"${r['total_usd']:.4f}"
        return f"Total: {cost} ({sum(r['n_calls'].values())} calls)"
