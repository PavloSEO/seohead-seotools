"""Evidence that never arrived must be reported as skipped, never as clean.

Before this, a check whose export was absent simply did not fire, and a report
renders "did not fire" as "found nothing". The arithmetic made it worse: the
health score is 100 - penalty/pages, so fewer checks running produced a *higher*
score and a partial evidence source flattered the site it measured least.

The score is deliberately not rescaled by coverage — estimating what the checks
that never ran would have found is invention. Comparability is refused instead:
coverage is machine-readable, and below a floor no score is emitted at all.
"""

import json
import shutil
from pathlib import Path

import pytest

from seohead.sf.config import load_config
from seohead.sf.core.audit import run_audit
from seohead.sf.core.registry import CHECK_REQUIRES, CHECKS, missing_requirements

EXPORTS = Path("examples/exports")


def _audit(tmp_path: Path, drop: list[str] | None = None) -> dict:
    """Run the analyzer over a copy of the example exports, minus some files."""
    work = tmp_path / "exports"
    shutil.copytree(EXPORTS, work)
    for pattern in drop or []:
        for path in work.glob(pattern):
            path.unlink()
    result = run_audit(input_mode="parse-exports", exports_dir=str(work), config=load_config(None))
    return json.loads(json.dumps(result.to_json()))


def test_declared_requirements_name_real_checks_and_frames():
    assert set(CHECK_REQUIRES) <= set(CHECKS)
    for frames in CHECK_REQUIRES.values():
        assert frames and all(isinstance(f, str) and f for f in frames)


def test_missing_requirements_reports_only_absent_frames():
    assert missing_requirements("IMG_MISSING_ALT", {"images_missing_alt"}) == ()
    assert missing_requirements("IMG_MISSING_ALT", set()) == ("images_missing_alt",)
    assert missing_requirements("NOT_A_CHECK", set()) == ()


def test_a_declared_dependency_is_skipped_with_a_readable_reason(tmp_path):
    reasons = {s["id"]: s["reason"] for s in _audit(tmp_path)["run"]["checks_skipped"]}
    assert "IMG_MISSING_ALT" in reasons
    assert "missing export" in reasons["IMG_MISSING_ALT"]
    assert "images_missing_alt" in reasons["IMG_MISSING_ALT"]


def test_silent_checks_are_counted_so_the_gap_is_visible(tmp_path):
    """Checks that neither fired nor declared a skip are the actual defect."""
    coverage = _audit(tmp_path)["summary"]["check_coverage"]
    total = coverage["checks_total"]
    assert (
        coverage["checks_fired"] + coverage["checks_skipped"] + coverage["checks_silent"] == total
    )
    # A ratchet: this may fall as declarations are added, never rise unnoticed.
    assert coverage["checks_silent"] <= 56


def test_removing_evidence_only_ever_grows_the_skip_set(tmp_path):
    baseline = _audit(tmp_path / "a")
    reduced = _audit(tmp_path / "b", drop=["*4xx*"])
    base_ids = {s["id"] for s in baseline["run"]["checks_skipped"]}
    less_ids = {s["id"] for s in reduced["run"]["checks_skipped"]}
    assert base_ids <= less_ids
    assert less_ids - base_ids, "removing an export must skip something new"
    assert (
        reduced["summary"]["check_coverage"]["coverage"]
        < baseline["summary"]["check_coverage"]["coverage"]
    )


def test_coverage_is_machine_readable_so_consumers_can_refuse_a_verdict(tmp_path):
    coverage = _audit(tmp_path)["summary"]["check_coverage"]
    assert set(coverage) == {
        "checks_total",
        "checks_fired",
        "checks_skipped",
        "checks_silent",
        "coverage",
    }
    assert coverage["checks_total"] == len(CHECKS)
    assert coverage["checks_skipped"] > 0


def test_a_partial_run_states_that_its_score_is_not_comparable(tmp_path):
    summary = _audit(tmp_path)["summary"]
    assert "not comparable" in summary["health_score_basis"]


def test_too_little_evidence_suppresses_the_score_entirely(tmp_path, monkeypatch):
    """A source serving a fraction of the registry must not grade a site."""
    from seohead.sf.core import aggregate

    monkeypatch.setattr(aggregate, "MIN_COVERAGE_TO_SCORE", 0.99)
    summary = _audit(tmp_path)["summary"]
    assert summary["health_score"] is None
    assert "coverage" in summary["health_score_reason"]


def test_a_full_registry_run_keeps_its_score(tmp_path, monkeypatch):
    from seohead.sf.core import aggregate

    monkeypatch.setattr(aggregate, "MIN_COVERAGE_TO_SCORE", 0.0)
    assert isinstance(_audit(tmp_path)["summary"]["health_score"], int)


@pytest.mark.parametrize("check_id", sorted(CHECK_REQUIRES))
def test_every_declared_check_reports_its_frame_as_missing_when_absent(check_id):
    assert missing_requirements(check_id, set()) == CHECK_REQUIRES[check_id]
