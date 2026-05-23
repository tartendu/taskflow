"""
Attendance Routes Blueprint
Handles all attendance-related page route and API endpoints
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for
from flask_login import login_required, current_user
from firebase_models import FirebaseAttendance, FirebaseUser, FirebaseLeaveBalance, FirebaseSettings, FirebaseHoliday, FirebaseRegularization, haversine_distance
from datetime import datetime, timezone, timedelta

attendance_bp = Blueprint('attendance', __name__)


# ---- Helper functions (duplicated to avoid circular imports) ----

def _is_client_user():
    """Check if current user is a client"""
    return hasattr(current_user, 'is_client') and current_user.is_client


def _format_attendance(record):
    """Format attendance record for JSON response"""
    check_in = record.get('check_in_time')
    check_out = record.get('check_out_time')
    created_at = record.get('created_at')

    work_hours = record.get('work_hours')
    if check_in and not check_out:
        delta = datetime.now(timezone.utc) - check_in
        work_hours = round(delta.total_seconds() / 3600, 2)

    # Check if device is different from registered device
    device_id = record.get('device_id')
    different_device = False
    if device_id:
        user_data = FirebaseUser.get_by_id(record.get('user_id'))
        registered = user_data.get('registered_device_id') if user_data else None
        if registered and registered != device_id:
            different_device = True

    leave_date = record.get('leave_date')
    approved_at = record.get('approved_at')
    edited_at = record.get('edited_at')
    return {
        'id': record.get('id'),
        'user_id': record.get('user_id'),
        'check_in_time': check_in.isoformat() if check_in else None,
        'check_out_time': check_out.isoformat() if check_out else None,
        'leave_date': leave_date.isoformat() if leave_date else None,
        'ip_address': record.get('ip_address'),
        'latitude': record.get('latitude'),
        'longitude': record.get('longitude'),
        'location_address': record.get('location_address'),
        'work_hours': work_hours,
        'work_hours_formatted': _format_attendance_hours(work_hours),
        'status': record.get('status', 'present'),
        'leave_type': record.get('leave_type'),
        'leave_reason': record.get('leave_reason'),
        'leave_duration': record.get('leave_duration', 'full'),
        'approval_status': record.get('approval_status'),
        'approved_by': record.get('approved_by'),
        'approved_at': approved_at.isoformat() if approved_at else None,
        'rejection_reason': record.get('rejection_reason'),
        'outside_geofence': record.get('outside_geofence', False),
        'manual_entry': record.get('manual_entry', False),
        'created_by': record.get('created_by'),
        'last_edited_by': record.get('last_edited_by'),
        'edited_at': edited_at.isoformat() if edited_at else None,
        'notes': record.get('notes'),
        'device_id': device_id,
        'device_info': record.get('device_info'),
        'different_device': different_device,
        'late_arrival': record.get('late_arrival', False),
        'late_by_minutes': record.get('late_by_minutes'),
        'early_departure': record.get('early_departure', False),
        'early_by_minutes': record.get('early_by_minutes'),
        'created_at': created_at.isoformat() if created_at else None
    }


def _format_attendance_hours(hours):
    """Format decimal hours into human-readable string"""
    if not hours or hours <= 0:
        return '0h 0m'
    h = int(hours)
    m = int((hours - h) * 60)
    if h > 0:
        return f'{h}h {m}m'
    return f'{m}m'


# ---- Page Route ----

@attendance_bp.route('/attendance')
@login_required
def attendance_page():
    """Show attendance page (team users only)"""
    if _is_client_user():
        return redirect(url_for('dashboard.home_dashboard'))
    return render_template('attendance.html')


# ---- API Routes ----

@attendance_bp.route('/api/attendance/check-in', methods=['POST'])
@login_required
def attendance_check_in():
    """Check in - capture IP, GPS, and address"""
    if _is_client_user():
        return jsonify({'error': 'Clients cannot use attendance'}), 403

    # Block if face-only mode is enabled
    face_settings = FirebaseSettings.get_face_settings()
    if face_settings.get('face_only_checkin'):
        return jsonify({'error': 'Face check-in is required. Please use the Face Check-In option.', 'face_only': True}), 403

    existing = FirebaseAttendance.get_by_user_today(current_user.id)

    # If already checked in today (has check_in_time), block duplicate
    if existing and existing.get('check_in_time'):
        return jsonify({'error': 'Already checked in today', 'record': _format_attendance(existing)}), 400

    data = request.json or {}

    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip_address and ',' in ip_address:
        ip_address = ip_address.split(',')[0].strip()

    device_id = data.get('device_id')
    device_info = data.get('device_info')

    # Device binding: auto-register first device, flag different devices
    different_device = False
    user_data = FirebaseUser.get_by_id(current_user.id)
    registered_device = user_data.get('registered_device_id') if user_data else None

    if device_id:
        if not registered_device:
            # First time: register this device
            FirebaseUser.update(current_user.id, {
                'registered_device_id': device_id,
                'registered_device_info': device_info or ''
            })
        elif registered_device != device_id:
            different_device = True

    # Geofencing check (warn only)
    outside_geofence = False
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    if latitude is not None and longitude is not None:
        office_settings = FirebaseSettings.get_office_settings()
        if office_settings.get('geofence_enabled'):
            office_lat = office_settings.get('office_latitude')
            office_lng = office_settings.get('office_longitude')
            radius = office_settings.get('geofence_radius_meters', 200)
            if office_lat is not None and office_lng is not None:
                distance = haversine_distance(latitude, longitude, office_lat, office_lng)
                if distance > radius:
                    outside_geofence = True

    # Late arrival detection
    now_utc = datetime.now(timezone.utc)
    late_arrival = False
    late_by_minutes = None
    if not existing or not existing.get('check_in_time'):
        try:
            chk_settings = FirebaseSettings.get_office_settings()
            office_start_str = chk_settings.get('office_start', '09:00')
            late_threshold = chk_settings.get('late_threshold_minutes', 15)
            scheduled_start = datetime.combine(now_utc.date(), datetime.strptime(office_start_str, '%H:%M').time()).replace(tzinfo=timezone.utc)
            diff = (now_utc - scheduled_start).total_seconds() / 60
            if diff > late_threshold:
                late_arrival = True
                late_by_minutes = round(diff)
        except (ValueError, AttributeError):
            pass

    if existing and not existing.get('check_in_time'):
        # Existing leave/absent record for today — convert it to a check-in
        # Revoke leave balance if it was a leave record
        if existing.get('leave_type') and existing.get('approval_status') == 'approved':
            leave_type = existing['leave_type']
            leave_date = existing.get('leave_date') or now_utc
            year = leave_date.year if hasattr(leave_date, 'year') else now_utc.year
            month = leave_date.month if hasattr(leave_date, 'month') else now_utc.month
            leave_amount = 0.5 if existing.get('leave_duration') == 'half' else 1.0
            FirebaseLeaveBalance.revoke_leave(current_user.id, year, month, leave_type, leave_amount)

        FirebaseAttendance.update(existing['id'], {
            'check_in_time': now_utc,
            'ip_address': ip_address,
            'latitude': latitude,
            'longitude': longitude,
            'location_address': data.get('location_address'),
            'notes': data.get('notes'),
            'device_id': device_id,
            'device_info': device_info,
            'status': 'present',
            'leave_type': None,
            'leave_reason': None,
            'leave_duration': None,
            'approval_status': None,
            'outside_geofence': outside_geofence,
            'late_arrival': late_arrival,
            'late_by_minutes': late_by_minutes,
        })
        record = FirebaseAttendance.get_by_id(existing['id'])
    else:
        # No existing record — create new check-in
        record_id = FirebaseAttendance.create(
            user_id=current_user.id,
            ip_address=ip_address,
            latitude=latitude,
            longitude=longitude,
            location_address=data.get('location_address'),
            notes=data.get('notes'),
            device_id=device_id,
            device_info=device_info,
            outside_geofence=outside_geofence,
            late_arrival=late_arrival,
            late_by_minutes=late_by_minutes,
        )
        record = FirebaseAttendance.get_by_id(record_id)

    result = _format_attendance(record)
    result['different_device'] = different_device
    result['outside_geofence'] = outside_geofence
    return jsonify(result), 201


@attendance_bp.route('/api/attendance/check-out', methods=['PUT'])
@login_required
def attendance_check_out():
    """Check out - end current session"""
    if _is_client_user():
        return jsonify({'error': 'Clients cannot use attendance'}), 403

    existing = FirebaseAttendance.get_by_user_today(current_user.id)
    if not existing:
        return jsonify({'error': 'No check-in found for today'}), 400

    if existing.get('check_out_time'):
        return jsonify({'error': 'Already checked out today', 'record': _format_attendance(existing)}), 400

    updated = FirebaseAttendance.check_out(existing['id'])
    return jsonify(_format_attendance(updated))


@attendance_bp.route('/api/attendance/status', methods=['GET'])
@login_required
def attendance_status():
    """Get today's attendance status for current user"""
    if _is_client_user():
        return jsonify({'error': 'Clients cannot use attendance'}), 403

    record = FirebaseAttendance.get_by_user_today(current_user.id)
    if record:
        return jsonify({
            'checked_in': True,
            'checked_out': record.get('check_out_time') is not None,
            'record': _format_attendance(record)
        })
    return jsonify({
        'checked_in': False,
        'checked_out': False,
        'record': None
    })


@attendance_bp.route('/api/attendance/history', methods=['GET'])
@login_required
def attendance_history():
    """Get attendance history for the current user (with optional pagination)"""
    if _is_client_user():
        return jsonify({'error': 'Clients cannot use attendance'}), 403

    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    if start_str:
        start_date = datetime.strptime(start_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    else:
        start_date = datetime.now(timezone.utc) - timedelta(days=30)

    if end_str:
        end_date = datetime.strptime(end_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
    else:
        end_date = datetime.now(timezone.utc)

    records = FirebaseAttendance.get_by_user_date_range(current_user.id, start_date, end_date)

    # Pagination support
    page = request.args.get('page')
    per_page = int(request.args.get('per_page', 20))
    if page is not None:
        page = int(page)
        total = len(records)
        start = (page - 1) * per_page
        end = start + per_page
        paginated = records[start:end]
        return jsonify({
            'records': [_format_attendance(r) for r in paginated],
            'total': total,
            'page': page,
            'per_page': per_page,
            'has_more': end < total
        })

    return jsonify([_format_attendance(r) for r in records])


@attendance_bp.route('/api/attendance/team', methods=['GET'])
@login_required
def attendance_team():
    """Get all team members' attendance for a date"""
    if _is_client_user():
        return jsonify({'error': 'Clients cannot use attendance'}), 403

    date_str = request.args.get('date')
    if date_str:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    else:
        target_date = datetime.now(timezone.utc)

    records = FirebaseAttendance.get_all_for_date(target_date)
    holiday_info = FirebaseHoliday.get_for_date(target_date)

    attendance_map = {}
    for record in records:
        attendance_map[record['user_id']] = _format_attendance(record)

    all_users = FirebaseUser.get_all()
    absent_status = 'holiday' if holiday_info else 'absent'
    team_attendance = []
    for user in all_users:
        user_record = attendance_map.get(user['id'])
        team_attendance.append({
            'user_id': user['id'],
            'user_name': user.get('full_name') or user.get('username', ''),
            'email': user.get('email', ''),
            'check_in_time': user_record['check_in_time'] if user_record else None,
            'check_out_time': user_record['check_out_time'] if user_record else None,
            'work_hours_formatted': user_record['work_hours_formatted'] if user_record else None,
            'location_address': user_record['location_address'] if user_record else None,
            'status': user_record['status'] if user_record else absent_status,
            'leave_type': user_record.get('leave_type') if user_record else None,
            'device_info': user_record['device_info'] if user_record else None,
            'different_device': user_record.get('different_device', False) if user_record else False,
            'holiday_name': holiday_info.get('name') if holiday_info else None
        })

    return jsonify(team_attendance)


@attendance_bp.route('/api/attendance/leave-balance', methods=['GET'])
@login_required
def attendance_leave_balance():
    """Get leave balance for current user for a given month"""
    if _is_client_user():
        return jsonify({'error': 'Clients cannot use attendance'}), 403

    now = datetime.now(timezone.utc)
    try:
        year = int(request.args.get('year', now.year))
        month = int(request.args.get('month', now.month))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid year or month'}), 400

    balance = FirebaseLeaveBalance.get_available(current_user.id, year, month)
    balance['year'] = year
    balance['month'] = month
    return jsonify(balance)


@attendance_bp.route('/api/attendance/mark-leave', methods=['POST'])
@login_required
def attendance_mark_leave():
    """Mark an absent day as sick or casual leave (goes through approval workflow)"""
    if _is_client_user():
        return jsonify({'error': 'Clients cannot use attendance'}), 403

    data = request.json or {}
    date_str = data.get('date')
    leave_type = data.get('leave_type')
    leave_reason = (data.get('leave_reason') or '').strip() or None
    leave_duration = data.get('leave_duration', 'full')

    if not date_str:
        return jsonify({'error': 'date is required'}), 400
    if leave_type not in ('sick', 'casual'):
        return jsonify({'error': 'leave_type must be sick or casual'}), 400
    if leave_duration not in ('full', 'half'):
        return jsonify({'error': 'leave_duration must be full or half'}), 400

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    except ValueError:
        return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

    today = datetime.now(timezone.utc).date()
    target_day = target_date.date()

    # Block leave on holidays
    holiday_check = FirebaseHoliday.get_for_date(target_date)
    if holiday_check:
        return jsonify({'error': f'Cannot mark leave on a holiday: {holiday_check.get("name")}'}), 400

    # Sick leave: only today or past (cannot plan sick leave in advance)
    if leave_type == 'sick' and target_day > today:
        return jsonify({'error': 'Sick leave can only be marked for today or past dates'}), 400

    # Casual leave: must be applied at least 1 day in advance (tomorrow or later)
    if leave_type == 'casual' and target_day == today:
        return jsonify({'error': 'Casual leave must be applied at least 1 day in advance'}), 400

    year = target_date.year
    month = target_date.month

    # Check balance availability
    leave_amount = 0.5 if leave_duration == 'half' else 1.0
    avail = FirebaseLeaveBalance.get_available(current_user.id, year, month)
    avail_key = 'sick_available' if leave_type == 'sick' else 'casual_available'
    if avail[avail_key] < leave_amount:
        leave_name = 'Sick' if leave_type == 'sick' else 'Casual'
        return jsonify({'error': f'No {leave_name} Leave balance available for this month'}), 400

    # Check for existing attendance record on that date
    existing = FirebaseAttendance.get_by_user_date(current_user.id, target_date)

    if existing:
        # If they already checked in (not absent), cannot mark leave
        if existing.get('check_in_time') is not None:
            return jsonify({'error': 'Cannot mark leave for a day you checked in'}), 400
        # If already has a pending/approved leave, block
        if existing.get('leave_type') and existing.get('approval_status') in ('pending', 'approved'):
            old_leave = existing['leave_type']
            if old_leave == leave_type and existing.get('leave_duration', 'full') == leave_duration:
                return jsonify({'error': f'Already marked as {leave_type} leave'}), 400
            # Revoke old leave if it was approved
            if existing.get('approval_status') == 'approved':
                old_amount = 0.5 if existing.get('leave_duration') == 'half' else 1.0
                FirebaseLeaveBalance.revoke_leave(current_user.id, year, month, old_leave, old_amount)
        # Set leave_date for proper date-based lookup
        leave_date = target_date.replace(hour=12, minute=0, second=0, microsecond=0)
        update_data = {
            'leave_type': leave_type,
            'leave_duration': leave_duration,
            'status': 'absent',
            'leave_date': leave_date,
            'leave_reason': leave_reason,
            'approval_status': 'pending'
        }
        FirebaseAttendance.update(existing['id'], update_data)
        record = FirebaseAttendance.get_by_id(existing['id'])
    else:
        # Create a leave record (no check-in) with pending approval
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()
        leave_date = target_date.replace(hour=12, minute=0, second=0, microsecond=0)
        record_id = FirebaseAttendance.create(
            user_id=current_user.id,
            ip_address=ip_address,
            leave_type=leave_type,
            status='absent',
            leave_date=leave_date,
            leave_reason=leave_reason,
            leave_duration=leave_duration,
            approval_status='pending'
        )
        record = FirebaseAttendance.get_by_id(record_id)

    # Balance is NOT deducted until admin approves
    updated_balance = FirebaseLeaveBalance.get_available(current_user.id, year, month)
    updated_balance['year'] = year
    updated_balance['month'] = month

    return jsonify({
        'record': _format_attendance(record),
        'balance': updated_balance
    })


@attendance_bp.route('/api/attendance/mark-leave', methods=['DELETE'])
@login_required
def attendance_revoke_leave():
    """Revoke/cancel a previously marked leave"""
    if _is_client_user():
        return jsonify({'error': 'Clients cannot use attendance'}), 403

    data = request.json or {}
    date_str = data.get('date')

    if not date_str:
        return jsonify({'error': 'date is required'}), 400

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    except ValueError:
        return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

    existing = FirebaseAttendance.get_by_user_date(current_user.id, target_date)

    if not existing or not existing.get('leave_type'):
        return jsonify({'error': 'No leave marked for this date'}), 400

    leave_type = existing['leave_type']
    leave_duration = existing.get('leave_duration', 'full')
    leave_amount = 0.5 if leave_duration == 'half' else 1.0
    approval_status = existing.get('approval_status')
    year = target_date.year
    month = target_date.month

    # Only revoke balance if it was already approved (deducted)
    if approval_status == 'approved':
        FirebaseLeaveBalance.revoke_leave(current_user.id, year, month, leave_type, leave_amount)

    # If the record was a leave-only record (no check-in), delete it entirely
    # so the day doesn't show as "absent" on the calendar
    if existing.get('check_in_time') is None:
        FirebaseAttendance.delete(existing['id'])
        updated_balance = FirebaseLeaveBalance.get_available(current_user.id, year, month)
        updated_balance['year'] = year
        updated_balance['month'] = month
        return jsonify({
            'record': None,
            'balance': updated_balance
        })

    # If user had checked in, just clear the leave fields
    FirebaseAttendance.update(existing['id'], {
        'leave_type': None,
        'leave_reason': None,
        'leave_duration': None,
        'approval_status': None,
        'approved_by': None,
        'approved_at': None,
        'rejection_reason': None
    })

    updated_balance = FirebaseLeaveBalance.get_available(current_user.id, year, month)
    updated_balance['year'] = year
    updated_balance['month'] = month

    record = FirebaseAttendance.get_by_id(existing['id'])
    return jsonify({
        'record': _format_attendance(record),
        'balance': updated_balance
    })


@attendance_bp.route('/api/attendance/holidays', methods=['GET'])
@login_required
def attendance_holidays():
    """Get holidays for a given month/year (user-facing)"""
    if _is_client_user():
        return jsonify({'error': 'Clients cannot use attendance'}), 403

    now = datetime.now(timezone.utc)
    try:
        year = int(request.args.get('year', now.year))
        month = int(request.args.get('month', now.month))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid year or month'}), 400

    holidays = FirebaseHoliday.get_for_month(year, month)
    result = []
    for h in holidays:
        d = h.get('date')
        result.append({
            'date': d.isoformat() if d else None,
            'name': h.get('name'),
            'type': h.get('type', 'company'),
            'day': d.day if d else None
        })
    return jsonify(result)


# ── Regularization Requests ──────────────────────────────────────────────────

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


@attendance_bp.route('/api/attendance/regularization', methods=['POST'])
@login_required
def submit_regularization():
    if _is_client_user():
        return jsonify({'error': 'Clients cannot submit regularization'}), 403
    data = request.json or {}
    date_str = data.get('date')
    reason = (data.get('reason') or '').strip()
    intended_check_in = (data.get('intended_check_in') or '').strip()
    intended_check_out = (data.get('intended_check_out') or '').strip() or None

    if not date_str or not reason or not intended_check_in:
        return jsonify({'error': 'Date, reason and intended check-in are required'}), 400

    try:
        req_date = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    except ValueError:
        return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    if req_date >= today:
        return jsonify({'error': 'Regularization is only for past dates'}), 400

    # Block if already has a check-in on that date
    existing = FirebaseAttendance.get_by_user_date(current_user.id, req_date)
    if existing and existing.get('check_in_time'):
        return jsonify({'error': 'Attendance already recorded for this date'}), 400

    # Block duplicate pending request for same date
    user_reqs = FirebaseRegularization.get_by_user(current_user.id)
    for r in user_reqs:
        rd = r.get('request_date')
        rd_str = rd.strftime('%Y-%m-%d') if hasattr(rd, 'strftime') else str(rd)[:10]
        if rd_str == date_str and r.get('status') == 'pending':
            return jsonify({'error': 'A pending regularization already exists for this date'}), 400

    user_data = FirebaseUser.get_by_id(current_user.id) or {}
    user_name = user_data.get('full_name') or user_data.get('username', 'Unknown')

    req_id = FirebaseRegularization.create(
        user_id=current_user.id,
        user_name=user_name,
        request_date=req_date,
        reason=reason,
        intended_check_in=intended_check_in,
        intended_check_out=intended_check_out,
    )
    rec = FirebaseRegularization.get_by_id(req_id)
    return jsonify(_fmt_regularization(rec)), 201


@attendance_bp.route('/api/attendance/regularization', methods=['GET'])
@login_required
def get_my_regularizations():
    if _is_client_user():
        return jsonify([])
    reqs = FirebaseRegularization.get_by_user(current_user.id)
    return jsonify([_fmt_regularization(r) for r in reqs])


@attendance_bp.route('/api/attendance/regularization/<req_id>', methods=['DELETE'])
@login_required
def cancel_regularization(req_id):
    if _is_client_user():
        return jsonify({'error': 'Forbidden'}), 403
    req = FirebaseRegularization.get_by_id(req_id)
    if not req:
        return jsonify({'error': 'Request not found'}), 404
    if req.get('user_id') != current_user.id:
        return jsonify({'error': 'Not your request'}), 403
    if req.get('status') != 'pending':
        return jsonify({'error': 'Only pending requests can be cancelled'}), 400
    FirebaseRegularization.delete(req_id)
    return jsonify({'ok': True})
