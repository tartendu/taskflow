"""
TaskFlow Application with Firebase Firestore
Main application file — setup + blueprint registration only
"""

from flask import Flask, redirect, url_for, request, jsonify, session
from flask_login import LoginManager, current_user
from firebase_models import FirebaseUser, FirebaseClient, FirebaseRole
from helpers import User, ClientUser
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-this-in-production')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)
app.config['REMEMBER_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# ---- Register Blueprints ----

from auth_routes import auth_bp
from admin_routes import admin_bp
from dashboard_routes import dashboard_bp
from project_routes import project_bp
from client_routes import client_bp
from calendar_routes import calendar_bp
from notification_routes import notification_bp
from holiday_routes import holiday_bp
from requirements_routes import requirements_bp
from attendance_routes import attendance_bp
from superadmin_routes import superadmin_bp
from petty_cash_routes import petty_cash_bp
from purchases_routes import purchases_bp
from invoices_routes import invoices_bp
from face_routes import face_bp

app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(project_bp)
app.register_blueprint(client_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(notification_bp)
app.register_blueprint(holiday_bp)
app.register_blueprint(requirements_bp)
app.register_blueprint(attendance_bp)
app.register_blueprint(superadmin_bp)
app.register_blueprint(petty_cash_bp)
app.register_blueprint(purchases_bp)
app.register_blueprint(invoices_bp)
app.register_blueprint(face_bp)


# ---- Cron endpoint ----

@app.route('/api/cron/auto-checkout', methods=['GET', 'POST'])
def cron_auto_checkout():
    """
    Auto-checkout endpoint — called by Vercel Cron daily at 00:05 UTC.
    Protected by a secret token set in CRON_SECRET env variable.
    """
    from firebase_models import FirebaseAttendance, FirebaseSettings
    from firebase_config import db, ATTENDANCE_COLLECTION

    cron_secret = os.getenv('CRON_SECRET', '')
    auth_header = request.headers.get('Authorization', '')
    if cron_secret and auth_header != f'Bearer {cron_secret}':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        settings = FirebaseSettings.get_office_settings()
        office_end = settings.get('office_end', '18:00')
        end_hour, end_min = map(int, office_end.split(':'))

        now_utc = datetime.now(timezone.utc)
        yesterday = (now_utc - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        checkout_time = yesterday.replace(hour=end_hour, minute=end_min, second=0)

        records = FirebaseAttendance.get_unchecked_out_for_date(yesterday)
        half_day_threshold = settings.get('half_day_threshold', 4)
        count = 0
        for record in records:
            check_in = record.get('check_in_time')
            work_hours = None
            if check_in:
                delta = checkout_time - check_in
                work_hours = round(max(delta.total_seconds(), 0) / 3600, 2)
            status = 'half-day' if (work_hours is not None and work_hours < half_day_threshold) else 'present'
            db.collection(ATTENDANCE_COLLECTION).document(record['id']).update({
                'check_out_time': checkout_time,
                'work_hours': work_hours,
                'status': status,
                'auto_checkout': True
            })
            count += 1

        return jsonify({'ok': True, 'date': str(yesterday.date()), 'checked_out': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---- Session & Auth setup ----

@app.before_request
def make_session_permanent():
    session.permanent = True


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'


@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Session expired. Please log in again.', 'auth_required': True}), 401
    return redirect(url_for('auth.login'))


@login_manager.user_loader
def load_user(user_id):
    if user_id and user_id.startswith('client_'):
        client_id = user_id[7:]
        client_data = FirebaseClient.get_by_id(client_id)
        if client_data and client_data.get('is_active', True):
            return ClientUser(client_data)
        return None

    user_data = FirebaseUser.get_by_id(user_id)
    if user_data:
        return User(user_data)
    return None


@app.context_processor
def inject_superadmin_status():
    from firebase_models import perm_allows_view, perm_allows_manage, normalize_permissions_dict
    if current_user.is_authenticated and hasattr(current_user, 'is_superadmin'):
        role = getattr(current_user, 'role', 'employee')
        try:
            perms = FirebaseRole.get_permissions_for_role(role)
        except Exception:
            perms = {}
        perms = normalize_permissions_dict(perms)
        is_superadmin = current_user.is_superadmin

        def can_view(key):
            return is_superadmin or perm_allows_view(perms.get(key))

        def can_manage(key):
            return is_superadmin or perm_allows_manage(perms.get(key))

        return {
            'is_superadmin': is_superadmin,
            'is_accountant': getattr(current_user, 'is_accountant', False),
            'user_role': role,
            # View-level access (show the page / nav link)
            'can_view_attendance':     can_view('attendance_mgmt'),
            'can_view_petty_cash':     can_view('petty_cash_mgmt'),
            'can_view_leave':          can_view('leave_requests'),
            'can_view_leave_summary':  can_view('leave_summary'),
            'can_view_monthly_report': can_view('monthly_report'),
            'can_view_projects':       can_view('projects_mgmt'),
            'can_view_holidays':       can_view('holidays_mgmt'),
            'can_view_purchases':      can_view('purchases_mgmt'),
            'can_view_invoices':       can_view('invoices_mgmt'),
            'can_view_settings':       can_view('settings'),
            # Manage-level access (write actions: create / edit / delete / approve)
            'can_manage_attendance':   can_manage('attendance_mgmt'),
            'can_manage_petty_cash':   can_manage('petty_cash_mgmt'),
            'can_manage_leave':        can_manage('leave_requests'),
            'can_manage_leave_summary':can_manage('leave_summary'),
            'can_manage_monthly_report':can_manage('monthly_report'),
            'can_manage_projects':     can_manage('projects_mgmt'),
            'can_manage_holidays':     can_manage('holidays_mgmt'),
            'can_manage_purchases':    can_manage('purchases_mgmt'),
            'can_manage_invoices':     can_manage('invoices_mgmt'),
            'can_manage_settings':     can_manage('settings'),
            'role_permissions':        perms,
        }
    return {
        'is_superadmin': False, 'is_accountant': False,
        'user_role': 'employee',
        'can_view_attendance': False, 'can_view_petty_cash': False,
        'can_view_leave': False, 'can_view_leave_summary': False,
        'can_view_monthly_report': False, 'can_view_projects': False,
        'can_view_holidays': False, 'can_view_purchases': False, 'can_view_invoices': False, 'can_view_settings': False,
        'can_manage_attendance': False, 'can_manage_petty_cash': False,
        'can_manage_leave': False, 'can_manage_leave_summary': False,
        'can_manage_monthly_report': False, 'can_manage_projects': False,
        'can_manage_holidays': False, 'can_manage_purchases': False, 'can_manage_invoices': False, 'can_manage_settings': False,
        'role_permissions': {},
    }


def bootstrap_superadmin():
    admin_email = os.getenv('SUPER_ADMIN_EMAIL')
    if admin_email:
        user = FirebaseUser.get_by_email(admin_email)
        if user and not user.get('is_superadmin', False):
            FirebaseUser.update(user['id'], {'is_superadmin': True})
            print(f"[BOOTSTRAP] Super admin set for: {admin_email}")


bootstrap_superadmin()


if __name__ == '__main__':
    app.run(debug=True, port=5083)
