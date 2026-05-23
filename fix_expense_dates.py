"""
One-off: correct the dates of specific imported petty-cash expenses whose dates
Gemini misread (or defaulted). Each expense is located by the original receipt
filename stored in its `receipt_files[].name`.

Usage:
    python fix_expense_dates.py --dry-run    # show what would change
    python fix_expense_dates.py              # apply
"""

import argparse
from datetime import datetime, timezone

from firebase_models import FirebasePettyCashExpense

# filename (as stored in receipt_files[].name)  ->  correct date (YYYY-MM-DD)
CORRECTIONS = {
    "WhatsApp Image 2026-05-23 at 8.40.29 PM.jpeg": "2026-02-21",   # DTDC
    "WhatsApp Image 2026-05-23 at 8.41.04 PM (1).jpeg": "2026-04-16",  # Haldiram
    "WhatsApp Image 2026-05-23 at 8.41.15 PM (1).jpeg": "2026-04-22",  # Haldiram
    "WhatsApp Image 2026-05-23 at 8.41.15 PM (2).jpeg": "2026-04-22",  # Anup Yadav
    "WhatsApp Image 2026-05-23 at 8.40.40 PM.jpeg": "2026-02-28",   # Shailendra Gupta
    "WhatsApp Image 2026-05-23 at 8.40.47 PM.jpeg": "2026-03-16",   # Hazelnut Factory
    "WhatsApp Image 2026-05-23 at 8.40.54 PM.jpeg": "2026-04-17",   # Wal-Mart
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    expenses = FirebasePettyCashExpense.get_all(limit=100000)

    # Build filename -> [expense, ...] index from receipt_files
    index = {}
    for e in expenses:
        for f in (e.get('receipt_files') or []):
            name = f.get('name')
            if name:
                index.setdefault(name, []).append(e)

    changed = 0
    for filename, new_date_str in CORRECTIONS.items():
        matches = index.get(filename, [])
        if not matches:
            print(f'[!] No expense found for: {filename}')
            continue
        if len(matches) > 1:
            print(f'[!] {len(matches)} expenses match {filename} - updating all of them')

        new_dt = datetime.strptime(new_date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        for e in matches:
            old = e.get('date')
            old_str = old.strftime('%Y-%m-%d') if hasattr(old, 'strftime') else str(old)[:10]
            note = e.get('receipt_note', '') or ''
            # Clean the "date defaulted" review flag if present
            clean_note = note.split(' - REVIEW: date defaulted')[0].split(' — REVIEW: date defaulted')[0]
            print(f'- {filename}\n    {old_str}  ->  {new_date_str}  (Rs {e.get("amount")}, {e.get("paid_to")})')
            if not args.dry_run:
                update = {'date': new_dt}
                if clean_note != note:
                    update['receipt_note'] = clean_note
                FirebasePettyCashExpense.update(e['id'], update)
            changed += 1

    print('\n' + '=' * 50)
    print(f'{"Would update" if args.dry_run else "Updated"} {changed} expense(s).')
    if args.dry_run:
        print('(dry-run — nothing written)')


if __name__ == '__main__':
    main()
