"""
Bulk receipt importer for the Petty Cash Ledger.

Scans every image / PDF in the `data/` folder with the Gemini API (same logic as
the in-app "Add Expense" AI scan), then creates a Petty Cash expense for each one
so it shows up in the Ledger with the file attached as its receipt.

Deduplication: before adding, an expense is compared against the existing ledger
on THREE fields — date + amount + paid_to. If all three match an existing entry
(or one already added earlier in this same run), the file is skipped.

Behaviour (configured per request):
  - Recorded under the SUPER_ADMIN_EMAIL account from .env
  - Successfully imported files are moved to data/processed/
  - Files Gemini can't extract amount/date from are skipped & logged (left in place)

Usage:
    python import_receipts.py                 # real import
    python import_receipts.py --dry-run       # scan + report, write nothing
    python import_receipts.py --data-dir some/other/folder
"""

import argparse
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone

import requests as http_requests
from dotenv import load_dotenv

load_dotenv()

# Importing firebase_models initialises Firebase (via firebase_config).
from firebase_models import FirebaseUser, FirebasePettyCashExpense  # noqa: E402
from firebase_admin import storage as fb_storage  # noqa: E402


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

SUPPORTED = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
    '.webp': 'image/webp', '.gif': 'image/gif', '.pdf': 'application/pdf',
}

# Categories must match PETTY_CASH_PREDEFINED_CATEGORIES so the Ledger displays them.
VALID_CATEGORIES = {'office_supplies', 'travel', 'food', 'utilities', 'misc'}

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODELS = [
    os.getenv('GEMINI_MODEL', 'gemini-2.5-flash'),
    'gemini-2.5-flash', 'gemini-flash-latest',
]

PROMPT = (
    "You are a receipt/invoice parser. Extract the following fields from this "
    "document and return ONLY valid JSON (no markdown, no code fences):\n"
    "{\n"
    '  "amount": <number, the final total paid, no currency symbol>,\n'
    '  "description": "<short description of what was purchased>",\n'
    '  "paid_to": "<vendor / shop / party name>",\n'
    '  "date": "<date in YYYY-MM-DD format, or empty string if not found>",\n'
    '  "category": "<one of: office_supplies, travel, food, utilities, misc>"\n'
    "}\n"
    "Rules: amount must be a plain number; if multiple amounts use the final total; "
    "category must be one of the listed options (use misc if unsure); "
    "if a field is missing use empty string (or 0 for amount). Return ONLY the JSON."
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def log(msg):
    print(msg, flush=True)


def scan_with_gemini(file_bytes, mime_type):
    """Send a file to Gemini and return the parsed dict, or raise on failure."""
    import base64
    payload = {
        'contents': [{
            'parts': [
                {'text': PROMPT},
                {'inline_data': {'mime_type': mime_type,
                                 'data': base64.b64encode(file_bytes).decode('utf-8')}},
            ]
        }]
    }
    seen, models = set(), []
    for m in GEMINI_MODELS:
        if m not in seen:
            seen.add(m)
            models.append(m)

    last_error = None
    for model in models:
        url = (f'https://generativelanguage.googleapis.com/v1beta/models/'
               f'{model}:generateContent?key={GEMINI_API_KEY}')
        resp = http_requests.post(url, json=payload, timeout=60)
        if resp.status_code == 404:
            last_error = f'{model}: not found'
            continue
        resp.raise_for_status()
        raw = resp.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
            raw = raw.strip()
        return json.loads(raw)
    raise RuntimeError(f'No usable Gemini model ({last_error})')


def upload_to_storage(file_bytes, mime_type, ext):
    blob_name = f"petty_cash_receipts/{uuid.uuid4().hex}.{ext.lstrip('.')}"
    bucket = fb_storage.bucket()
    blob = bucket.blob(blob_name)
    blob.upload_from_string(file_bytes, content_type=mime_type)
    blob.make_public()
    return blob.public_url


def norm_date(value):
    """Return a YYYY-MM-DD string from a datetime or string, or '' if not parseable."""
    if value is None:
        return ''
    if hasattr(value, 'strftime'):
        return value.strftime('%Y-%m-%d')
    return str(value)[:10]


def dedup_key(date_str, amount, paid_to):
    return (date_str, round(float(amount or 0), 2), (paid_to or '').strip().lower())


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser(description='Import receipts from a folder into the Petty Cash ledger.')
    parser.add_argument('--data-dir', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data'))
    parser.add_argument('--dry-run', action='store_true', help='Scan and report only; write nothing.')
    args = parser.parse_args()

    if not GEMINI_API_KEY:
        log('ERROR: GEMINI_API_KEY is not set in the environment / .env')
        sys.exit(1)

    data_dir = args.data_dir
    if not os.path.isdir(data_dir):
        log(f'ERROR: data folder not found: {data_dir}')
        sys.exit(1)

    # Resolve the recorder (superadmin from .env)
    admin_email = os.getenv('SUPER_ADMIN_EMAIL')
    admin = FirebaseUser.get_by_email(admin_email) if admin_email else None
    if not admin:
        log(f'ERROR: could not find superadmin user for SUPER_ADMIN_EMAIL={admin_email!r}')
        sys.exit(1)
    recorded_by = admin['id']
    log(f'Recording imported expenses under: {admin.get("full_name") or admin.get("username")} ({admin_email})')

    processed_dir = os.path.join(data_dir, 'processed')
    if not args.dry_run:
        os.makedirs(processed_dir, exist_ok=True)

    # Build dedup set from existing ledger
    existing = FirebasePettyCashExpense.get_all(limit=100000)
    seen_keys = set()
    for e in existing:
        seen_keys.add(dedup_key(norm_date(e.get('date')), e.get('amount'), e.get('paid_to')))
    log(f'Loaded {len(existing)} existing ledger entries for duplicate checking.\n')

    # Gather files (skip the processed/ subfolder)
    files = []
    for name in sorted(os.listdir(data_dir)):
        full = os.path.join(data_dir, name)
        if not os.path.isfile(full):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext in SUPPORTED:
            files.append((name, full, ext))

    if not files:
        log('No supported image/PDF files found in the data folder.')
        return

    log(f'Found {len(files)} file(s) to process.\n' + '-' * 60)

    stats = {'imported': 0, 'incomplete': 0, 'duplicate': 0, 'skipped': 0, 'failed': 0}

    for name, full, ext in files:
        mime = SUPPORTED[ext]
        log(f'\n• {name}')
        try:
            with open(full, 'rb') as fh:
                file_bytes = fh.read()
            data = scan_with_gemini(file_bytes, mime)
        except Exception as exc:
            log(f'  ✗ Scan failed: {exc}  → skipped')
            stats['failed'] += 1
            continue

        amount = data.get('amount') or 0
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            amount = 0
        date_str = (data.get('date') or '').strip()
        paid_to = (data.get('paid_to') or '').strip()
        description = (data.get('description') or '').strip()
        category = (data.get('category') or 'misc').strip()
        if category not in VALID_CATEGORIES:
            category = 'misc'

        # IMPORTANT fields = amount (price) + paid_to (whom). If either is missing,
        # the receipt isn't worth recording → skip & log. Non-essential fields like
        # date are allowed to be missing (date defaults to today).
        missing_important = []
        if amount <= 0:
            missing_important.append('amount')
        if not paid_to:
            missing_important.append('paid_to')
        if missing_important:
            log(f'  ⚠ Missing important field(s): {", ".join(missing_important)}  → skipped & logged (not written)')
            stats['skipped'] += 1
            continue

        # Date is optional — default to today if missing/unparseable.
        date_defaulted = False
        if not date_str:
            parsed_date = datetime.now(timezone.utc)
            date_str = parsed_date.strftime('%Y-%m-%d')
            date_defaulted = True
        else:
            try:
                parsed_date = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            except ValueError:
                parsed_date = datetime.now(timezone.utc)
                date_str = parsed_date.strftime('%Y-%m-%d')
                date_defaulted = True

        # Deduplicate on date + amount + paid_to (all present now).
        key = dedup_key(date_str, amount, paid_to)
        if key in seen_keys:
            log(f'  ⊘ Duplicate (date={date_str}, amount={amount}, paid_to={paid_to!r})  → skipped')
            stats['duplicate'] += 1
            continue

        receipt_note = 'Imported from data/ via Gemini scan'
        if date_defaulted:
            receipt_note += ' — REVIEW: date defaulted (not found on receipt)'
            log('  ⚠ Date not found — defaulted to today, flagged for review')
        log(f'  ✓ Parsed: amount={amount}, date={date_str}, paid_to={paid_to!r}, category={category}')

        if args.dry_run:
            log('    (dry-run — not written)')
            seen_keys.add(key)
            stats['imported'] += 1
            if date_defaulted:
                stats['incomplete'] += 1
            continue

        try:
            url = upload_to_storage(file_bytes, mime, ext)
            file_obj = {'url': url, 'name': name, 'type': mime, 'is_pdf': mime == 'application/pdf'}
            FirebasePettyCashExpense.create(
                date=parsed_date,
                amount=amount,
                category=category,
                description=description,
                paid_to=paid_to,
                receipt_note=receipt_note,
                recorded_by=recorded_by,
                receipt_image_url=url,
                receipt_files=[file_obj],
                payment_mode='cash',
            )
        except Exception as exc:
            log(f'  ✗ Failed to save/upload: {exc}  → skipped')
            stats['failed'] += 1
            continue

        seen_keys.add(key)
        stats['imported'] += 1
        if date_defaulted:
            stats['incomplete'] += 1
        # Move processed file
        try:
            shutil.move(full, os.path.join(processed_dir, name))
            log(f'    → added to ledger and moved to processed/')
        except Exception as exc:
            log(f'    → added to ledger (could not move file: {exc})')

    log('\n' + '=' * 60)
    log(f"Done. Imported: {stats['imported']} (of which {stats['incomplete']} had date defaulted) | "
        f"Duplicates: {stats['duplicate']} | Skipped (missing amount/paid_to): {stats['skipped']} | "
        f"Failed: {stats['failed']}")
    if args.dry_run:
        log('(dry-run — nothing was written to the ledger or storage)')


if __name__ == '__main__':
    main()
