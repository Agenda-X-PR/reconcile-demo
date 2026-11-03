"""Command-line entry point for the reconcile tool."""
from .matcher import MatchResult, match

import argparse
import csv
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .models import BankRow, ProcessorRow


def load_processor(path: Path) -> list[ProcessorRow]:
    """Read a processor CSV export into a list of ProcessorRow objects."""
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line_no, row in enumerate(reader, start=2):
            try:
                rows.append(
                    ProcessorRow(
                        reference=row["reference"].strip(),
                        amount=Decimal(row["amount"].strip()),
                        currency=row["currency"].strip().upper(),
                        status=row["status"].strip().lower(),
                        created_at=datetime.fromisoformat(
                            row["created_at"].strip().replace("Z", "+00:00")
                        ),
                    )
                )
            except (KeyError, InvalidOperation, ValueError) as e:
                raise SystemExit(f"Processor CSV line {line_no}: {e}")
    return rows


def load_bank(path: Path) -> list[BankRow]:
    """Read a bank CSV export into a list of BankRow objects."""
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line_no, row in enumerate(reader, start=2):
            try:
                rows.append(
                    BankRow(
                        description=row["description"].strip(),
                        amount=Decimal(row["amount"].strip()),
                        currency=row["currency"].strip().upper(),
                        transaction_date=datetime.fromisoformat(
                            row["transaction_date"].strip()
                        ),
                    )
                )
            except (KeyError, InvalidOperation, ValueError) as e:
                raise SystemExit(f"Bank CSV line {line_no}: {e}")
    return rows

def print_report(result: MatchResult) -> None:
    """Print the three-section reconciliation report."""
    print()
    print(f"Matched: {len(result.matched)}")
    for proc, bank in result.matched:
        print(f"  {proc.reference:<12} {proc.amount:>10} {proc.currency}  ->  {bank.description}")

    print()
    print(f"Unmatched processor rows: {len(result.unmatched_processor)}")
    for proc in result.unmatched_processor:
        print(f"  {proc.reference:<12} {proc.amount:>10} {proc.currency}  (status: {proc.status})")

    print()
    print(f"Unmatched bank rows: {len(result.unmatched_bank)}")
    for bank in result.unmatched_bank:
        print(f"  {bank.description:<30} {bank.amount:>10} {bank.currency}")

def main(argv: list[str] | None = None) -> int:
    """Entry point: parse arguments, load both CSVs, print counts."""
    parser = argparse.ArgumentParser(
        prog="reconcile",
        description="Match payment processor exports against bank statements.",
    )
    parser.add_argument("processor_csv", type=Path, help="CSV export from the payment processor")
    parser.add_argument("bank_csv", type=Path, help="CSV export from the bank")
    args = parser.parse_args(argv)

    for path in (args.processor_csv, args.bank_csv):
        if not path.exists():
            print(f"Error: file not found: {path}", file=sys.stderr)
            return 2

    processor_rows = load_processor(args.processor_csv)
    bank_rows = load_bank(args.bank_csv)
    print(f"Loaded {len(processor_rows)} processor rows, {len(bank_rows)} bank rows")
    result = match(processor_rows, bank_rows)
    print_report(result)
    return 0