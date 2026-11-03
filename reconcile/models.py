"""Data models for processor and bank rows."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class ProcessorRow:
    """One row from a payment processor export."""

    reference: str
    amount: Decimal
    currency: str
    status: str
    created_at: datetime


@dataclass(frozen=True)
class BankRow:
    """One row from a bank statement export."""

    description: str
    amount: Decimal
    currency: str
    transaction_date: datetime