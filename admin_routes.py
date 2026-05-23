"""
Admin Portal Routes Blueprint
Separate admin authentication and dashboard — completely isolated from user sessions.
All routes under /admin/* require admin session (not Flask-Login).
"""

from flask import Blueprint, request, jsonify, redirect, url_for, render_template, session
from functools import wraps
from firebase_models import FirebaseUser, FirebaseCredits, FirebaseTransaction, FirebaseClient, FirebaseClientProjectAccess, FirebaseProject, FirebaseRole
from werkzeug.security import check_password_hash
from flask_login import login_user, logout_user
from helpers import User
from datetime import datetime, timezone
import uuid

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

ADMIN_SESSION_KEY = 'admin_user_id'
IMPERSONATE_KEY = 'impersonating_as'


# ---- Admin session decorator ----

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get(ADMIN_SESSION_KEY):
            if request.path.startswith('/admin/api/'):
                return jsonify({'error': 'Admin authentication required'}), 401
            return redirect(url_for('admin.admin_login'))
        return f(*args, **kwargs)
    return decorated


def get_current_admin():
    """Get the currently logged-in admin user data from session."""
    admin_id = session.get(ADMIN_SESSION_KEY)
    if not admin_id:
        return None
    return FirebaseUser.get_by_id(admin_id)


# ---- Admin Login / Logout ----

@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    """Separate admin login — only superadmin accounts can access."""
    if session.get(ADMIN_SESSION_KEY):
        return redirect(url_for('admin.admin_dashboard'))

    if request.method == 'POST':
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')

        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password are required'}), 400

        user_data = FirebaseUser.get_by_email(email)

        if not user_data:
            return jsonify({'success': False, 'message': 'Invalid email or password'}), 401

        if not user_data.get('is_superadmin', False):
            return jsonify({'success': False, 'message': 'Access denied. Admin credentials required.'}), 403

        if not check_password_hash(user_data['password_hash'], password):
            return jsonify({'success': False, 'message': 'Invalid email or password'}), 401

        # Set admin session (separate from Flask-Login user session)
        session[ADMIN_SESSION_KEY] = user_data['id']
        session.permanent = True

        return jsonify({'success': True, 'redirect': url_for('admin.admin_dashboard')})

    return render_template('admin/admin_login.html')


@admin_bp.route('/logout')
def admin_logout():
    """Clear admin session and redirect to admin login."""
    session.pop(ADMIN_SESSION_KEY, None)
    return redirect(url_for('admin.admin_login'))


# ---- Admin Dashboard ----

@admin_bp.route('/dashboard')
@admin_required
def admin_dashboard():
    """Main admin dashboard."""
    admin = get_current_admin()
    return render_template('admin/admin_dashboard.html', admin=admin, active_page='dashboard')


@admin_bp.route('/api/dashboard-metrics')
@admin_required
def dashboard_metrics():
    """Return dashboard metrics as JSON for the frontend."""
    admin = get_current_admin()
    admin_id = admin['id']

    all_users = FirebaseUser.get_all()
    # Exclude superadmins from user count
    regular_users = [u for u in all_users if not u.get('is_superadmin', False)]

    active_users = [u for u in regular_users if u.get('subscription_status', 'active') == 'active']
    grace_users = [u for u in regular_users if u.get('subscription_status') == 'grace']
    locked_users = [u for u in regular_users if u.get('subscription_status') == 'locked']

    wallet = FirebaseCredits.get(admin_id)
    recent_txns = FirebaseTransaction.get_by_admin(admin_id, limit=10)

    # Serialise transactions (convert datetimes)
    serialised_txns = []
    for t in recent_txns:
        created_at = t.get('created_at')
        serialised_txns.append({
            **t,
            'created_at': created_at.isoformat() if created_at else None
        })

    return jsonify({
        'total_users': len(regular_users),
        'active_users': len(active_users),
        'grace_users': len(grace_users),
        'locked_users': len(locked_users),
        'credit_balance': wallet.get('balance', 0),
        'total_purchased': wallet.get('total_purchased', 0),
        'total_used': wallet.get('total_used', 0),
        'monthly_revenue': wallet.get('total_used', 0) * FirebaseCredits.PRICE_PER_CREDIT,
        'recent_transactions': serialised_txns
    })


# ---- Billing & Credits ----

CREDIT_PACKS = [
    {'id': 'pack_5',  'credits': 5,  'amount': 2495,  'label': 'Starter',    'popular': False},
    {'id': 'pack_10', 'credits': 10, 'amount': 4990,  'label': 'Business',   'popular': True},
    {'id': 'pack_25', 'credits': 25, 'amount': 12475, 'label': 'Growth',     'popular': False},
    {'id': 'pack_50', 'credits': 50, 'amount': 24950, 'label': 'Enterprise', 'popular': False},
]


@admin_bp.route('/billing')
@admin_required
def admin_billing():
    """Billing & credits page."""
    admin = get_current_admin()
    wallet = FirebaseCredits.get(admin['id'])
    all_txns = FirebaseTransaction.get_by_admin(admin['id'], limit=50)

    # Serialise datetimes
    for t in all_txns:
        if t.get('created_at'):
            t['created_at'] = t['created_at'].isoformat()

    return render_template(
        'admin/admin_billing.html',
        admin=admin,
        wallet=wallet,
        transactions=all_txns,
        packs=CREDIT_PACKS,
        price_per_credit=FirebaseCredits.PRICE_PER_CREDIT,
        active_page='billing'
    )


@admin_bp.route('/billing/checkout', methods=['POST'])
@admin_required
def billing_checkout():
    """Store selected pack in session and redirect to payment page."""
    data = request.get_json()
    pack_id = data.get('pack_id')

    pack = next((p for p in CREDIT_PACKS if p['id'] == pack_id), None)
    if not pack:
        return jsonify({'success': False, 'message': 'Invalid pack selected'}), 400

    # Store order in session
    session['pending_order'] = {
        'pack_id': pack['id'],
        'credits': pack['credits'],
        'amount': pack['amount'],
        'label': pack['label']
    }

    return jsonify({'success': True, 'redirect': url_for('admin.billing_payment')})


@admin_bp.route('/billing/payment', methods=['GET'])
@admin_required
def billing_payment():
    """Fake payment gateway page."""
    order = session.get('pending_order')
    if not order:
        return redirect(url_for('admin.admin_billing'))

    admin = get_current_admin()
    return render_template('admin/admin_payment.html', admin=admin, order=order)


@admin_bp.route('/api/billing/process-payment', methods=['POST'])
@admin_required
def process_payment():
    """
    Simulate payment processing.
    Validates fake card details, adds credits, records transaction.
    """
    admin = get_current_admin()
    order = session.get('pending_order')

    if not order:
        return jsonify({'success': False, 'message': 'No pending order found'}), 400

    data = request.get_json()
    card_number = data.get('card_number', '').replace(' ', '')
    expiry = data.get('expiry', '')
    cvv = data.get('cvv', '')
    name = data.get('name', '').strip()

    # Basic fake validation
    if len(card_number) < 16:
        return jsonify({'success': False, 'message': 'Invalid card number'}), 400
    if not expiry or len(expiry) < 5:
        return jsonify({'success': False, 'message': 'Invalid expiry date'}), 400
    if len(cvv) < 3:
        return jsonify({'success': False, 'message': 'Invalid CVV'}), 400
    if not name:
        return jsonify({'success': False, 'message': 'Cardholder name is required'}), 400

    # Generate fake payment ID (Razorpay-style)
    payment_id = f"pay_{uuid.uuid4().hex[:16].upper()}"

    credits = order['credits']
    amount = order['amount']
    admin_id = admin['id']

    # Add credits to wallet
    FirebaseCredits.add(admin_id, credits)

    # Record transaction
    FirebaseTransaction.create(
        admin_id=admin_id,
        transaction_type='purchase',
        credits=credits,
        amount_inr=amount,
        description=f"{order['label']} Pack — {credits} credits purchased",
        payment_id=payment_id
    )

    # Clear pending order from session
    session.pop('pending_order', None)

    # Store success info for the success page
    session['last_payment'] = {
        'payment_id': payment_id,
        'credits': credits,
        'amount': amount,
        'label': order['label']
    }

    return jsonify({'success': True, 'redirect': url_for('admin.billing_success')})


# ---- User Management ----

@admin_bp.route('/users')
@admin_required
def admin_users():
    """User management page."""
    admin = get_current_admin()
    wallet = FirebaseCredits.get(admin['id'])
    all_users = FirebaseUser.get_all()
    regular_users = [u for u in all_users if not u.get('is_superadmin', False)]

    # Serialise datetimes for template
    for u in regular_users:
        for field in ('created_at', 'subscription_start', 'subscription_expires', 'grace_period_ends'):
            val = u.get(field)
            if val and hasattr(val, 'isoformat'):
                u[field] = val.isoformat()

    return render_template('admin/admin_users.html', admin=admin, users=regular_users, wallet=wallet, active_page='users')


@admin_bp.route('/api/users/create', methods=['POST'])
@admin_required
def create_user():
    """Create a new user account, deducting 1 credit."""
    admin = get_current_admin()
    admin_id = admin['id']
    data = request.get_json()

    full_name = data.get('full_name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()
    department = data.get('department', '').strip()

    if not full_name or not email or not password:
        return jsonify({'success': False, 'message': 'Full name, email, and password are required'}), 400

    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400

    if FirebaseUser.get_by_email(email):
        return jsonify({'success': False, 'message': 'Email is already registered'}), 400

    # Check credits before creating
    wallet = FirebaseCredits.get(admin_id)
    if wallet.get('balance', 0) < 1:
        return jsonify({'success': False, 'message': 'Insufficient credits. Please purchase more credits to create user accounts.', 'no_credits': True}), 402

    # Generate username from email
    username = email.split('@')[0]
    base_username = username
    counter = 1
    while FirebaseUser.get_by_username(username):
        username = f"{base_username}{counter}"
        counter += 1

    # Create user with subscription fields
    user_id = FirebaseUser.create(
        username=username,
        email=email,
        password=password,
        full_name=full_name,
        created_by_admin=True,
        department=department or None
    )

    # Deduct 1 credit
    FirebaseCredits.deduct(admin_id)

    # Record deduction transaction
    FirebaseTransaction.create(
        admin_id=admin_id,
        transaction_type='deduction',
        credits=1,
        amount_inr=0,
        description=f"User account created: {full_name} ({email})",
        user_id=user_id
    )

    return jsonify({'success': True, 'message': f'User account created for {full_name}', 'user_id': user_id})


@admin_bp.route('/api/users/<user_id>/toggle-lock', methods=['POST'])
@admin_required
def toggle_user_lock(user_id):
    """Lock or unlock a user account."""
    user = FirebaseUser.get_by_id(user_id)
    if not user or user.get('is_superadmin'):
        return jsonify({'success': False, 'message': 'User not found'}), 404

    current_status = user.get('subscription_status', 'active')
    new_status = 'active' if current_status == 'locked' else 'locked'
    FirebaseUser.update(user_id, {'subscription_status': new_status})

    return jsonify({'success': True, 'subscription_status': new_status})


@admin_bp.route('/api/users/<user_id>/role', methods=['PUT'])
@admin_required
def update_user_role(user_id):
    """Update a user's role (any custom or built-in role name)."""
    user = FirebaseUser.get_by_id(user_id)
    if not user or user.get('is_superadmin'):
        return jsonify({'success': False, 'message': 'User not found'}), 404
    data = request.get_json()
    role = (data.get('role') or 'employee').strip()
    if not role:
        return jsonify({'success': False, 'message': 'Role name is required'}), 400
    update = {'role': role}
    # Keep is_accountant flag in sync for backward compat
    update['is_accountant'] = role in ('accountant', 'superadmin')
    FirebaseUser.update(user_id, update)
    return jsonify({'success': True, 'role': role})


@admin_bp.route('/api/users/<user_id>/reset-password', methods=['POST'])
@admin_required
def reset_user_password(user_id):
    """Set a new temporary password for a user and force change on next login."""
    from firebase_models import FirebaseUser as FU
    from helpers import generate_password
    from werkzeug.security import generate_password_hash
    user = FU.get_by_id(user_id)
    if not user or user.get('is_superadmin'):
        return jsonify({'success': False, 'message': 'User not found'}), 404
    data = request.get_json() or {}
    new_password = data.get('password', '').strip() or generate_password(10)
    FU.update(user_id, {
        'password_hash': generate_password_hash(new_password),
        'must_change_password': True,
    })
    return jsonify({'success': True, 'new_password': new_password})


@admin_bp.route('/api/clients/<client_id>/reset-password', methods=['POST'])
@admin_required
def reset_client_password(client_id):
    """Set a new temporary password for a client."""
    from firebase_config import db, CLIENTS_COLLECTION
    from helpers import generate_password
    from werkzeug.security import generate_password_hash
    doc_ref = db.collection(CLIENTS_COLLECTION).document(client_id)
    if not doc_ref.get().exists:
        return jsonify({'success': False, 'message': 'Client not found'}), 404
    data = request.get_json() or {}
    new_password = data.get('password', '').strip() or generate_password(10)
    doc_ref.update({'password_hash': generate_password_hash(new_password)})
    return jsonify({'success': True, 'new_password': new_password})


@admin_bp.route('/api/users/<user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """Delete a user and refund 1 credit."""
    admin = get_current_admin()
    user = FirebaseUser.get_by_id(user_id)
    if not user or user.get('is_superadmin'):
        return jsonify({'success': False, 'message': 'User not found'}), 404

    FirebaseUser.update(user_id, {'is_active': False, 'subscription_status': 'locked', 'deleted': True})

    # Refund 1 credit
    FirebaseCredits.refund(admin['id'])
    FirebaseTransaction.create(
        admin_id=admin['id'],
        transaction_type='refund',
        credits=1,
        amount_inr=0,
        description=f"User deleted: {user.get('full_name', user.get('email'))}",
        user_id=user_id
    )

    return jsonify({'success': True})


# ---- HR & Operations Pages ----

@admin_bp.route('/attendance')
@admin_required
def admin_attendance():
    admin = get_current_admin()
    return render_template('admin/admin_attendance.html', admin=admin, active_page='attendance')


@admin_bp.route('/leave')
@admin_required
def admin_leave():
    admin = get_current_admin()
    return render_template('admin/admin_leave.html', admin=admin, active_page='leave')


@admin_bp.route('/leave-summary')
@admin_required
def admin_leave_summary():
    admin = get_current_admin()
    return render_template('admin/admin_leave_summary.html', admin=admin, active_page='leave-summary')


@admin_bp.route('/monthly-report')
@admin_required
def admin_monthly_report():
    admin = get_current_admin()
    return render_template('admin/admin_monthly_report.html', admin=admin, active_page='report')


@admin_bp.route('/projects')
@admin_required
def admin_projects():
    admin = get_current_admin()
    return render_template('admin/admin_projects.html', admin=admin, active_page='projects')


@admin_bp.route('/holidays')
@admin_required
def admin_holidays():
    admin = get_current_admin()
    return render_template('admin/admin_holidays.html', admin=admin, active_page='holidays')


@admin_bp.route('/settings')
@admin_required
def admin_settings():
    admin = get_current_admin()
    return render_template('admin/admin_settings.html', admin=admin, active_page='settings')


@admin_bp.route('/api/change-password', methods=['PUT'])
@admin_required
def admin_change_own_password():
    """Allow the logged-in admin to change their own password."""
    admin = get_current_admin()
    if not admin:
        return jsonify({'success': False, 'message': 'Session expired. Please log in again.'}), 401

    data = request.get_json() or {}
    current_password = data.get('current_password') or ''
    new_password = data.get('new_password') or ''

    if not current_password or not new_password:
        return jsonify({'success': False, 'message': 'Both current and new password are required'}), 400

    if not check_password_hash(admin.get('password_hash', ''), current_password):
        return jsonify({'success': False, 'message': 'Current password is incorrect'}), 400

    if len(new_password) < 6:
        return jsonify({'success': False, 'message': 'New password must be at least 6 characters'}), 400

    if new_password == current_password:
        return jsonify({'success': False, 'message': 'New password must be different from the current password'}), 400

    FirebaseUser.set_password(admin['id'], new_password)
    return jsonify({'success': True, 'message': 'Password changed successfully'})


@admin_bp.route('/petty-cash')
@admin_required
def admin_petty_cash():
    admin = get_current_admin()
    return render_template('admin/admin_petty_cash.html', admin=admin, active_page='petty-cash')


@admin_bp.route('/purchases')
@admin_required
def admin_purchases():
    admin = get_current_admin()
    return render_template('admin/admin_purchases.html', admin=admin, active_page='purchases')


@admin_bp.route('/invoices')
@admin_required
def admin_invoices():
    admin = get_current_admin()
    return render_template('admin/admin_invoices.html', admin=admin, active_page='invoices')


@admin_bp.route('/clients')
@admin_required
def admin_clients():
    admin = get_current_admin()
    return render_template('admin/admin_clients.html', admin=admin, active_page='clients')


@admin_bp.route('/api/clients/<client_id>/projects', methods=['GET'])
@admin_required
def admin_get_client_projects(client_id):
    """Get all projects + which ones this client has access to."""
    all_projects = FirebaseProject.get_all()
    access_records = FirebaseClientProjectAccess.get_by_client(client_id)
    granted_project_ids = {a['project_id']: a['id'] for a in access_records}
    result = []
    for p in all_projects:
        result.append({
            'id': p['id'],
            'name': p.get('name', '—'),
            'has_access': p['id'] in granted_project_ids,
            'access_id': granted_project_ids.get(p['id']),
        })
    result.sort(key=lambda x: x['name'].lower())
    return jsonify({'projects': result})


@admin_bp.route('/api/clients/<client_id>/projects/<project_id>', methods=['POST'])
@admin_required
def admin_grant_client_project(client_id, project_id):
    """Grant a client access to a project."""
    existing = FirebaseClientProjectAccess.get_by_client_and_project(client_id, project_id)
    if existing:
        return jsonify({'success': True, 'access_id': existing['id']})
    admin = get_current_admin()
    access_id = FirebaseClientProjectAccess.create(client_id, project_id, granted_by=admin['id'])
    return jsonify({'success': True, 'access_id': access_id})


@admin_bp.route('/api/clients/<client_id>/projects/<project_id>', methods=['DELETE'])
@admin_required
def admin_revoke_client_project(client_id, project_id):
    """Revoke a client's access to a project."""
    existing = FirebaseClientProjectAccess.get_by_client_and_project(client_id, project_id)
    if existing:
        FirebaseClientProjectAccess.delete(existing['id'])
    return jsonify({'success': True})


@admin_bp.route('/api/clients/<client_id>/toggle-active', methods=['POST'])
@admin_required
def admin_toggle_client(client_id):
    from firebase_config import db, CLIENTS_COLLECTION
    doc_ref = db.collection(CLIENTS_COLLECTION).document(client_id)
    doc = doc_ref.get()
    if not doc.exists:
        return jsonify({'success': False, 'message': 'Client not found'}), 404
    current = doc.to_dict().get('is_active', True)
    doc_ref.update({'is_active': not current})
    return jsonify({'success': True, 'is_active': not current})


@admin_bp.route('/api/clients/<client_id>', methods=['DELETE'])
@admin_required
def admin_delete_client(client_id):
    from firebase_config import db, CLIENTS_COLLECTION
    doc_ref = db.collection(CLIENTS_COLLECTION).document(client_id)
    if not doc_ref.get().exists:
        return jsonify({'success': False, 'message': 'Client not found'}), 404
    doc_ref.delete()
    return jsonify({'success': True})


@admin_bp.route('/api/clients')
@admin_required
def admin_get_clients():
    """Get ALL clients across all users with creator and project info."""
    from firebase_config import db, CLIENTS_COLLECTION
    all_docs = db.collection(CLIENTS_COLLECTION).stream()
    all_clients = [{'id': d.id, **d.to_dict()} for d in all_docs]

    user_map = {u['id']: u for u in FirebaseUser.get_all()}
    project_map = {p['id']: p for p in FirebaseProject.get_all()}

    result = []
    for c in all_clients:
        c.pop('password_hash', None)
        creator_id = c.get('created_by')
        creator = user_map.get(creator_id, {})
        access_records = FirebaseClientProjectAccess.get_by_client(c['id'])
        projects = []
        for acc in access_records:
            proj = project_map.get(acc['project_id'])
            if proj:
                projects.append({'id': proj['id'], 'name': proj['name'], 'access_id': acc['id']})
        created_at = c.get('created_at')
        last_login = c.get('last_login')
        result.append({
            'id': c['id'],
            'name': c.get('name', '—'),
            'email': c.get('email', '—'),
            'is_active': c.get('is_active', True),
            'created_by_id': creator_id,
            'created_by_name': creator.get('full_name') or creator.get('username') or '—',
            'created_by_email': creator.get('email', ''),
            'created_at': created_at.isoformat() if created_at and hasattr(created_at, 'isoformat') else (str(created_at)[:10] if created_at else None),
            'last_login': last_login.isoformat() if last_login and hasattr(last_login, 'isoformat') else (str(last_login)[:10] if last_login else None),
            'projects': projects,
            'project_count': len(projects),
        })

    result.sort(key=lambda x: x.get('created_at') or '', reverse=True)
    return jsonify({'clients': result})


@admin_bp.route('/impersonate/<user_id>')
@admin_required
def impersonate_user(user_id):
    """Log in as the selected user so admin can see exactly what they see."""
    user_data = FirebaseUser.get_by_id(user_id)
    if not user_data or user_data.get('is_superadmin'):
        return redirect(url_for('admin.admin_users'))
    # Store admin id so we can return to admin panel later
    session[IMPERSONATE_KEY] = session[ADMIN_SESSION_KEY]
    login_user(User(user_data))
    return redirect(url_for('dashboard.home_dashboard'))


@admin_bp.route('/stop-impersonating')
def stop_impersonating():
    """Exit impersonation and return to admin panel."""
    admin_id = session.pop(IMPERSONATE_KEY, None)
    logout_user()
    if admin_id:
        session[ADMIN_SESSION_KEY] = admin_id
        return redirect(url_for('admin.admin_users'))
    return redirect(url_for('admin.admin_login'))


# ---- Role Management ----

@admin_bp.route('/roles')
@admin_required
def admin_roles():
    admin = get_current_admin()
    return render_template('admin/admin_roles.html', admin=admin, active_page='roles')


@admin_bp.route('/api/roles', methods=['GET'])
@admin_required
def get_roles():
    roles = FirebaseRole.get_all()
    for r in roles:
        for f in ('created_at', 'updated_at'):
            val = r.get(f)
            if val and hasattr(val, 'isoformat'):
                r[f] = val.isoformat()
    return jsonify({'roles': roles})


@admin_bp.route('/api/roles', methods=['POST'])
@admin_required
def create_role():
    admin = get_current_admin()
    data = request.get_json()
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'message': 'Role name is required'}), 400
    if FirebaseRole.get_by_name(name):
        return jsonify({'success': False, 'message': 'A role with this name already exists'}), 400
    permissions = data.get('permissions', {})
    role_id = FirebaseRole.create(name, permissions, created_by=admin['id'])
    return jsonify({'success': True, 'id': role_id})


@admin_bp.route('/api/roles/<role_id>', methods=['PUT'])
@admin_required
def update_role(role_id):
    data = request.get_json()
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'message': 'Role name is required'}), 400
    existing = FirebaseRole.get_by_name(name)
    if existing and existing['id'] != role_id:
        return jsonify({'success': False, 'message': 'A role with this name already exists'}), 400
    permissions = data.get('permissions', {})
    FirebaseRole.update(role_id, name, permissions)
    return jsonify({'success': True})


@admin_bp.route('/api/roles/<role_id>', methods=['DELETE'])
@admin_required
def delete_role(role_id):
    FirebaseRole.delete(role_id)
    return jsonify({'success': True})


@admin_bp.route('/billing/success')
@admin_required
def billing_success():
    """Payment success page."""
    payment = session.pop('last_payment', None)
    if not payment:
        return redirect(url_for('admin.admin_billing'))

    admin = get_current_admin()
    wallet = FirebaseCredits.get(admin['id'])
    return render_template('admin/admin_payment_success.html', admin=admin, payment=payment, wallet=wallet)
