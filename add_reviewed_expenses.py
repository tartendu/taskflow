"""
One-off: add the manually-reviewed receipts from data/needs_review/ to the
Petty Cash ledger, using the amount/date/payee confirmed by reading each file.

- Uploads each file to Firebase Storage and attaches it as the receipt.
- Dedups on date + amount + paid_to against the existing ledger (so the Rapido
  rides that were already imported from PDFs won't double up).
- Successfully added files are moved to data/processed/.
- The Porter Consignment Note PDF is intentionally excluded (it shows only the
  declared goods value, not the fare paid).

Usage:
    python add_reviewed_expenses.py --dry-run
    python add_reviewed_expenses.py
"""

import argparse
import os
import shutil
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from firebase_models import FirebaseUser, FirebasePettyCashExpense
from firebase_admin import storage as fb_storage

SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'needs_review')
PROCESSED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'processed')

MIME = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
        '.webp': 'image/webp', '.gif': 'image/gif', '.pdf': 'application/pdf'}

# Confirmed from reading each receipt. date=None means no date on the receipt
# (defaults to today, flagged for review).
RECORDS = [
    {"file": "WhatsApp Image 2026-05-23 at 8.41.34 PM.jpeg", "amount": 700, "date": "2026-05-19",
     "paid_to": "Flash tank repair", "category": "misc", "description": "Flash tank repair (2 pcs + labour)"},
    {"file": "WhatsApp Image 2026-05-23 at 8.41.35 PM.jpeg", "amount": 90, "date": "2026-05-20",
     "paid_to": "Rapido", "category": "travel", "description": "Rapido ride"},
    {"file": "WhatsApp Image 2026-05-23 at 8.41.22 PM.jpeg", "amount": 61, "date": "2026-04-07",
     "paid_to": "Rapido", "category": "travel", "description": "Rapido auto"},
    {"file": "WhatsApp Image 2026-05-23 at 8.41.21 PM.jpeg", "amount": 76, "date": "2026-04-08",
     "paid_to": "Rapido", "category": "travel", "description": "Rapido auto"},
    {"file": "WhatsApp Image 2026-05-23 at 8.41.01 PM (2).jpeg", "amount": 76, "date": "2026-04-08",
     "paid_to": "Rapido", "category": "travel", "description": "Rapido auto"},
    {"file": "WhatsApp Image 2026-05-23 at 8.41.18 PM.jpeg", "amount": 1296.82, "date": None,
     "paid_to": "Airtel", "category": "utilities", "description": "Airtel B2B Telemedia payment"},
    {"file": "WhatsApp Image 2026-05-23 at 8.40.20 PM.jpeg", "amount": 71, "date": "2026-02-17",
     "paid_to": "Porter", "category": "travel", "description": "Parcel delivery"},
    {"file": "WhatsApp Image 2026-05-23 at 8.40.40 PM (1).jpeg", "amount": 612, "date": "2026-04-09",
     "paid_to": "Zepto", "category": "office_supplies", "description": "Disposal plates and other items"},
]


def dedup_key(date_str, amount, paid_to):
    return (date_str, round(float(amount or 0), 2), (paid_to or '').strip().lower())


def norm_date(value):
    if value is None:
        return ''
    if hasattr(value, 'strftime'):
        return value.strftime('%Y-%m-%d')
    return str(value)[:10]


def upload(path, mime, ext):
    with open(path, 'rb') as fh:
        data = fh.read()
    blob_name = f"petty_cash_receipts/{uuid.uuid4().hex}.{ext.lstrip('.')}"
    blob = fb_storage.bucket().blob(blob_name)
    blob.upload_from_string(data, content_type=mime)
    blob.make_public()
    return blob.public_url


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    admin_email = os.getenv('SUPER_ADMIN_EMAIL')
    admin = FirebaseUser.get_by_email(admin_email) if admin_email else None
    if not admin:
        print(f'ERROR: superadmin not found for SUPER_ADMIN_EMAIL={admin_email!r}')
        return
    recorded_by = admin['id']

    if not args.dry_run:
        os.makedirs(PROCESSED_DIR, exist_ok=True)

    existing = FirebasePettyCashExpense.get_all(limit=100000)
    seen = set(dedup_key(norm_date(e.get('date')), e.get('amount'), e.get('paid_to')) for e in existing)

    stats = {'added': 0, 'duplicate': 0, 'missing_file': 0}

    for r in RECORDS:
        path = os.path.join(SRC_DIR, r['file'])
        ext = os.path.splitext(r['file'])[1].lower()
        if not os.path.isfile(path):
            print(f'[!] file not found, skipping: {r["file"]}')
            stats['missing_file'] += 1
            continue

        date_defaulted = r['date'] is None
        if date_defaulted:
            parsed = datetime.now(timezone.utc)
            date_str = parsed.strftime('%Y-%m-%d')
        else:
            parsed = datetime.strptime(r['date'], '%Y-%m-%d').replace(tzinfo=timezone.utc)
            date_str = r['date']

        key = dedup_key(date_str, r['amount'], r['paid_to'])
        if key in seen:
            print(f"- DUP   {r['file']}  (Rs {r['amount']}, {date_str}, {r['paid_to']})")
            stats['duplicate'] += 1
            continue

        note = 'Imported from data/needs_review via manual review'
        if date_defaulted:
            note += ' - REVIEW: date not on receipt (defaulted to today)'

        print(f"- ADD   {r['file']}  (Rs {r['amount']}, {date_str}, {r['paid_to']}, {r['category']})")
        if not args.dry_run:
            url = upload(path, MIME[ext], ext)
            FirebasePettyCashExpense.create(
                date=parsed, amount=float(r['amount']), category=r['category'],
                description=r['description'], paid_to=r['paid_to'], receipt_note=note,
                recorded_by=recorded_by, receipt_image_url=url,
                receipt_files=[{'url': url, 'name': r['file'], 'type': MIME[ext], 'is_pdf': ext == '.pdf'}],
                payment_mode='cash',
            )
            try:
                shutil.move(path, os.path.join(PROCESSED_DIR, r['file']))
            except Exception as exc:
                print(f'      (added; could not move file: {exc})')
        seen.add(key)
        stats['added'] += 1

    print('\n' + '=' * 50)
    print(f"{'Would add' if args.dry_run else 'Added'}: {stats['added']} | "
          f"Duplicates skipped: {stats['duplicate']} | Missing files: {stats['missing_file']}")
    if args.dry_run:
        print('(dry-run - nothing written)')


if __name__ == '__main__':
    main()
