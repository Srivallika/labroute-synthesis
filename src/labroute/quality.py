"""Label-quality checks for outcome records.

Why this exists: yields extracted from patents or other text-mined sources are often missing,
impossible (negative or above 100%), or reported inconsistently (crude vs isolated). Treating
them as ground-truth success labels would quietly corrupt every downstream estimate.

Rule in this prototype: a **public** record is only trusted as a success label if it carries a
valid yield. A **lab** record may omit the yield, because the lab can state the pass/fail result
directly against its own success criterion. Which public datasets are trusted for yields is a
documented Phase 1 decision, not something this module can decide.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Optional

from .models import Outcome


def yield_status(yield_pct: Optional[float]) -> str:
    """Return "ok", "missing", "negative", or "over_100"."""
    if yield_pct is None:
        return "missing"
    if yield_pct < 0:
        return "negative"
    if yield_pct > 100:
        return "over_100"
    return "ok"


def is_trusted(outcome: Outcome, require_valid_yield_for_public: bool = True) -> bool:
    status = yield_status(outcome.yield_pct)
    if outcome.source == "public":
        return status == "ok" if require_valid_yield_for_public else status in ("ok", "missing")
    # Lab record: a missing yield is allowed, an impossible one is not.
    return status in ("ok", "missing")


def trusted_outcomes(
    outcomes: Iterable[Outcome], require_valid_yield_for_public: bool = True
) -> list:
    """Keep only outcomes whose labels can be trusted (see module docstring)."""
    return [o for o in outcomes if is_trusted(o, require_valid_yield_for_public)]


def quality_report(outcomes: Iterable[Outcome]) -> dict:
    """Counts of yield problems by source, plus how many records would be kept."""
    outcomes = list(outcomes)
    kept = len(trusted_outcomes(outcomes))
    by_source: dict = {}
    for o in outcomes:
        by_source.setdefault(o.source, Counter())[yield_status(o.yield_pct)] += 1
    return {
        "total": len(outcomes),
        "trusted": kept,
        "excluded": len(outcomes) - kept,
        "yield_status_by_source": {s: dict(c) for s, c in by_source.items()},
    }
