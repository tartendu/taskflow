"""
Holiday Routes Blueprint
Handles holiday CRUD APIs (admin only)
"""

from flask import Blueprint, request, jsonify, session
from flask_login import current_user
from firebase_models import FirebaseHoliday, FirebaseRole, perm_allows_view
from datetime import datetime, timezone
from functools import wraps
from helpers import requires_manage

holiday_bp = Blueprint('holiday', __name__)

ADMIN_SESSION_KEY = 'admin_user_id'


def superadmin_required(f):
    """Allow admin-portal session, superadmin, or users with view/manage on holidays_mgmt.
    Write actions add @requires_manage('holidays_mgmt') on top of this."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get(ADMIN_SESSION_KEY):
            return f(*args, **kwargs)
        if not current_user.is_authenticated:
            return jsonify({'error': 'Access denied'}), 403
        if getattr(current_user, 'is_superadmin', False):
            return f(*args, **kwargs)
        role = getattr(current_user, 'role', 'employee')
        try:
            perms = FirebaseRole.get_permissions_for_role(role)
        except Exception:
            perms = {}
        if perm_allows_view(perms.get('holidays_mgmt')):
            return f(*args, **kwargs)
        return jsonify({'error': 'Access denied'}), 403
    return decorated_function


@holiday_bp.route('/api/admin/holidays', methods=['GET'])
@superadmin_required
def admin_get_holidays():
    """Get all holidays, optionally filtered by year"""
    year = request.args.get('year')
    if year:
        year = int(year)
    holidays = FirebaseHoliday.get_all(year=year)
    result = []
    for h in holidays:
        d = h.get('date')
        result.append({
            'id': h.get('id'),
            'date': d.isoformat() if d else None,
            'name': h.get('name'),
            'type': h.get('type', 'company'),
            'created_at': h.get('created_at').isoformat() if h.get('created_at') else None
        })
    return jsonify(result)


@holiday_bp.route('/api/admin/holidays', methods=['POST'])
@superadmin_required
@requires_manage('holidays_mgmt')
def admin_create_holiday():
    """Create a new holiday"""
    data = request.json or {}
    date_str = data.get('date')
    name = (data.get('name') or '').strip()
    holiday_type = data.get('type', 'company')

    if not date_str or not name:
        return jsonify({'error': 'date and name are required'}), 400
    if holiday_type not in ('national', 'company', 'optional'):
        return jsonify({'error': 'type must be national, company, or optional'}), 400

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    except ValueError:
        return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

    existing = FirebaseHoliday.get_for_date(target_date)
    if existing:
        return jsonify({'error': f'A holiday already exists on this date: {existing.get("name")}'}), 400

    holiday_id = FirebaseHoliday.create(
        date=target_date,
        name=name,
        holiday_type=holiday_type,
        created_by=current_user.id
    )
    return jsonify({'success': True, 'id': holiday_id}), 201


@holiday_bp.route('/api/admin/holidays/<holiday_id>', methods=['PUT'])
@superadmin_required
@requires_manage('holidays_mgmt')
def admin_update_holiday(holiday_id):
    """Update an existing holiday"""
    holiday = FirebaseHoliday.get_by_id(holiday_id)
    if not holiday:
        return jsonify({'error': 'Holiday not found'}), 404

    data = request.json or {}
    update_data = {}

    if 'name' in data:
        name = (data['name'] or '').strip()
        if not name:
            return jsonify({'error': 'name cannot be empty'}), 400
        update_data['name'] = name

    if 'date' in data:
        try:
            new_date = datetime.strptime(data['date'], '%Y-%m-%d').replace(tzinfo=timezone.utc)
            update_data['date'] = new_date.replace(hour=0, minute=0, second=0, microsecond=0)
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400

    if 'type' in data:
        if data['type'] not in ('national', 'company', 'optional'):
            return jsonify({'error': 'type must be national, company, or optional'}), 400
        update_data['type'] = data['type']

    if update_data:
        FirebaseHoliday.update(holiday_id, update_data)

    return jsonify({'success': True})


@holiday_bp.route('/api/admin/holidays/<holiday_id>', methods=['DELETE'])
@superadmin_required
@requires_manage('holidays_mgmt')
def admin_delete_holiday(holiday_id):
    """Delete a holiday"""
    holiday = FirebaseHoliday.get_by_id(holiday_id)
    if not holiday:
        return jsonify({'error': 'Holiday not found'}), 404

    FirebaseHoliday.delete(holiday_id)
    return jsonify({'success': True})
