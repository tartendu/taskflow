"""
Firebase Data Migration Script
Copies all Firestore collections from old project (taskflow-25a46) to new project (taskflow-3280e)

Usage:
    python migrate_firebase.py
"""

import sys
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, firestore

# ─── Old project credentials (taskflow-25a46) hardcoded so .env change doesn't break migration ───

OLD_CRED = {
    "type": "service_account",
    "project_id": "taskflow-25a46",
    "private_key_id": "4bb2f2e7a5f06142cf9bb30ef0d27028717eb139",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQCigL6bQw9Al2tj\nlIelaTP3K65uJjFGyQjjYeqoZG+Ir7yeXEWu6M567760bjo7PuWlRPSphNBz81Iu\nvyQB5fzsugIsKCjgTiERfpIu1OmhlmCuRyOExGEmu6AlA7jvrWcevnR3ful7Qnm7\nZMx1WzlIwVtge8qAnXSCDxPjYIL9MHC7v/1NxlNJZ15wYato2GlTzSMXZp6TAr0J\nW0pmDd79ZwTk4NU6KjI1ShdK+Z6VqyhTKuTLsexRkTCHLXGnwhstR5/ugDO7tXR6\nfgHU0g2SKIGaW+wE/Xxnr4LHlxqnrsvNl+Ffd7cfJOUuAl9qjj2iUji3Ym/FkF4I\nFc4tq9QFAgMBAAECggEAI5zYaNlU7eBhSgUChzcbitcZVo1rLiqflolebkH4iXmN\n+hyZrt/ZZGrHHe6sN1Cs7j/C6KWxM0AHajQ8dWgMOmr3T+sLLkEhER7udXH2s5Fr\npbX0bEPHUMA8s+/xZyFW4I93obp/+6HRYMaR4kQ4NSAe4PGwKuiW4GvifWmou0i5\nffWvA0eJGDHxyY0RKKbk8/Uz2+FrJeRoAkMyvrG+NMubfZZDu8YmCLtzn0yh4Hz0\np4ovLVWnXR+XhIM7oI8xL/CCYptoZUHeHcJTs9C9B2B7YCVxKJJE1LMDUXJyZtvu\ngjg413Dal7/0dgnE+jfnvr1TI6snBz3Q/ytHtCmh4QKBgQDMNoCebbice29GC4cw\nwTRYL43EQTyVFqzth4CYnmtlZJrfD+SoEXLyKaJrdPhI1KnGjDkamgmUTna9ZeYn\n35fWxbauThfowtcM7YtTXI7ZJz8rysILzafL7ttt0vPqYL9CyOlOKtRXSFJSdliL\nS05CzRxHFRwqGCULJxXFI1mscQKBgQDLtm4mlAF64mmr3xXf3+JaC5EyGKuVMfHo\nYL39C13oNpAOrMTl2khVaPJyQmO9PTLOTwj78OMyHOneC+utowE/1I7BLaiuxpmP\nkEqAhDb2Wgppk2BaC1ZFNyhxhrqPDUJyY0VUupnx3K1MiOgLLmTHTO9BWkuSRRaM\nMV+X1Ln61QKBgHJcL0kJjvHq2hSyzgGKoOKlttFp6yBes3bNhEFzrhb48RXr05Qf\nOWzNzgw5U/WNSopK6ouwKZ8pFavZDbvUpjZ7QGN6jj8mJcIyoOyND94h8Wl3wZVU\nlRxKZg2prjjZ9yHSW30P1RwP/zH43nsbL/eO38Aa3Uvhe5U0TSe6NTSxAoGAV+xP\nMntjACTEsxfAGzZIPdEMQ/D97ZD29fL7TUIgr98M4iiTexlxatu2+LXK0pydVwop\nuIPJq5FrJxlCCVl3apNVYe9RBM5W7O28Gif2iPFn2RVw2qxV+d3KqOUblC6G5VQP\nUniPhSJX8daNQHYvrQ15nl1YjLMg/jU5KxD3jFkCgYB/S7MsGpNp6uoJRHkDfZP9\nDHcx9SjQBl5Pl2Tv0wBMxU+6rAkHIeHGHLsBgHI0/YsKlMFbtvcQzG0z3Yt/3VvZ\nlMJlWCinr11jKpKHUxGHbsTmrkeLWsX9ExL48/Fo3EJdxGoQFM6h36tWZVSzposj\nYCrnc0XPpEK6DJaSgII+cQ==\n-----END PRIVATE KEY-----\n",
    "client_email": "firebase-adminsdk-fbsvc@taskflow-25a46.iam.gserviceaccount.com",
    "client_id": "105966073265927661756",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40taskflow-25a46.iam.gserviceaccount.com",
}

# ─── New project credentials (taskflow-3280e) ────────────────────────────────

NEW_CRED = {
    "type": "service_account",
    "project_id": "taskflow-3280e",
    "private_key_id": "9579f5f5aad84afb5b65e0fa47155ac3b69d93f8",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDSDB2Q7xiOjsMJ\nRTd/by51ENHeXD5jND0BdehG0O3LQiB5/iNTXtDp5gOlzihcLP0acLi9zOLXqjml\nAaPJl/5Gc5YYxL8c0guNme2BOTMYfTOQMZNJrrVL6iI8Tce0mcl1aXmScUaNKoVm\njJnGAHnlesAdTPkqyCde/zpu8ZubWpzvz4gJ2iIYirwracNW9ZQ8EhRCjzSSCH6I\nmWvgHMiR8NtjP8M9XHqlFjRI+7qcS3Hd+xxvwYCWETIbQ1QvxRXA1e42BqkhYrjQ\nviv4xGoZgUgPrPShpY5XXlUWXySmbuXhWNR+WeQ9CYtyxzBDH5mJ2+ZJ+/IbObhC\nBiYrxd2XAgMBAAECggEAFDgHVo61Ye+bFZbclz84DRu/3/QoKzt5jdzwLXTqFvE4\nGBYfB2Tunj0+Z6T3HJxWBsgH+Hky8siXgOst/XdMijKRJbQ2o0sSwqApDRHY+cf/\ngSdMgsC3AeY5Qm3IRfmxu0QaaD7QKEGKEsuA997O3QiaWpewum4G4C2YTdqi/Gqp\nYQQSPGTTdG6a54DKK4stA4asKWu/laSmzgL3YBSbkDxqdUsTJsIurWyR+VDrpEki\nHV0KnLveimBUpw7ATQd5kwEExW0VKW8rVAD7IiQL+1GZnQ0dknlyPdSUSzaDe62X\nQZRlK0hUcd+g9BTdUoJ93WoNprLsboMUAbxZZkwnMQKBgQDoGtpQsmlo8Ok2N9Pb\n9yMv1JBuboKvXbhkjM3+Pg/LMNs/fZjU2Jg8u9TTW3ZJm8QPHlNy8DQReJPKj+HT\nHxXQovt0StVMUKGs7CKygJEdlq8/p0Pk2zxZKrU9J9ZMuDoWiV+9tNLXTSO4qM5U\nB5DoTnuheK0a6vEQlHiQJ51VkQKBgQDnq+7vst1sYw7kuNux1eVm1LhsYh+sh+sz\ndhefQrqGZ47LNH99UuChWTnvsYcbXppSB54WDy/N8OrzEEjrFvvR/dT3akaKtf+R\n4batjJrav/3h6VMFhl/tJ1oO/gYQ4IHqOJkwH1BmbaxJqPev9vwFN2cLBW4fYiLa\nkrHhJPxMpwKBgBqoUuCnzRF/cdmHSe7ekI0Cxd/ZE2tewTnTLimAKUI2B0hgfXgc\ntEdtb0EjJQ/JMxhlbEIsMl67UYYXRmGAFXpT7btqiNrt+9Onf0ivGXujfdc6t8KG\nJ4U6MXynoaZIFmvWNUfNh9Wwh2TDBoeCIvN7aBmgiYko6Kz10G8GDbzxAoGBANTw\nlchAcYGEc1YMC/MjlZ20/GayskZVD/zXGNNL9EJBwWBJur0ohkwHxVbpqDOh+tpX\nIhlIkDoMrQgI+d0L3R6g3zUivAAXVPdzrgNK77MNMYCKg8LaRiWnPAH3vv+YPBFb\nQIKY5b+gIvH5muBkdjUdPVtF/HhgLYUVvOYipryVAoGBALtMdJA5AHHOHeg/Xkhx\npVtfa+PXNkgGc+L8akfbHYfh4BAX1LZAgoCYtRJjMuQMle/arLmSh1MoHhLJKVom\nD/Kite7xzWpOTikAHz5zBkTQawjyClvjE7dewA8zre5DKZMskFTicPXmD8GNchoo\nqZCbwpWsQMNTlgRqu7RgFo4M\n-----END PRIVATE KEY-----\n",
    "client_email": "firebase-adminsdk-fbsvc@taskflow-3280e.iam.gserviceaccount.com",
    "client_id": "112307138433824644338",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40taskflow-3280e.iam.gserviceaccount.com",
}

# ─── Collections to migrate ───────────────────────────────────────────────────

COLLECTIONS_TO_MIGRATE = [
    'users',
    'projects',
    'tasks',
    'project_members',
    'labels',
    'comments',
    'activities',
    'events',
    'clients',
    'client_project_access',
    'notifications',
    'time_entries',
    'requirements',
    'attendance',
    'settings',
    'leave_balances',
    'petty_cash_fund',
    'petty_cash_expenses',
    'petty_cash_requests',
    'petty_cash_categories',
]

# ─── Migration Logic ──────────────────────────────────────────────────────────

def migrate_collection(old_db, new_db, collection_name):
    print(f"  '{collection_name}'...", end='', flush=True)

    docs = list(old_db.collection(collection_name).stream())
    if not docs:
        print(" empty, skipped")
        return 0

    batch = new_db.batch()
    count = 0
    batch_size = 0

    for doc in docs:
        data = doc.to_dict()
        new_ref = new_db.collection(collection_name).document(doc.id)
        batch.set(new_ref, data)
        count += 1
        batch_size += 1

        if batch_size >= 400:
            batch.commit()
            batch = new_db.batch()
            batch_size = 0

    if batch_size > 0:
        batch.commit()

    print(f" {count} docs ✓")
    return count


def run_migration():
    print("=" * 60)
    print("  Firebase Data Migration")
    print("  From: taskflow-25a46  →  To: taskflow-3280e")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    print("\n[1/3] Connecting to OLD Firebase project (taskflow-25a46)...")
    try:
        old_app = firebase_admin.initialize_app(credentials.Certificate(OLD_CRED), name='old_project')
        old_db = firestore.client(app=old_app)
        print("      ✓ Connected")
    except Exception as e:
        print(f"      ❌ Failed: {e}")
        sys.exit(1)

    print("\n[2/3] Connecting to NEW Firebase project (taskflow-3280e)...")
    try:
        new_app = firebase_admin.initialize_app(credentials.Certificate(NEW_CRED), name='new_project')
        new_db = firestore.client(app=new_app)
        print("      ✓ Connected")
    except Exception as e:
        print(f"      ❌ Failed: {e}")
        sys.exit(1)

    print("\n[3/3] Migrating collections...")
    total = 0
    failed = []

    for collection in COLLECTIONS_TO_MIGRATE:
        try:
            total += migrate_collection(old_db, new_db, collection)
        except Exception as e:
            print(f" ❌ Error: {e}")
            failed.append(collection)

    print("\n" + "=" * 60)
    print(f"  Migration Complete!")
    print(f"  Total documents migrated: {total}")
    if failed:
        print(f"  ❌ Failed collections: {', '.join(failed)}")
    else:
        print(f"  All collections migrated successfully ✓")
    print("=" * 60)


if __name__ == '__main__':
    run_migration()
