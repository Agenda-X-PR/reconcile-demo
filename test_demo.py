"""Send the fixture CSVs to the local demo and print the response."""

import json
import sys
from pathlib import Path

import httpx

URL = "http://127.0.0.1:8000/reconcile"
FIXTURES = Path(__file__).parent.parent / "reconcile" / "tests" / "fixtures"


def main() -> None:
    processor = FIXTURES / "processor_sample.csv"
    bank = FIXTURES / "bank_sample.csv"

    if not processor.exists() or not bank.exists():
        print(f"Missing fixtures at {FIXTURES}")
        sys.exit(1)

    try:
        with processor.open("rb") as p, bank.open("rb") as b:
            response = httpx.post(
                URL,
                files={
                    "processor_csv": ("processor.csv", p, "text/csv"),
                    "bank_csv": ("bank.csv", b, "text/csv"),
                },
                timeout=30,
            )
    except httpx.ConnectError:
        print("Server not running. Start it with: uvicorn main:app --reload")
        sys.exit(1)

    print(f"Status: {response.status_code}")
    try:
        print(json.dumps(response.json(), indent=2))
    except json.JSONDecodeError:
        print(response.text)


if __name__ == "__main__":
    main()