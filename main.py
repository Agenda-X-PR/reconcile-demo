"""FastAPI demo wrapper around the reconcile tool."""

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from reconcile.cli import load_bank, load_processor
from reconcile.matcher import MatchResult, match

app = FastAPI(
    title="reconcile-demo",
    version="0.1.0",
    description="Match payment processor exports against bank statements.",
)


def _serialize(result: MatchResult) -> dict:
    """Convert a MatchResult into JSON-safe dictionaries."""
    return {
        "summary": {
            "matched": len(result.matched),
            "unmatched_processor": len(result.unmatched_processor),
            "unmatched_bank": len(result.unmatched_bank),
        },
        "matched": [
            {
                "processor": {
                    "reference": p.reference,
                    "amount": str(p.amount),
                    "currency": p.currency,
                    "status": p.status,
                    "created_at": p.created_at.isoformat(),
                },
                "bank": {
                    "description": b.description,
                    "amount": str(b.amount),
                    "currency": b.currency,
                    "transaction_date": b.transaction_date.isoformat(),
                },
            }
            for p, b in result.matched
        ],
        "unmatched_processor": [
            {
                "reference": r.reference,
                "amount": str(r.amount),
                "currency": r.currency,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r in result.unmatched_processor
        ],
        "unmatched_bank": [
            {
                "description": b.description,
                "amount": str(b.amount),
                "currency": b.currency,
                "transaction_date": b.transaction_date.isoformat(),
            }
            for b in result.unmatched_bank
        ],
    }


def _write_temp(data: bytes) -> str:
    with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as f:
        f.write(data)
        return f.name


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return INDEX_HTML

@app.post("/reconcile")
async def reconcile(
    processor_csv: UploadFile = File(...),
    bank_csv: UploadFile = File(...),
):
    """Accept two CSV uploads, return the reconciliation report as JSON."""
    proc_bytes = await processor_csv.read()
    bank_bytes = await bank_csv.read()

    proc_path = _write_temp(proc_bytes)
    bank_path = _write_temp(bank_bytes)

    try:
        processor = load_processor(Path(proc_path))
        bank = load_bank(Path(bank_path))
        result = match(processor, bank)
        return _serialize(result)
    except SystemExit as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        Path(proc_path).unlink(missing_ok=True)
        Path(bank_path).unlink(missing_ok=True)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>reconcile-demo</title>
  <style>
    :root { --bg: #f8f8f4; --ink: #171716; --muted: #666761; --line: #d4d5cf; --accent: #2859c9; --high: #ca1830; --medium: #b88700; }
    * { box-sizing: border-box; }
    body { margin: 0; padding: 2rem 1rem; background: var(--bg); color: var(--ink); font-family: system-ui, -apple-system, sans-serif; line-height: 1.5; }
    main { max-width: 720px; margin: 0 auto; }
    h1 { margin: 0 0 0.25rem; font-size: 1.75rem; }
    .sub { margin: 0 0 2rem; color: var(--muted); }
    form { display: flex; flex-direction: column; gap: 1rem; padding: 1.5rem; border: 1px solid var(--line); border-radius: 8px; background: #fff; margin-bottom: 2rem; }
    label { display: flex; flex-direction: column; gap: 0.35rem; font-size: 0.9rem; font-weight: 600; }
    input[type=file] { padding: 0.5rem; border: 1px solid var(--line); border-radius: 4px; font: inherit; background: var(--bg); }
    button { padding: 0.65rem 1rem; border: 0; border-radius: 4px; background: var(--accent); color: #fff; font: inherit; font-weight: 600; cursor: pointer; }
    button:hover { background: #1c45a8; }
    button:disabled { opacity: 0.5; cursor: wait; }
    .error { padding: 1rem; border: 1px solid var(--high); border-radius: 4px; background: #fdf0f1; color: var(--high); margin-bottom: 1.5rem; }
    .section { margin-bottom: 2rem; }
    .section h2 { margin: 0 0 0.75rem; font-size: 1rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); }
    .summary { display: flex; gap: 1.5rem; padding: 1rem; border: 1px solid var(--line); border-radius: 8px; background: #fff; }
    .stat { display: flex; flex-direction: column; }
    .stat .num { font-size: 1.75rem; font-weight: 700; }
    .stat .label { color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .row { display: grid; grid-template-columns: 1fr auto; gap: 0.5rem 1rem; padding: 0.75rem; border: 1px solid var(--line); border-radius: 4px; background: #fff; margin-bottom: 0.5rem; font-size: 0.9rem; }
    .row .ref { font-family: ui-monospace, monospace; font-weight: 600; }
    .row .amount { font-family: ui-monospace, monospace; color: var(--muted); }
    .row .detail { grid-column: 1 / -1; color: var(--muted); font-size: 0.85rem; }
    .empty { color: var(--muted); font-style: italic; }
  </style>
</head>
<body>
  <main>
    <h1>reconcile</h1>
    <p class="sub">Match a payment processor export against a bank statement. Upload both CSVs and get a report.</p>

    <form id="form">
      <label>
        Processor CSV
        <input type="file" name="processor_csv" accept=".csv" required>
      </label>
      <label>
        Bank CSV
        <input type="file" name="bank_csv" accept=".csv" required>
      </label>
      <button type="submit" id="submit">Reconcile</button>
    </form>

    <div id="output"></div>
  </main>

  <script>
    const form = document.getElementById('form');
    const submit = document.getElementById('submit');
    const output = document.getElementById('output');

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      output.innerHTML = '';
      submit.disabled = true;
      submit.textContent = 'Reconciling...';

      const formData = new FormData();
      formData.append('processor_csv', form.processor_csv.files[0]);
      formData.append('bank_csv', form.bank_csv.files[0]);

      try {
        const response = await fetch('/reconcile', { method: 'POST', body: formData });
        const text = await response.text();
        let data;
        try { data = JSON.parse(text); } catch { data = null; }

        if (!response.ok) {
          const msg = (data && data.detail) || text || 'Unknown error';
          output.innerHTML = '<div class="error">' + escapeHtml(msg) + '</div>';
        } else {
          output.innerHTML = renderReport(data);
        }
      } catch (err) {
        output.innerHTML = '<div class="error">Network error: ' + escapeHtml(String(err)) + '</div>';
      } finally {
        submit.disabled = false;
        submit.textContent = 'Reconcile';
      }
    });

    function escapeHtml(s) {
      return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }

    function renderReport(data) {
      const s = data.summary;
      let html = '<div class="section"><h2>Summary</h2><div class="summary">';
      html += '<div class="stat"><span class="num">' + s.matched + '</span><span class="label">Matched</span></div>';
      html += '<div class="stat"><span class="num">' + s.unmatched_processor + '</span><span class="label">Unmatched processor</span></div>';
      html += '<div class="stat"><span class="num">' + s.unmatched_bank + '</span><span class="label">Unmatched bank</span></div>';
      html += '</div></div>';

      html += renderSection('Matched', data.matched.map(m => ({
        ref: m.processor.reference,
        amount: m.processor.amount + ' ' + m.processor.currency,
        detail: m.bank.description
      })));

      html += renderSection('Unmatched processor rows', data.unmatched_processor.map(r => ({
        ref: r.reference,
        amount: r.amount + ' ' + r.currency,
        detail: 'Status: ' + r.status
      })));

      html += renderSection('Unmatched bank rows', data.unmatched_bank.map(b => ({
        ref: b.description,
        amount: b.amount + ' ' + b.currency,
        detail: b.transaction_date
      })));

      return html;
    }

    function renderSection(title, rows) {
      let html = '<div class="section"><h2>' + title + '</h2>';
      if (rows.length === 0) {
        html += '<p class="empty">None</p>';
      } else {
        for (const row of rows) {
          html += '<div class="row">';
          html += '<span class="ref">' + escapeHtml(row.ref) + '</span>';
          html += '<span class="amount">' + escapeHtml(row.amount) + '</span>';
          html += '<span class="detail">' + escapeHtml(row.detail) + '</span>';
          html += '</div>';
        }
      }
      html += '</div>';
      return html;
    }
  </script>
</body>
</html>
"""