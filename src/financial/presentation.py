"""Deterministic task labels for standalone cited narrative answers."""


def narrative_answer(tasks, claims):
    lines = []
    for claim in claims:
        task = tasks[claim['task_id']]
        period = task.get('document_period_label')
        label = f"{task['company_id']} / {period}" if period else task['company_id']
        lines.append(f"{label}: {claim['text']} [{claim['evidence_id']}]")
    lines.append('Generated synthesis requires semantic review; exact quote locators establish provenance only.')
    return '\n'.join(lines)
