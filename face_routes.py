"""
Face Recognition Routes
Handles face enrollment and face-verified check-in using face-api.js embeddings.
All ML inference runs in the browser; server only stores/compares 128-dim embeddings.
"""

import math
import uuid
from functools import wraps
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, session
from flask_login import login_required, current_user
from helpers import requires_manage
from firebase_models import (
    FirebaseFaceEmbedding, FirebaseUser, FirebaseAttendance,
    FirebaseLeaveBalance, FirebaseSettings, haversine_distance
)

ADMIN_SESSION_KEY = 'admin_user_id'

def _is_admin():
    """Check if current user has admin access (mirrors superadmin_required logic)."""
    if session.get(ADMIN_SESSION_KEY):
        return True
    if not current_user.is_authenticated:
        return False
    if getattr(current_user, 'is_superadmin', False):
        return True
    from firebase_models import FirebaseRole, perm_allows_view
    role = getattr(current_user, 'role', 'employee')
    try:
        perms = FirebaseRole.get_permissions_for_role(role)
    except Exception:
        perms = {}
    return any(perm_allows_view(perms.get(p)) for p in ['attendance_mgmt', 'settings'])

def _admin_required(f):
    """Decorator: allow admin portal session OR Flask-Login superadmin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _is_admin():
            return jsonify({'error': 'Admin access required'}), 401
        return f(*args, **kwargs)
    return decorated

face_bp = Blueprint('face', __name__)

@face_bp.route('/api/face/debug-session', methods=['GET'])
def debug_session():
    """Temp debug: show session keys and auth state."""
    return jsonify({
        'session_keys': list(session.keys()),
        'admin_user_id': session.get(ADMIN_SESSION_KEY),
        'is_authenticated': current_user.is_authenticated if hasattr(current_user, 'is_authenticated') else None,
    })

# In-memory challenge token store: {token: (user_id, expires_at)}
# Lightweight — tokens are 60-second TTL, no persistence needed
_challenge_store = {}

SIMILARITY_THRESHOLD = 0.55  # Euclidean distance cutoff (face-api.js uses distance, not cosine)
                               # Lower = stricter. 0.6 is face-api.js default, 0.55 is tighter.


def _euclidean_distance(a, b):
    """Euclidean distance between two 128-dim embedding vectors."""
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _is_client_user():
    return hasattr(current_user, 'is_client') and current_user.is_client


def _cleanup_expired_challenges():
    """Remove expired tokens from the in-memory store."""
    now = datetime.now(timezone.utc)
    expired = [t for t, (_, exp) in _challenge_store.items() if now > exp]
    for t in expired:
        del _challenge_store[t]


# ── Challenge Token (anti-replay) ──────────────────────────────────────────

@face_bp.route('/api/face/challenge', methods=['POST'])
@login_required
def get_challenge():
    """Issue a one-time challenge token valid for 60 seconds."""
    if _is_client_user():
        return jsonify({'error': 'Not allowed'}), 403

    _cleanup_expired_challenges()
    token = str(uuid.uuid4())
    _challenge_store[token] = (
        current_user.id,
        datetime.now(timezone.utc) + timedelta(seconds=60)
    )
    return jsonify({'challenge_token': token})


def _consume_challenge(token):
    """
    Validate and consume a challenge token.
    Returns True if valid for current_user, False otherwise.
    """
    _cleanup_expired_challenges()
    entry = _challenge_store.get(token)
    if not entry:
        return False
    user_id, expires_at = entry
    if datetime.now(timezone.utc) > expires_at:
        del _challenge_store[token]
        return False
    if user_id != current_user.id:
        return False
    del _challenge_store[token]   # one-time use
    return True


# ── Enrollment ──────────────────────────────────────────────────────────────

@face_bp.route('/api/face/enroll', methods=['POST'])
@login_required
def face_enroll():
    """
    Store the user's face embedding.
    Body: { "embedding": [128 floats] }
    The embedding is computed by face-api.js in the browser.
    """
    if _is_client_user():
        return jsonify({'error': 'Not allowed'}), 403

    data = request.json or {}
    embedding = data.get('embedding')

    if not embedding or not isinstance(embedding, list) or len(embedding) != 128:
        return jsonify({'error': 'Invalid embedding — must be a list of 128 floats'}), 400

    # Validate all values are numeric
    try:
        embedding = [float(v) for v in embedding]
    except (TypeError, ValueError):
        return jsonify({'error': 'Embedding must contain numeric values only'}), 400

    FirebaseFaceEmbedding.enroll(
        user_id=current_user.id,
        embedding=embedding,
        enrolled_by=current_user.id
    )
    # Flag user as enrolled
    FirebaseUser.update(current_user.id, {'face_enrolled': True})

    return jsonify({'ok': True, 'message': 'Face enrolled successfully'})


# ── Enrollment Status ───────────────────────────────────────────────────────

@face_bp.route('/api/face/enrollment-status', methods=['GET'])
@login_required
def face_enrollment_status():
    """Check if the current user has a face enrolled."""
    if _is_client_user():
        return jsonify({'enrolled': False})

    record = FirebaseFaceEmbedding.get_by_user(current_user.id)
    if record:
        enrolled_at = record.get('enrolled_at')
        return jsonify({
            'enrolled': True,
            'enrolled_at': enrolled_at.isoformat() if enrolled_at else None
        })
    return jsonify({'enrolled': False})


# ── Face Verify + Check-In ──────────────────────────────────────────────────

@face_bp.route('/api/face/verify-and-checkin', methods=['POST'])
@login_required
def face_verify_and_checkin():
    """
    Verify face embedding then perform check-in.
    Body: {
        "embedding": [128 floats],
        "challenge_token": "...",
        "latitude": ..., "longitude": ...,
        "location_address": "...",
        "device_id": "...", "device_info": "..."
    }
    """
    if _is_client_user():
        return jsonify({'error': 'Clients cannot use attendance'}), 403

    data = request.json or {}

    # 1. Validate challenge token (anti-replay)
    token = data.get('challenge_token')
    if not token or not _consume_challenge(token):
        return jsonify({'error': 'Invalid or expired challenge token. Please try again.'}), 400

    # 2. Validate embedding
    embedding = data.get('embedding')
    if not embedding or not isinstance(embedding, list) or len(embedding) != 128:
        return jsonify({'error': 'Invalid embedding from face detection'}), 400
    try:
        embedding = [float(v) for v in embedding]
    except (TypeError, ValueError):
        return jsonify({'error': 'Embedding contains non-numeric values'}), 400

    # 3. Load enrolled embedding
    enrolled = FirebaseFaceEmbedding.get_by_user(current_user.id)
    if not enrolled:
        return jsonify({
            'error': 'No face enrolled. Please enroll your face first.',
            'not_enrolled': True
        }), 400

    # 4. Compare embeddings
    stored_embedding = enrolled.get('embedding', [])
    if len(stored_embedding) != 128:
        return jsonify({'error': 'Stored embedding is invalid. Please re-enroll.'}), 400

    distance = _euclidean_distance(embedding, stored_embedding)

    if distance > SIMILARITY_THRESHOLD:
        return jsonify({
            'error': 'Face not recognized. Please try again or check in manually.',
            'verified': False,
            'distance': round(distance, 4)
        }), 401

    # 5. Face verified — proceed with check-in (same logic as attendance_check_in)
    existing = FirebaseAttendance.get_by_user_today(current_user.id)

    if existing and existing.get('check_in_time'):
        return jsonify({'error': 'Already checked in today', 'record': _fmt(existing)}), 400

    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip_address and ',' in ip_address:
        ip_address = ip_address.split(',')[0].strip()

    device_id = data.get('device_id')
    device_info = data.get('device_info')
    latitude = data.get('latitude')
    longitude = data.get('longitude')

    # Device binding
    different_device = False
    user_data = FirebaseUser.get_by_id(current_user.id)
    registered_device = user_data.get('registered_device_id') if user_data else None
    if device_id:
        if not registered_device:
            FirebaseUser.update(current_user.id, {
                'registered_device_id': device_id,
                'registered_device_info': device_info or ''
            })
        elif registered_device != device_id:
            different_device = True

    # Geofencing
    outside_geofence = False
    if latitude is not None and longitude is not None:
        office_settings = FirebaseSettings.get_office_settings()
        if office_settings.get('geofence_enabled'):
            office_lat = office_settings.get('office_latitude')
            office_lng = office_settings.get('office_longitude')
            radius = office_settings.get('geofence_radius_meters', 200)
            if office_lat is not None and office_lng is not None:
                dist_m = haversine_distance(latitude, longitude, office_lat, office_lng)
                if dist_m > radius:
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
            scheduled_start = datetime.combine(
                now_utc.date(),
                datetime.strptime(office_start_str, '%H:%M').time()
            ).replace(tzinfo=timezone.utc)
            diff = (now_utc - scheduled_start).total_seconds() / 60
            if diff > late_threshold:
                late_arrival = True
                late_by_minutes = round(diff)
        except (ValueError, AttributeError):
            pass

    face_check_in_extra = {
        'face_verified': True,
        'face_distance': round(distance, 4),
    }

    if existing and not existing.get('check_in_time'):
        # Convert existing leave/absent record
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
            **face_check_in_extra,
        })
        record = FirebaseAttendance.get_by_id(existing['id'])
    else:
        record_id = FirebaseAttendance.create(
            user_id=current_user.id,
            ip_address=ip_address,
            latitude=latitude,
            longitude=longitude,
            location_address=data.get('location_address'),
            device_id=device_id,
            device_info=device_info,
            outside_geofence=outside_geofence,
            late_arrival=late_arrival,
            late_by_minutes=late_by_minutes,
        )
        # Add face fields separately since create() doesn't accept them
        FirebaseAttendance.update(record_id, face_check_in_extra)
        record = FirebaseAttendance.get_by_id(record_id)

    result = _fmt(record)
    result['verified'] = True
    result['face_distance'] = round(distance, 4)
    result['different_device'] = different_device
    result['outside_geofence'] = outside_geofence
    return jsonify(result), 201


# ── Admin: Face Settings ────────────────────────────────────────────────────

@face_bp.route('/api/admin/face/settings', methods=['GET'])
@_admin_required
def admin_get_face_settings():
    """Get face recognition settings."""
    settings = FirebaseSettings.get_face_settings()
    return jsonify(settings)


@face_bp.route('/api/admin/face/settings', methods=['POST'])
@_admin_required
@requires_manage('settings')
def admin_save_face_settings():
    """Save face recognition settings (face_only_checkin toggle)."""
    data = request.json or {}
    face_only = bool(data.get('face_only_checkin', False))
    FirebaseSettings.save_face_settings({'face_only_checkin': face_only})
    return jsonify({'ok': True, 'face_only_checkin': face_only})


# ── Public: face settings for client enforcement ─────────────────────────────

@face_bp.route('/api/face/settings', methods=['GET'])
@login_required
def get_face_settings():
    """Return face settings so the frontend can enforce face-only mode."""
    if _is_client_user():
        return jsonify({'face_only_checkin': False})
    settings = FirebaseSettings.get_face_settings()
    return jsonify(settings)


# ── Admin: Revoke enrollment ────────────────────────────────────────────────

@face_bp.route('/api/admin/face/<user_id>', methods=['DELETE'])
@_admin_required
@requires_manage('settings')
def admin_revoke_face(user_id):
    """Admin: delete a user's face enrollment."""
    FirebaseFaceEmbedding.delete(user_id)
    FirebaseUser.update(user_id, {'face_enrolled': False})
    return jsonify({'ok': True})


# ── Admin: List enrollment status ───────────────────────────────────────────

@face_bp.route('/api/admin/face/enrollment-status', methods=['GET'])
@_admin_required
def admin_face_enrollment_status():
    """Admin: get face enrollment status for all users."""

    users = FirebaseUser.get_all()
    result = []
    for u in users:
        rec = FirebaseFaceEmbedding.get_by_user(u['id'])
        enrolled_at = None
        if rec and rec.get('enrolled_at'):
            enrolled_at = rec['enrolled_at'].isoformat()
        result.append({
            'user_id': u['id'],
            'username': u.get('username'),
            'full_name': u.get('full_name'),
            'enrolled': rec is not None,
            'enrolled_at': enrolled_at,
        })
    return jsonify({'users': result})


# ── Local format helper ─────────────────────────────────────────────────────

def _fmt(record):
    """Minimal attendance record formatter for face check-in response."""
    check_in = record.get('check_in_time')
    check_out = record.get('check_out_time')
    work_hours = record.get('work_hours')
    if check_in and not check_out:
        delta = datetime.now(timezone.utc) - check_in
        work_hours = round(delta.total_seconds() / 3600, 2)
    return {
        'id': record.get('id'),
        'user_id': record.get('user_id'),
        'check_in_time': check_in.isoformat() if check_in else None,
        'check_out_time': check_out.isoformat() if check_out else None,
        'status': record.get('status', 'present'),
        'work_hours': work_hours,
        'late_arrival': record.get('late_arrival', False),
        'late_by_minutes': record.get('late_by_minutes'),
        'face_verified': record.get('face_verified', False),
        'outside_geofence': record.get('outside_geofence', False),
    }
