"""
Firebase Configuration Module
Initializes Firebase Admin SDK and provides Firestore database access
"""

import os
import firebase_admin
from firebase_admin import credentials, firestore, auth, storage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Firebase Admin SDK
def initialize_firebase():
    """Initialize Firebase Admin SDK with service account credentials"""

    # Check if already initialized
    if firebase_admin._apps:
        return firestore.client()

    # Create credentials from environment variables
    cred_dict = {
        "type": os.getenv('FIREBASE_TYPE'),
        "project_id": os.getenv('FIREBASE_PROJECT_ID'),
        "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID'),
        "private_key": os.getenv('FIREBASE_PRIVATE_KEY').replace('\\n', '\n') if os.getenv('FIREBASE_PRIVATE_KEY') else None,
        "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
        "client_id": os.getenv('FIREBASE_CLIENT_ID'),
        "auth_uri": os.getenv('FIREBASE_AUTH_URI'),
        "token_uri": os.getenv('FIREBASE_TOKEN_URI'),
        "auth_provider_x509_cert_url": os.getenv('FIREBASE_AUTH_PROVIDER_X509_CERT_URL'),
        "client_x509_cert_url": os.getenv('FIREBASE_CLIENT_X509_CERT_URL'),
    }

    # Initialize Firebase
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred, {
        'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET')
    })

    # Return Firestore client
    return firestore.client()

# Get Firestore database instance
db = initialize_firebase()

# Collections
USERS_COLLECTION = 'users'
PROJECTS_COLLECTION = 'projects'
TASKS_COLLECTION = 'tasks'
PROJECT_MEMBERS_COLLECTION = 'project_members'
LABELS_COLLECTION = 'labels'
COMMENTS_COLLECTION = 'comments'
ACTIVITIES_COLLECTION = 'activities'
EVENTS_COLLECTION = 'events'
CLIENTS_COLLECTION = 'clients'
CLIENT_PROJECT_ACCESS_COLLECTION = 'client_project_access'
NOTIFICATIONS_COLLECTION = 'notifications'
TIME_ENTRIES_COLLECTION = 'time_entries'
REQUIREMENTS_COLLECTION = 'requirements'
ATTENDANCE_COLLECTION = 'attendance'
SETTINGS_COLLECTION = 'settings'
LEAVE_BALANCES_COLLECTION = 'leave_balances'
LEAVE_BALANCE_ARCHIVE_COLLECTION = 'leave_balance_archive'
PETTY_CASH_FUND_COLLECTION = 'petty_cash_fund'
PETTY_CASH_EXPENSES_COLLECTION = 'petty_cash_expenses'
PETTY_CASH_REQUESTS_COLLECTION = 'petty_cash_requests'
PETTY_CASH_CATEGORIES_COLLECTION = 'petty_cash_categories'
COMPANY_PURCHASES_COLLECTION = 'company_purchases'
COMPANY_INVOICES_COLLECTION = 'company_invoices'
HOLIDAYS_COLLECTION = 'holidays'
CREDITS_COLLECTION = 'credits'
TRANSACTIONS_COLLECTION = 'transactions'
ROLES_COLLECTION = 'roles'
REGULARIZATION_COLLECTION = 'regularization_requests'
FACE_EMBEDDINGS_COLLECTION = 'face_embeddings'
