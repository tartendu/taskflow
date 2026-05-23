"""
Super Admin Routes Blueprint
Handles all super admin panel page routes and API endpoints
"""

import csv
import io
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, Response, session
from flask_login import current_user
from firebase_models import (
    FirebaseUser, FirebaseProject, FirebaseTask, FirebaseProjectMember,
    FirebaseAttendance, FirebaseClient, FirebaseSettings, FirebaseLeaveBalance,
    FirebaseHoliday, FirebaseRegularization
)
from datetime import datetime, timezone, timedelta
from functools import wraps
from helpers import requires_manage

superadmin_bp = Blueprint('superadmin', __name__)

ADMIN_SESSION_KEY = 'admin_user_id'


def superadmin_required(f):
    """Decorator that checks if the current user is a superadmin or has settings permission.
    Accepts both Flask-Login session (legacy panel) and admin portal session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Accept admin portal session
        if session.get(ADMIN_SESSION_KEY):
            return f(*args, **kwargs)
        # Fall back to Flask-Login check
        if not current_user.is_authenticated:
            return jsonify({'error': 'Access denied'}), 403
        if getattr(current_user, 'is_superadmin', False):
            return f(*args, **kwargs)
        # Also allow users whose role has any view/manage permission on an admin feature
        from firebase_models import FirebaseRole, perm_allows_view
        role = getattr(current_user, 'role', 'employee')
        try:
            perms = FirebaseRole.get_permissions_for_role(role)
        except Exception:
            perms = {}
        if any(perm_allows_view(perms.get(p)) for p in ['attendance_mgmt', 'petty_cash_mgmt', 'leave_requests', 'leave_summary', 'monthly_report', 'settings']):
            return f(*args, **kwargs)
        return jsonify({'error': 'Access denied'}), 403
    return decorated_function


# ---- Helper ----

def _format_hours(hours):
    """Format decimal hours into human-readable string"""
    if not hours or hours <= 0:
        return '0h 0m'
    h = int(hours)
    m = int((hours - h) * 60)
    if h > 0:
        return f'{h}h {m}m'
    return f'{m}m'


# ---- Page Route ----

@superadmin_bp.route('/admin')
@superadmin_required
def admin_panel():
    """Show super admin panel"""
    return render_template('superadmin.html')


# ---- API Routes ----

@superadmin_bp.route('/api/admin/overview', methods=['GET'])
@superadmin_required
def admin_overview():
    """Get system-wide overview stats"""
    users = FirebaseUser.get_all()
    projects = FirebaseProject.get_all()
    tasks = FirebaseTask.get_all()

    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.get('status') == 'done'])
    in_progress_tasks = len([t for t in tasks if t.get('status') == 'in_progress'])

    today_attendance = FirebaseAttendance.get_all_for_date(datetime.now(timezone.utc))
    checked_in_count = len(today_attendance)

    return jsonify({
        'total_users': len(users),
        'total_projects': len(projects),
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'in_progress_tasks': in_progress_tasks,
        'checked_in_today': checked_in_count,
        'total_team_members': len(users)
    })


@superadmin_bp.route('/api/admin/users', methods=['GET'])
@superadmin_required
def admin_get_users():
    """Get all users with details"""
    users = FirebaseUser.get_all()
    result = []
    for user in users:
        user.pop('password_hash', None)
        owned = FirebaseProject.get_by_owner(user['id'])
        memberships = FirebaseProjectMember.get_by_user(user['id'])
        user['project_count'] = len(owned) + len(memberships)
        user['is_superadmin'] = user.get('is_superadmin', False)
        user['is_accountant'] = user.get('is_accountant', False)
        created = user.get('created_at')
        user['created_at'] = created.isoformat() if created else None
        result.append(user)
    return jsonify(result)


@superadmin_bp.route('/api/admin/users/<user_id>/toggle-admin', methods=['PUT'])
@superadmin_required
@requires_manage('settings')
def admin_toggle_superadmin(user_id):
    """Toggle superadmin status for a user"""
    if user_id == current_user.id:
        return jsonify({'error': 'Cannot modify your own admin status'}), 400

    user_data = FirebaseUser.get_by_id(user_id)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404

    new_status = not user_data.get('is_superadmin', False)
    FirebaseUser.set_superadmin(user_id, new_status)
    return jsonify({'success': True, 'is_superadmin': new_status})


@superadmin_bp.route('/api/admin/users/<user_id>/toggle-accountant', methods=['PUT'])
@superadmin_required
@requires_manage('settings')
def admin_toggle_accountant(user_id):
    """Toggle accountant role for a user"""
    user_data = FirebaseUser.get_by_id(user_id)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404
    new_status = not user_data.get('is_accountant', False)
    FirebaseUser.set_accountant(user_id, new_status)
    return jsonify({'success': True, 'is_accountant': new_status})


@superadmin_bp.route('/api/admin/users/<user_id>/reset-password', methods=['POST'])
@superadmin_required
@requires_manage('settings')
def admin_reset_user_password(user_id):
    """Reset a user's password"""
    user_data = FirebaseUser.get_by_id(user_id)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404

    data = request.json or {}
    new_password = data.get('new_password', '')
    if len(new_password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    FirebaseUser.set_password(user_id, new_password)
    return jsonify({'success': True, 'message': 'Password reset successfully'})


@superadmin_bp.route('/api/admin/attendance', methods=['GET'])
@superadmin_required
def admin_get_attendance():
    """Get attendance for all users for a given date or month."""
    year_str = request.args.get('year')
    month_str = request.args.get('month')
    date_str = request.args.get('date')
    user_id_filter = request.args.get('user_id')

    all_users = FirebaseUser.get_all()
    user_map = {u['id']: u for u in all_users}

    def _fmt_record(record):
        uid = record.get('user_id')
        user = user_map.get(uid, {})
        check_in = record.get('check_in_time')
        check_out = record.get('check_out_time')
        work_hours = record.get('work_hours')
        if check_in and not check_out:
            delta = datetime.now(timezone.utc) - check_in
            work_hours = round(delta.total_seconds() / 3600, 2)
        device_id = record.get('device_id')
        different_device = False
        if device_id:
            registered = user.get('registered_device_id')
            if registered and registered != device_id:
                different_device = True
        # include date field for month view
        rec_date = record.get('date')
        if not rec_date and check_in:
            rec_date = check_in.strftime('%Y-%m-%d')
        return {
            'id': record.get('id'),
            'user_id': uid,
            'user_name': user.get('full_name') or user.get('username', 'Unknown'),
            'email': user.get('email', ''),
            'date': rec_date,
            'check_in_time': check_in.isoformat() if check_in else None,
            'check_out_time': check_out.isoformat() if check_out else None,
            'work_hours': work_hours,
            'work_hours_formatted': _format_hours(work_hours),
            'location_address': record.get('location_address'),
            'ip_address': record.get('ip_address'),
            'status': record.get('status', 'present'),
            'leave_type': record.get('leave_type'),
            'leave_duration': record.get('leave_duration', 'full'),
            'approval_status': record.get('approval_status'),
            'outside_geofence': record.get('outside_geofence', False),
            'manual_entry': record.get('manual_entry', False),
            'device_info': record.get('device_info'),
            'different_device': different_device,
            'late_arrival': record.get('late_arrival', False),
            'late_by_minutes': record.get('late_by_minutes'),
            'early_departure': record.get('early_departure', False),
            'early_by_minutes': record.get('early_by_minutes'),
        }

    # --- Month-based query ---
    if year_str and month_str:
        import calendar
        year, month = int(year_str), int(month_str)
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        last_day = calendar.monthrange(year, month)[1]
        end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
        records = FirebaseAttendance.get_all_for_date_range(start, end)
        attendance_data = [_fmt_record(r) for r in records]
        if user_id_filter:
            attendance_data = [r for r in attendance_data if r['user_id'] == user_id_filter]
        # Sort by date desc
        attendance_data.sort(key=lambda r: r.get('date') or '', reverse=True)
        return jsonify({'attendance': attendance_data})

    # --- Single-date query (legacy) ---
    if date_str:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    else:
        target_date = datetime.now(timezone.utc)

    records = FirebaseAttendance.get_all_for_date(target_date)
    holiday_info = FirebaseHoliday.get_for_date(target_date)

    attendance_data = []
    users_with_records = set()

    for record in records:
        users_with_records.add(record.get('user_id'))
        attendance_data.append(_fmt_record(record))

    absent_status = 'holiday' if holiday_info else 'absent'
    for user in all_users:
        if user['id'] not in users_with_records:
            attendance_data.append({
                'user_id': user['id'],
                'user_name': user.get('full_name') or user.get('username', 'Unknown'),
                'email': user.get('email', ''),
                'date': target_date.strftime('%Y-%m-%d'),
                'check_in_time': None,
                'check_out_time': None,
                'work_hours': None,
                'work_hours_formatted': None,
                'location_address': None,
                'ip_address': None,
                'status': absent_status,
                'leave_type': None,
                'device_info': None,
                'different_device': False,
                'holiday_name': holiday_info.get('name') if holiday_info else None
            })

    return jsonify({'attendance': attendance_data})


@superadmin_bp.route('/api/admin/settings/office', methods=['GET'])
@superadmin_required
def admin_get_office_settings():
    """Get office timing settings"""
    settings = FirebaseSettings.get_office_settings()
    if settings.get('updated_at'):
        settings['updated_at'] = settings['updated_at'].isoformat()
    return jsonify(settings)


@superadmin_bp.route('/api/admin/settings/office', methods=['PUT'])
@superadmin_required
@requires_manage('settings')
def admin_update_office_settings():
    """Update office timing settings"""
    data = request.json or {}
    allowed_fields = ['office_start', 'office_end', 'expected_hours',
                      'half_day_threshold', 'late_threshold_minutes',
                      'geofence_enabled', 'office_latitude', 'office_longitude',
                      'geofence_radius_meters']
    update_data = {k: data[k] for k in allowed_fields if k in data}

    if not update_data:
        return jsonify({'error': 'No valid fields provided'}), 400

    for field in ['office_start', 'office_end']:
        if field in update_data:
            try:
                datetime.strptime(update_data[field], '%H:%M')
            except ValueError:
                return jsonify({'error': f'Invalid time format for {field}, use HH:MM'}), 400

    settings = FirebaseSettings.update_office_settings(update_data)
    settings['updated_at'] = settings['updated_at'].isoformat() if settings.get('updated_at') else None
    return jsonify(settings)


@superadmin_bp.route('/api/admin/settings/leave', methods=['GET'])
@superadmin_required
def admin_get_leave_settings():
    """Get leave quota settings"""
    settings = FirebaseSettings.get_leave_settings()
    if settings.get('updated_at'):
        settings['updated_at'] = settings['updated_at'].isoformat()
    return jsonify(settings)


@superadmin_bp.route('/api/admin/settings/leave', methods=['PUT'])
@superadmin_required
@requires_manage('settings')
def admin_update_leave_settings():
    """Update leave quota settings"""
    data = request.json or {}
    allowed_fields = ['monthly_sick_leaves', 'monthly_casual_leaves', 'max_carry_forward']
    update_data = {}
    for k in allowed_fields:
        if k in data:
            try:
                val = int(data[k])
                if val < 0:
                    return jsonify({'error': f'{k} must be 0 or greater'}), 400
                update_data[k] = val
            except (ValueError, TypeError):
                return jsonify({'error': f'{k} must be an integer'}), 400

    if not update_data:
        return jsonify({'error': 'No valid fields provided'}), 400

    settings = FirebaseSettings.update_leave_settings(update_data)
    settings['updated_at'] = settings['updated_at'].isoformat() if settings.get('updated_at') else None
    return jsonify(settings)


@superadmin_bp.route('/api/admin/leave-balances/fiscal-year-reset', methods=['POST'])
@superadmin_required
@requires_manage('leave_summary')
def admin_fiscal_year_reset():
    """Manually trigger fiscal year reset: archive March balances and reset April
    balances to the monthly allotment with no carry-forward. Accepts optional
    `fy_end_year` in body (defaults to current year)."""
    data = request.json or {}
    try:
        fy_end_year = int(data.get('fy_end_year') or datetime.now(timezone.utc).year)
    except (ValueError, TypeError):
        return jsonify({'error': 'fy_end_year must be an integer'}), 400

    result = FirebaseLeaveBalance.run_fiscal_year_reset(fy_end_year)
    return jsonify({'success': True, 'fy_end_year': fy_end_year, **result})


@superadmin_bp.route('/api/admin/attendance/leave-summary', methods=['GET'])
@superadmin_required
def admin_leave_summary():
    """Get leave balance summary for all users for a given month"""
    now = datetime.now(timezone.utc)
    try:
        year = int(request.args.get('year', now.year))
        month = int(request.args.get('month', now.month))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid year or month'}), 400

    all_users = FirebaseUser.get_all()
    existing_balances = FirebaseLeaveBalance.get_all_for_month(year, month)
    balance_map = {b['user_id']: b for b in existing_balances}

    result = []
    for user in all_users:
        uid = user['id']
        if uid in balance_map:
            b = balance_map[uid]
        else:
            b = FirebaseLeaveBalance.get_or_create(uid, year, month)

        sick_total = b.get('sick_allotted', 1) + b.get('carried_sick', 0)
        casual_total = b.get('casual_allotted', 1) + b.get('carried_casual', 0)
        result.append({
            'user_id': uid,
            'user_name': user.get('full_name') or user.get('username', 'Unknown'),
            'email': user.get('email', ''),
            'sick_allotted': b.get('sick_allotted', 1),
            'sick_used': b.get('sick_used', 0),
            'sick_available': max(0, sick_total - b.get('sick_used', 0)),
            'carried_sick': b.get('carried_sick', 0),
            'casual_allotted': b.get('casual_allotted', 1),
            'casual_used': b.get('casual_used', 0),
            'casual_available': max(0, casual_total - b.get('casual_used', 0)),
            'carried_casual': b.get('carried_casual', 0)
        })

    return jsonify(result)


@superadmin_bp.route('/api/admin/attendance/stats', methods=['GET'])
@superadmin_required
def admin_attendance_stats():
    """Get attendance statistics for a date compared against office timing"""
    date_str = request.args.get('date')
    if date_str:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    else:
        target_date = datetime.now(timezone.utc)

    settings = FirebaseSettings.get_office_settings()
    office_start_time = datetime.strptime(settings['office_start'], '%H:%M').time()
    office_end_time = datetime.strptime(settings['office_end'], '%H:%M').time()
    expected_hours = settings.get('expected_hours', 8)
    half_day_threshold = settings.get('half_day_threshold', 4)
    late_threshold = settings.get('late_threshold_minutes', 15)

    records = FirebaseAttendance.get_all_for_date(target_date)
    all_users = FirebaseUser.get_all()

    total_users = len(all_users)
    present_count = len(records)
    absent_count = total_users - present_count
    late_arrivals = 0
    early_departures = 0
    overtime_count = 0
    half_day_count = 0
    total_work_hours = 0

    enriched_records = []
    day_date = target_date.date()

    for record in records:
        check_in = record.get('check_in_time')
        check_out = record.get('check_out_time')
        work_hours = record.get('work_hours') or 0

        late_by = None
        early_by = None
        overtime = None

        if check_in:
            scheduled_start = datetime.combine(day_date, office_start_time).replace(tzinfo=timezone.utc)
            diff_minutes = (check_in - scheduled_start).total_seconds() / 60
            if diff_minutes > late_threshold:
                late_arrivals += 1
                late_by = round(diff_minutes)

        if check_out:
            scheduled_end = datetime.combine(day_date, office_end_time).replace(tzinfo=timezone.utc)
            diff_minutes = (scheduled_end - check_out).total_seconds() / 60
            if diff_minutes > 0:
                early_departures += 1
                early_by = round(diff_minutes)

        if work_hours:
            total_work_hours += work_hours
            if work_hours >= expected_hours:
                overtime_val = round(work_hours - expected_hours, 2)
                if overtime_val > 0:
                    overtime_count += 1
                    overtime = overtime_val
            if work_hours < half_day_threshold:
                half_day_count += 1

        enriched_records.append({
            'user_id': record.get('user_id'),
            'late_by_minutes': late_by,
            'early_by_minutes': early_by,
            'overtime_hours': overtime
        })

    avg_work_hours = round(total_work_hours / present_count, 2) if present_count > 0 else 0

    return jsonify({
        'date': target_date.strftime('%Y-%m-%d'),
        'total_users': total_users,
        'present': present_count,
        'absent': absent_count,
        'late_arrivals': late_arrivals,
        'early_departures': early_departures,
        'overtime': overtime_count,
        'half_day': half_day_count,
        'avg_work_hours': avg_work_hours,
        'avg_work_hours_formatted': _format_hours(avg_work_hours),
        'office_start': settings['office_start'],
        'office_end': settings['office_end'],
        'expected_hours': expected_hours,
        'records': enriched_records
    })


@superadmin_bp.route('/api/admin/attendance/range', methods=['GET'])
@superadmin_required
def admin_get_attendance_range():
    """Get attendance for all users across a date range (for CSV export)"""
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    if not start_str or not end_str:
        return jsonify({'error': 'start_date and end_date are required'}), 400

    try:
        start_date = datetime.strptime(start_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        end_date = datetime.strptime(end_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    except ValueError:
        return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

    if (end_date - start_date).days > 90:
        return jsonify({'error': 'Date range cannot exceed 90 days'}), 400

    if end_date < start_date:
        return jsonify({'error': 'end_date must be after start_date'}), 400

    all_users = FirebaseUser.get_all()
    user_map = {u['id']: u for u in all_users}

    attendance_data = []
    current = start_date

    while current <= end_date:
        records = FirebaseAttendance.get_all_for_date(current)
        day_holiday = FirebaseHoliday.get_for_date(current)
        users_with_records = set()

        for record in records:
            uid = record.get('user_id')
            users_with_records.add(uid)
            user = user_map.get(uid, {})
            check_in = record.get('check_in_time')
            check_out = record.get('check_out_time')
            work_hours = record.get('work_hours')
            if check_in and not check_out:
                delta = datetime.now(timezone.utc) - check_in
                work_hours = round(delta.total_seconds() / 3600, 2)

            attendance_data.append({
                'user_name': user.get('full_name') or user.get('username', 'Unknown'),
                'email': user.get('email', ''),
                'date': current.strftime('%Y-%m-%d'),
                'check_in_time': check_in.isoformat() if check_in else None,
                'check_out_time': check_out.isoformat() if check_out else None,
                'work_hours': work_hours,
                'work_hours_formatted': _format_hours(work_hours),
                'status': record.get('status', 'present'),
                'leave_type': record.get('leave_type'),
                'location_address': record.get('location_address'),
                'device_info': record.get('device_info'),
                'is_holiday': day_holiday is not None,
                'holiday_name': day_holiday.get('name') if day_holiday else None
            })

        # Add absent users for this date
        absent_status_range = 'holiday' if day_holiday else 'absent'
        for user in all_users:
            if user['id'] not in users_with_records:
                attendance_data.append({
                    'user_name': user.get('full_name') or user.get('username', 'Unknown'),
                    'email': user.get('email', ''),
                    'date': current.strftime('%Y-%m-%d'),
                    'check_in_time': None,
                    'check_out_time': None,
                    'work_hours': None,
                    'work_hours_formatted': None,
                    'status': absent_status_range,
                    'leave_type': None,
                    'location_address': None,
                    'device_info': None,
                    'is_holiday': day_holiday is not None,
                    'holiday_name': day_holiday.get('name') if day_holiday else None
                })

        current += timedelta(days=1)

    return jsonify(attendance_data)


@superadmin_bp.route('/api/admin/projects', methods=['GET'])
@superadmin_required
def admin_get_projects():
    """Get all projects with stats"""
    projects = FirebaseProject.get_all()

    all_users = FirebaseUser.get_all()
    user_map = {u['id']: u for u in all_users}

    result = []
    for project in projects:
        tasks = FirebaseTask.get_by_project(project['id'])
        members = FirebaseProjectMember.get_by_project(project['id'])
        owner = user_map.get(project.get('owner_id'), {})

        created = project.get('created_at')
        result.append({
            'id': project['id'],
            'name': project.get('name', ''),
            'description': project.get('description', ''),
            'owner_name': owner.get('full_name') or owner.get('username', 'Unknown'),
            'member_count': len(members) + 1,
            'task_count': len(tasks),
            'completed_tasks': len([t for t in tasks if t.get('status') == 'done']),
            'in_progress_tasks': len([t for t in tasks if t.get('status') == 'in_progress']),
            'created_at': created.isoformat() if created else None
        })

    return jsonify({'projects': result})


# ---- Leave Approval Workflow ----

@superadmin_bp.route('/api/admin/leave-requests', methods=['GET'])
@superadmin_required
def admin_get_leave_requests():
    """Get leave requests for admin approval, optionally filtered by status"""
    status_filter = request.args.get('status')  # pending | approved | rejected | '' (all)

    if status_filter == 'pending' or not status_filter:
        records = FirebaseAttendance.get_pending_leaves() if status_filter == 'pending' else FirebaseAttendance.get_pending_leaves()
    else:
        records = FirebaseAttendance.get_pending_leaves()

    # Get all leave records (pending + others) via a broader query if needed
    all_users = FirebaseUser.get_all()
    user_map = {u['id']: u for u in all_users}

    result = []
    for record in records:
        uid = record.get('user_id')
        user = user_map.get(uid, {})
        leave_date = record.get('leave_date')
        approval = record.get('approval_status', 'pending')
        if status_filter and approval != status_filter:
            continue
        result.append({
            'id': record.get('id'),
            'user_id': uid,
            'user_name': user.get('full_name') or user.get('username', 'Unknown'),
            'email': user.get('email', ''),
            'leave_date': leave_date.isoformat() if leave_date else None,
            'leave_type': record.get('leave_type'),
            'leave_duration': record.get('leave_duration', 'full'),
            'leave_reason': record.get('leave_reason'),
            'approval_status': approval,
            'created_at': record.get('created_at').isoformat() if record.get('created_at') else None
        })

    result.sort(key=lambda x: x.get('created_at') or '', reverse=True)
    return jsonify({'leave_requests': result})


@superadmin_bp.route('/api/admin/leave-requests/<record_id>/approve', methods=['PUT'])
@superadmin_required
@requires_manage('leave_requests')
def admin_approve_leave(record_id):
    """Approve a pending leave request — deducts leave balance"""
    record = FirebaseAttendance.get_by_id(record_id)
    if not record:
        return jsonify({'error': 'Record not found'}), 404
    if record.get('approval_status') != 'pending':
        return jsonify({'error': 'This request is not pending'}), 400

    approver_id = session.get(ADMIN_SESSION_KEY) or (current_user.id if current_user.is_authenticated else 'admin')
    updated = FirebaseAttendance.approve_leave(record_id, approver_id)

    # Deduct leave balance now
    leave_date = record.get('leave_date') or datetime.now(timezone.utc)
    year = leave_date.year if hasattr(leave_date, 'year') else datetime.now(timezone.utc).year
    month = leave_date.month if hasattr(leave_date, 'month') else datetime.now(timezone.utc).month
    leave_type = record.get('leave_type')
    leave_amount = 0.5 if record.get('leave_duration') == 'half' else 1.0
    FirebaseLeaveBalance.use_leave(record['user_id'], year, month, leave_type, leave_amount)

    return jsonify({'success': True, 'record': {
        'id': updated.get('id'),
        'approval_status': 'approved'
    }})


@superadmin_bp.route('/api/admin/leave-requests/<record_id>/reject', methods=['PUT'])
@superadmin_required
@requires_manage('leave_requests')
def admin_reject_leave(record_id):
    """Reject a pending leave request"""
    record = FirebaseAttendance.get_by_id(record_id)
    if not record:
        return jsonify({'error': 'Record not found'}), 404
    if record.get('approval_status') != 'pending':
        return jsonify({'error': 'This request is not pending'}), 400

    data = request.json or {}
    reason = (data.get('reason') or '').strip() or None

    approver_id = session.get(ADMIN_SESSION_KEY) or (current_user.id if current_user.is_authenticated else 'admin')
    updated = FirebaseAttendance.reject_leave(record_id, approver_id, reason)

    return jsonify({'success': True, 'record': {
        'id': updated.get('id'),
        'approval_status': 'rejected',
        'rejection_reason': reason
    }})


# ---- Admin Manual Attendance ----

@superadmin_bp.route('/api/admin/attendance', methods=['POST'])
@superadmin_required
@requires_manage('attendance_mgmt')
def admin_create_attendance():
    """Admin creates an attendance record for a user"""
    data = request.json or {}
    user_id = data.get('user_id')
    date_str = data.get('date')

    if not user_id or not date_str:
        return jsonify({'error': 'user_id and date are required'}), 400

    user = FirebaseUser.get_by_id(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    except ValueError:
        return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

    # Check for existing record
    existing = FirebaseAttendance.get_by_user_date(user_id, target_date)
    if existing and existing.get('check_in_time'):
        return jsonify({'error': 'Attendance record already exists for this date'}), 400

    # Parse check-in/out times
    check_in_str = data.get('check_in_time', '09:00')
    check_out_str = data.get('check_out_time')

    try:
        check_in_parts = datetime.strptime(check_in_str, '%H:%M')
        check_in_time = target_date.replace(hour=check_in_parts.hour, minute=check_in_parts.minute, second=0)
    except ValueError:
        return jsonify({'error': 'Invalid check_in_time format, use HH:MM'}), 400

    check_out_time = None
    work_hours = None
    status = 'present'

    if check_out_str:
        try:
            check_out_parts = datetime.strptime(check_out_str, '%H:%M')
            check_out_time = target_date.replace(hour=check_out_parts.hour, minute=check_out_parts.minute, second=0)
            delta = check_out_time - check_in_time
            work_hours = round(delta.total_seconds() / 3600, 2)
            settings = FirebaseSettings.get_office_settings()
            if work_hours < settings.get('half_day_threshold', 4):
                status = 'half-day'
        except ValueError:
            return jsonify({'error': 'Invalid check_out_time format, use HH:MM'}), 400

    # If there's an existing leave record, update it
    if existing:
        # Revoke leave balance if it was approved
        if existing.get('leave_type') and existing.get('approval_status') == 'approved':
            leave_date = existing.get('leave_date') or target_date
            year = leave_date.year
            month = leave_date.month
            leave_amount = 0.5 if existing.get('leave_duration') == 'half' else 1.0
            FirebaseLeaveBalance.revoke_leave(user_id, year, month, existing['leave_type'], leave_amount)

        FirebaseAttendance.update(existing['id'], {
            'check_in_time': check_in_time,
            'check_out_time': check_out_time,
            'work_hours': work_hours,
            'status': status,
            'leave_type': None,
            'leave_reason': None,
            'leave_duration': None,
            'approval_status': None,
            'manual_entry': True,
            'created_by': current_user.id,
            'notes': data.get('notes')
        })
        record = FirebaseAttendance.get_by_id(existing['id'])
    else:
        record_id = FirebaseAttendance.create(
            user_id=user_id,
            ip_address='manual',
            manual_entry=True,
            created_by=current_user.id,
            notes=data.get('notes')
        )
        FirebaseAttendance.update(record_id, {
            'check_in_time': check_in_time,
            'check_out_time': check_out_time,
            'work_hours': work_hours,
            'status': status
        })
        record = FirebaseAttendance.get_by_id(record_id)

    return jsonify({
        'success': True,
        'record': {
            'id': record.get('id'),
            'user_id': user_id,
            'check_in_time': check_in_time.isoformat(),
            'check_out_time': check_out_time.isoformat() if check_out_time else None,
            'work_hours_formatted': _format_hours(work_hours),
            'status': status,
            'manual_entry': True
        }
    }), 201


@superadmin_bp.route('/api/admin/attendance/<record_id>', methods=['PUT'])
@superadmin_required
@requires_manage('attendance_mgmt')
def admin_edit_attendance(record_id):
    """Admin edits an existing attendance record"""
    record = FirebaseAttendance.get_by_id(record_id)
    if not record:
        return jsonify({'error': 'Record not found'}), 404

    data = request.json or {}
    update_data = {
        'last_edited_by': current_user.id,
        'edited_at': datetime.now(timezone.utc)
    }

    # Get the date from the existing record
    check_in = record.get('check_in_time')
    leave_date = record.get('leave_date')
    record_date = check_in or leave_date or record.get('created_at')

    if 'check_in_time' in data and data['check_in_time']:
        try:
            parts = datetime.strptime(data['check_in_time'], '%H:%M')
            base_date = record_date.replace(hour=0, minute=0, second=0, microsecond=0) if record_date else datetime.now(timezone.utc)
            update_data['check_in_time'] = base_date.replace(hour=parts.hour, minute=parts.minute, second=0)
        except ValueError:
            return jsonify({'error': 'Invalid check_in_time format, use HH:MM'}), 400

    if 'check_out_time' in data and data['check_out_time']:
        try:
            parts = datetime.strptime(data['check_out_time'], '%H:%M')
            base_date = record_date.replace(hour=0, minute=0, second=0, microsecond=0) if record_date else datetime.now(timezone.utc)
            update_data['check_out_time'] = base_date.replace(hour=parts.hour, minute=parts.minute, second=0)
        except ValueError:
            return jsonify({'error': 'Invalid check_out_time format, use HH:MM'}), 400

    if 'notes' in data:
        update_data['notes'] = data['notes']

    if 'status' in data and data['status'] in ('present', 'half-day', 'absent'):
        update_data['status'] = data['status']

    # Recalculate work hours if both times are set
    ci = update_data.get('check_in_time', record.get('check_in_time'))
    co = update_data.get('check_out_time', record.get('check_out_time'))
    if ci and co:
        delta = co - ci
        work_hours = round(delta.total_seconds() / 3600, 2)
        update_data['work_hours'] = work_hours
        settings = FirebaseSettings.get_office_settings()
        if 'status' not in data:
            update_data['status'] = 'half-day' if work_hours < settings.get('half_day_threshold', 4) else 'present'

    update_data['manual_entry'] = True
    FirebaseAttendance.update(record_id, update_data)

    updated = FirebaseAttendance.get_by_id(record_id)
    return jsonify({
        'success': True,
        'record': {
            'id': updated.get('id'),
            'status': updated.get('status'),
            'work_hours_formatted': _format_hours(updated.get('work_hours'))
        }
    })


# ---- Monthly Report ----

@superadmin_bp.route('/api/admin/attendance/monthly-report', methods=['GET'])
@superadmin_required
def admin_monthly_report():
    """Get aggregate monthly attendance report for all users"""
    now = datetime.now(timezone.utc)
    try:
        year = int(request.args.get('year', now.year))
        month = int(request.args.get('month', now.month))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid year or month'}), 400

    import calendar
    days_in_month = calendar.monthrange(year, month)[1]
    month_start = datetime(year, month, 1, tzinfo=timezone.utc)
    month_end = datetime(year, month, days_in_month, 23, 59, 59, tzinfo=timezone.utc)

    # Count working days (exclude Sundays and holidays)
    holiday_days = FirebaseHoliday.get_holiday_dates_for_month(year, month)
    total_working_days = 0
    for day in range(1, days_in_month + 1):
        d = datetime(year, month, day)
        if d.weekday() != 6 and day not in holiday_days:  # 6 = Sunday
            total_working_days += 1

    # Get all records for the month
    all_records = FirebaseAttendance.get_all_for_date_range(month_start, month_end)
    all_users = FirebaseUser.get_all()
    user_map = {u['id']: u for u in all_users}

    settings = FirebaseSettings.get_office_settings()
    office_start_time = datetime.strptime(settings['office_start'], '%H:%M').time()
    late_threshold = settings.get('late_threshold_minutes', 15)

    # Group records by user
    user_records = {}
    for r in all_records:
        uid = r.get('user_id')
        if uid not in user_records:
            user_records[uid] = []
        user_records[uid].append(r)

    report = []
    total_leaves = 0
    total_attendance_pct = 0

    for user in all_users:
        uid = user['id']
        records = user_records.get(uid, [])

        days_present = 0
        days_half_day = 0
        days_absent = 0
        sick_leaves = 0
        casual_leaves = 0
        total_work_hours = 0
        late_arrivals = 0
        early_departures = 0

        seen_dates = set()
        for r in records:
            check_in = r.get('check_in_time')
            leave_date = r.get('leave_date')
            record_date = (check_in or leave_date or r.get('created_at'))
            if record_date:
                date_key = record_date.strftime('%Y-%m-%d')
                if date_key in seen_dates:
                    continue
                seen_dates.add(date_key)

            status = r.get('status')
            leave_type = r.get('leave_type')
            approval = r.get('approval_status')

            if status == 'present':
                days_present += 1
                wh = r.get('work_hours') or 0
                total_work_hours += wh
            elif status == 'half-day':
                days_half_day += 1
                wh = r.get('work_hours') or 0
                total_work_hours += wh
            elif leave_type and approval == 'approved':
                if leave_type == 'sick':
                    sick_leaves += 1
                elif leave_type == 'casual':
                    casual_leaves += 1

            # Late arrival / early departure — use stored flags when available
            if check_in:
                if r.get('late_arrival'):
                    late_arrivals += 1
                else:
                    day_date = check_in.date()
                    scheduled_start = datetime.combine(day_date, office_start_time).replace(tzinfo=timezone.utc)
                    diff_minutes = (check_in - scheduled_start).total_seconds() / 60
                    if diff_minutes > late_threshold:
                        late_arrivals += 1
            if r.get('check_out_time') and r.get('early_departure'):
                early_departures += 1

        effective_present = days_present + (days_half_day * 0.5)
        days_absent = max(0, total_working_days - days_present - days_half_day - sick_leaves - casual_leaves)
        attendance_pct = round((effective_present / total_working_days) * 100, 1) if total_working_days > 0 else 0
        avg_daily = round(total_work_hours / (days_present + days_half_day), 2) if (days_present + days_half_day) > 0 else 0

        total_leaves += sick_leaves + casual_leaves
        total_attendance_pct += attendance_pct

        report.append({
            'user_id': uid,
            'user_name': user.get('full_name') or user.get('username', 'Unknown'),
            'email': user.get('email', ''),
            'total_working_days': total_working_days,
            'days_present': days_present,
            'days_half_day': days_half_day,
            'days_absent': days_absent,
            'sick_leaves': sick_leaves,
            'casual_leaves': casual_leaves,
            'total_work_hours': round(total_work_hours, 2),
            'avg_daily_hours': avg_daily,
            'avg_daily_hours_formatted': _format_hours(avg_daily),
            'late_arrivals': late_arrivals,
            'early_departures': early_departures,
            'attendance_percentage': attendance_pct
        })

    avg_pct = round(total_attendance_pct / len(all_users), 1) if all_users else 0

    return jsonify({
        'year': year,
        'month': month,
        'total_working_days': total_working_days,
        'report': report,
        'summary': {
            'total_users': len(all_users),
            'avg_attendance_percentage': avg_pct,
            'total_leaves_taken': total_leaves
        }
    })


# ---- Server-Side CSV Export ----

@superadmin_bp.route('/api/admin/attendance/export-csv', methods=['GET'])
@superadmin_required
def admin_export_csv():
    """Generate and return CSV file for attendance data"""
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    if not start_str or not end_str:
        return jsonify({'error': 'start_date and end_date are required'}), 400

    try:
        start_date = datetime.strptime(start_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        end_date = datetime.strptime(end_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    except ValueError:
        return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

    if (end_date - start_date).days > 90:
        return jsonify({'error': 'Date range cannot exceed 90 days'}), 400

    all_users = FirebaseUser.get_all()
    user_map = {u['id']: u for u in all_users}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Email', 'Date', 'Check-in Time', 'Check-out Time',
                     'Work Hours', 'Status', 'Leave Type', 'Leave Duration',
                     'Location', 'Device', 'Geofence'])

    IST = timezone(timedelta(hours=5, minutes=30))
    current = start_date
    while current <= end_date:
        records = FirebaseAttendance.get_all_for_date(current)
        csv_holiday = FirebaseHoliday.get_for_date(current)
        users_with_records = set()
        for record in records:
            uid = record.get('user_id')
            users_with_records.add(uid)
            user = user_map.get(uid, {})
            check_in = record.get('check_in_time')
            check_out = record.get('check_out_time')
            work_hours = record.get('work_hours')

            writer.writerow([
                user.get('full_name') or user.get('username', 'Unknown'),
                user.get('email', ''),
                current.strftime('%d-%m-%Y'),
                check_in.astimezone(IST).strftime('%I:%M %p') if check_in else '',
                check_out.astimezone(IST).strftime('%I:%M %p') if check_out else '',
                _format_hours(work_hours) if work_hours else '',
                record.get('status', 'present'),
                record.get('leave_type', ''),
                record.get('leave_duration', ''),
                record.get('location_address', ''),
                record.get('device_info', ''),
                'Outside' if record.get('outside_geofence') else ''
            ])

        csv_absent_status = 'holiday' if csv_holiday else 'absent'
        for user in all_users:
            if user['id'] not in users_with_records:
                writer.writerow([
                    user.get('full_name') or user.get('username', 'Unknown'),
                    user.get('email', ''),
                    current.strftime('%d-%m-%Y'),
                    '', '', '', csv_absent_status, '', '', '', '', ''
                ])

        current += timedelta(days=1)

    output.seek(0)
    filename = f'attendance_{start_str}_to_{end_str}.csv'
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


@superadmin_bp.route('/api/admin/attendance/monthly-report/csv', methods=['GET'])
@superadmin_required
def admin_monthly_report_csv():
    """Generate CSV for monthly report"""
    now = datetime.now(timezone.utc)
    try:
        year = int(request.args.get('year', now.year))
        month = int(request.args.get('month', now.month))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid year or month'}), 400

    # Reuse the monthly report logic
    import calendar as cal_mod
    days_in_month = cal_mod.monthrange(year, month)[1]
    month_start = datetime(year, month, 1, tzinfo=timezone.utc)
    month_end = datetime(year, month, days_in_month, 23, 59, 59, tzinfo=timezone.utc)

    holiday_days_csv = FirebaseHoliday.get_holiday_dates_for_month(year, month)
    total_working_days = sum(1 for day in range(1, days_in_month + 1)
                            if datetime(year, month, day).weekday() != 6 and day not in holiday_days_csv)

    all_records = FirebaseAttendance.get_all_for_date_range(month_start, month_end)
    all_users = FirebaseUser.get_all()

    settings = FirebaseSettings.get_office_settings()
    office_start_time = datetime.strptime(settings['office_start'], '%H:%M').time()
    late_threshold = settings.get('late_threshold_minutes', 15)

    user_records = {}
    for r in all_records:
        uid = r.get('user_id')
        if uid not in user_records:
            user_records[uid] = []
        user_records[uid].append(r)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Email', 'Working Days', 'Days Present', 'Half Days',
                     'Days Absent', 'Sick Leaves', 'Casual Leaves', 'Total Hours',
                     'Avg Daily Hours', 'Late Arrivals', 'Attendance %'])

    for user in all_users:
        uid = user['id']
        records = user_records.get(uid, [])

        days_present = 0
        days_half_day = 0
        sick_leaves = 0
        casual_leaves = 0
        total_work_hours = 0
        late_arrivals = 0
        seen_dates = set()

        for r in records:
            check_in = r.get('check_in_time')
            leave_date = r.get('leave_date')
            record_date = check_in or leave_date or r.get('created_at')
            if record_date:
                dk = record_date.strftime('%Y-%m-%d')
                if dk in seen_dates:
                    continue
                seen_dates.add(dk)

            status = r.get('status')
            leave_type = r.get('leave_type')
            approval = r.get('approval_status')

            if status == 'present':
                days_present += 1
                total_work_hours += r.get('work_hours') or 0
            elif status == 'half-day':
                days_half_day += 1
                total_work_hours += r.get('work_hours') or 0
            elif leave_type and approval == 'approved':
                if leave_type == 'sick':
                    sick_leaves += 1
                elif leave_type == 'casual':
                    casual_leaves += 1

            if check_in:
                scheduled = datetime.combine(check_in.date(), office_start_time).replace(tzinfo=timezone.utc)
                if (check_in - scheduled).total_seconds() / 60 > late_threshold:
                    late_arrivals += 1

        days_absent = max(0, total_working_days - days_present - days_half_day - sick_leaves - casual_leaves)
        effective = days_present + days_half_day * 0.5
        att_pct = round((effective / total_working_days) * 100, 1) if total_working_days > 0 else 0
        avg_daily = round(total_work_hours / (days_present + days_half_day), 2) if (days_present + days_half_day) > 0 else 0

        writer.writerow([
            user.get('full_name') or user.get('username', 'Unknown'),
            user.get('email', ''),
            total_working_days, days_present, days_half_day, days_absent,
            sick_leaves, casual_leaves, round(total_work_hours, 2),
            _format_hours(avg_daily), late_arrivals, f'{att_pct}%'
        ])

    output.seek(0)
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    filename = f'monthly_report_{month_names[month-1]}_{year}.csv'
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


# ── Regularization Admin Endpoints ──────────────────────────────────────────

def _fmt_regularization(r):
    def _ts(v):
        return v.isoformat() if v and hasattr(v, 'isoformat') else v
    return {
        'id': r.get('id'),
        'user_id': r.get('user_id'),
        'user_name': r.get('user_name', ''),
        'request_date': _ts(r.get('request_date')),
        'reason': r.get('reason', ''),
        'intended_check_in': r.get('intended_check_in'),
        'intended_check_out': r.get('intended_check_out'),
        'status': r.get('status', 'pending'),
        'reviewed_by': r.get('reviewed_by'),
        'reviewed_at': _ts(r.get('reviewed_at')),
        'rejection_reason': r.get('rejection_reason'),
        'created_at': _ts(r.get('created_at')),
    }


@superadmin_bp.route('/api/admin/regularization', methods=['GET'])
@superadmin_required
def admin_get_regularizations():
    status_filter = request.args.get('status')
    reqs = FirebaseRegularization.get_all(status_filter=status_filter or None)
    return jsonify([_fmt_regularization(r) for r in reqs])


@superadmin_bp.route('/api/admin/regularization/<req_id>/approve', methods=['PUT'])
@superadmin_required
@requires_manage('attendance_mgmt')
def admin_approve_regularization(req_id):
    req = FirebaseRegularization.get_by_id(req_id)
    if not req:
        return jsonify({'error': 'Request not found'}), 404
    if req.get('status') != 'pending':
        return jsonify({'error': 'Request already reviewed'}), 400
    rd = req.get('request_date')
    req_date = rd if hasattr(rd, 'date') else datetime.strptime(str(rd)[:10], '%Y-%m-%d').replace(tzinfo=timezone.utc)
    check_in_str = req.get('intended_check_in', '09:00')
    check_out_str = req.get('intended_check_out')
    try:
        check_in_time = datetime.combine(req_date.date(), datetime.strptime(check_in_str, '%H:%M').time()).replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        check_in_time = req_date.replace(hour=9, minute=0)
    check_out_time = None
    work_hours = None
    if check_out_str:
        try:
            check_out_time = datetime.combine(req_date.date(), datetime.strptime(check_out_str, '%H:%M').time()).replace(tzinfo=timezone.utc)
            work_hours = round((check_out_time - check_in_time).total_seconds() / 3600, 2)
        except (ValueError, AttributeError):
            pass
    settings = FirebaseSettings.get_office_settings()
    late_arrival = False
    late_by_minutes = None
    try:
        sched_start = datetime.combine(req_date.date(), datetime.strptime(settings.get('office_start', '09:00'), '%H:%M').time()).replace(tzinfo=timezone.utc)
        diff = (check_in_time - sched_start).total_seconds() / 60
        if diff > settings.get('late_threshold_minutes', 15):
            late_arrival = True
            late_by_minutes = round(diff)
    except (ValueError, AttributeError):
        pass
    early_departure = False
    early_by_minutes = None
    if check_out_time:
        try:
            sched_end = datetime.combine(req_date.date(), datetime.strptime(settings.get('office_end', '18:00'), '%H:%M').time()).replace(tzinfo=timezone.utc)
            diff = (sched_end - check_out_time).total_seconds() / 60
            if diff > 0:
                early_departure = True
                early_by_minutes = round(diff)
        except (ValueError, AttributeError):
            pass
    status = 'present'
    if work_hours is not None and work_hours < settings.get('half_day_threshold', 4):
        status = 'half-day'
    existing = FirebaseAttendance.get_by_user_date(req.get('user_id'), req_date)
    reviewer_id = current_user.id if hasattr(current_user, 'id') else 'admin'
    att_data = {'check_in_time': check_in_time, 'status': status, 'manual_entry': True,
                'created_by': reviewer_id, 'late_arrival': late_arrival, 'late_by_minutes': late_by_minutes}
    if check_out_time:
        att_data.update({'check_out_time': check_out_time, 'work_hours': work_hours,
                         'early_departure': early_departure, 'early_by_minutes': early_by_minutes})
    if existing:
        FirebaseAttendance.update(existing['id'], att_data)
    else:
        new_id = FirebaseAttendance.create(user_id=req.get('user_id'), ip_address='regularization',
                                            late_arrival=late_arrival, late_by_minutes=late_by_minutes,
                                            manual_entry=True, created_by=reviewer_id)
        FirebaseAttendance.update(new_id, att_data)
    FirebaseRegularization.update(req_id, {'status': 'approved', 'reviewed_by': reviewer_id,
                                            'reviewed_at': datetime.now(timezone.utc)})
    return jsonify({'ok': True})


@superadmin_bp.route('/api/admin/regularization/<req_id>/reject', methods=['PUT'])
@superadmin_required
@requires_manage('attendance_mgmt')
def admin_reject_regularization(req_id):
    req = FirebaseRegularization.get_by_id(req_id)
    if not req:
        return jsonify({'error': 'Request not found'}), 404
    if req.get('status') != 'pending':
        return jsonify({'error': 'Request already reviewed'}), 400
    data = request.json or {}
    reviewer_id = current_user.id if hasattr(current_user, 'id') else 'admin'
    FirebaseRegularization.update(req_id, {'status': 'rejected', 'reviewed_by': reviewer_id,
                                            'reviewed_at': datetime.now(timezone.utc),
                                            'rejection_reason': data.get('reason', '')})
    return jsonify({'ok': True})
