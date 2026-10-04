"""Portable integrity of real-source transition receipts; no DB or provider calls."""
from pathlib import Path
import shutil
import pytest

from scripts.check_authentic_source_change import replay

CAPTURE = Path(__file__).resolve().parents[2] / 'docs/benchmarks/20261004-authentic-gaps/source-change-corrected'


def test_saved_authentic_version_change_and_rerun():
    result = replay(CAPTURE)
    assert result['passed'] == result['checks'] == 13
    assert result['authentic_scenarios'] == 1 and result['api_calls'] == 0


def test_changed_transition_labels_fail_closed(tmp_path):
    shutil.copytree(CAPTURE, tmp_path/'capture')
    (tmp_path/'capture'/'labels.json').write_text('{}')
    with pytest.raises(ValueError, match='hash mismatch'):
        replay(tmp_path/'capture')
