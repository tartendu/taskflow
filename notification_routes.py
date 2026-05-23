"""
Notification Routes Blueprint
Handles notification APIs
"""

from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from firebase_models import FirebaseNotification
from helpers import is_client_user, format_notification

notification_bp = Blueprint('notification', __name__)


@notification_bp.route('/api/notifications', methods=['GET'])
@login_required
def get_notifications():
    """Get all notifications for current user"""
    if is_client_user():
        return jsonify({'error': 'Access denied'}), 403

    notifications = FirebaseNotification.get_by_user(current_user.id)
    return jsonify([format_notification(n) for n in notifications])


@notification_bp.route('/api/notifications/unread-count', methods=['GET'])
@login_required
def get_unread_notification_count():
    """Get count of unread notifications"""
    if is_client_user():
        return jsonify({'count': 0})

    count = FirebaseNotification.get_unread_count(current_user.id)
    return jsonify({'count': count})


@notification_bp.route('/api/notifications/<notification_id>/read', methods=['PUT'])
@login_required
def mark_notification_read(notification_id):
    """Mark a notification as read"""
    if is_client_user():
        return jsonify({'error': 'Access denied'}), 403

    FirebaseNotification.mark_as_read(notification_id)
    return jsonify({'success': True})


@notification_bp.route('/api/notifications/mark-all-read', methods=['PUT'])
@login_required
def mark_all_notifications_read():
    """Mark all notifications as read"""
    if is_client_user():
        return jsonify({'error': 'Access denied'}), 403

    FirebaseNotification.mark_all_as_read(current_user.id)
    return jsonify({'success': True})
