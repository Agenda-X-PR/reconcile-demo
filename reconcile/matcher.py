"""Match processor rows against bank rows."""

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .models import BankRow, ProcessorRow

# Extract references like ORD-001, PAY-12345 from free-text bank descriptions.
# Case-insensitive so lowercase bank references still match.
REFERENCE_PATTERN = re.compile(r"[A-Z]+-\d+", re.IGNORECASE)


@dataclass(frozen=True)
class FuzzyMatchConfig:
    """Tolerances for fuzzy matching. Change these to tune strictness."""

    amount_tolerance: Decimal = Decimal("0.01")
    date_window_days: int = 3


@dataclass(frozen=True)
class MatchResult:
    """Outcome of matching processor rows to bank rows."""

    matched: list[tuple[ProcessorRow, BankRow]]
    unmatched_processor: list[ProcessorRow]
    unmatched_bank: list[BankRow]


def _extract_reference(description: str) -> str | None:
    """Pull the first ORD-XXX-style reference from a bank description."""
    match = REFERENCE_PATTERN.search(description)
    return match.group(0) if match else None


def _normalize_reference(ref: str | None) -> str:
    """Uppercase and strip so case doesn't affect comparison."""
    return ref.strip().upper() if ref else ""


def _rows_match(proc: ProcessorRow, bank: BankRow, config: FuzzyMatchConfig) -> bool:
    """Apply all four rules: currency, amount, reference, date."""
    if bank.currency != proc.currency:
        return False
    if abs(bank.amount - proc.amount) > config.amount_tolerance:
        return False
    if _normalize_reference(_extract_reference(bank.description)) != _normalize_reference(proc.reference):
        return False
    day_delta = abs((bank.transaction_date.date() - proc.created_at.date()).days)
    if day_delta > config.date_window_days:
        return False
    return True


def match(
    processor_rows: list[ProcessorRow],
    bank_rows: list[BankRow],
    config: FuzzyMatchConfig | None = None,
) -> MatchResult:
    """Match on currency, amount (fuzzy), reference (fuzzy), and date (fuzzy).

    Only processor rows with status == 'successful' are eligible.
    Failed transactions never reach the bank and should not be reconciled.
    """
    if config is None:
        config = FuzzyMatchConfig()

    eligible = [r for r in processor_rows if r.status == "successful"]

    matched: list[tuple[ProcessorRow, BankRow]] = []
    matched_indices: set[int] = set()
    remaining_bank = list(bank_rows)

    for i, proc in enumerate(eligible):
        for j, bank in enumerate(remaining_bank):
            if _rows_match(proc, bank, config):
                matched.append((proc, bank))
                matched_indices.add(i)
                del remaining_bank[j]
                break

    unmatched_processor = [
        r for i, r in enumerate(eligible) if i not in matched_indices
    ]

    return MatchResult(
        matched=matched,
        unmatched_processor=unmatched_processor,
        unmatched_bank=remaining_bank,
    )