"""
Calendar & Time Management Routes Blueprint
Handles calendar, events, and time tracking
"""

from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from firebase_models import (
    FirebaseProject, FirebaseTask, FirebaseEvent, FirebaseTimeEntry
)
from datetime import datetime, timezone
from helpers import (
    format_task, format_event, format_time_entry, format_duration,
    is_client_user, has_project_access, get_user_cached
)

calendar_bp = Blueprint('calendar', __name__)


@calendar_bp.route('/calendar')
@login_required
def calendar():
    """Show calendar page"""
    return render_template('calendar.html')


@calendar_bp.route('/api/calendar/tasks', methods=['GET'])
@login_required
def get_calendar_tasks():
    """Get tasks with due dates for calendar view"""
    tasks = FirebaseTask.get_by_assigned_user(current_user.id)

    calendar_tasks = []
    for task in tasks:
        if task.get('due_date'):
            project = FirebaseProject.get_by_id(task['project_id'])
            task['project_name'] = project['name'] if project else 'Unknown'
            calendar_tasks.append(format_task(task))

    return jsonify(calendar_tasks)


@calendar_bp.route('/api/calendar/events', methods=['GET'])
@login_required
def get_calendar_events():
    """Get events for calendar view"""
    events = FirebaseEvent.get_by_user(current_user.id)
    return jsonify([format_event(e) for e in events])


@calendar_bp.route('/time-management')
@login_required
def time_management():
    """Show time management page"""
    return render_template('time_management.html')


@calendar_bp.route('/api/events', methods=['GET'])
@login_required
def get_events():
    """Get all events for the current user"""
    events = FirebaseEvent.get_by_user(current_user.id)
    return jsonify([format_event(e) for e in events])


@calendar_bp.route('/api/events', methods=['POST'])
@login_required
def create_event():
    """Create a new event"""
    data = request.json

    start_time = datetime.fromisoformat(data.get('start_time').replace('Z', '+00:00')) if data.get('start_time') else None
    end_time = datetime.fromisoformat(data.get('end_time').replace('Z', '+00:00')) if data.get('end_time') else None

    event_id = FirebaseEvent.create(
        title=data.get('title'),
        description=data.get('description', ''),
        event_type=data.get('event_type', 'meeting'),
        start_time=start_time,
        end_time=end_time,
        location=data.get('location', ''),
        user_id=current_user.id
    )

    event = FirebaseEvent.get_by_id(event_id)
    return jsonify(format_event(event)), 201


@calendar_bp.route('/api/events/<event_id>', methods=['PUT'])
@login_required
def update_event(event_id):
    """Update an event"""
    event = FirebaseEvent.get_by_id(event_id)
    if not event or event.get('user_id') != current_user.id:
        return jsonify({'error': 'Event not found'}), 404

    data = request.json
    update_data = {}

    if 'title' in data:
        update_data['title'] = data['title']
    if 'description' in data:
        update_data['description'] = data['description']
    if 'event_type' in data:
        update_data['event_type'] = data['event_type']
    if 'location' in data:
        update_data['location'] = data['location']
    if 'start_time' in data:
        update_data['start_time'] = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
    if 'end_time' in data:
        update_data['end_time'] = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))

    FirebaseEvent.update(event_id, update_data)
    updated_event = FirebaseEvent.get_by_id(event_id)
    return jsonify(format_event(updated_event))


@calendar_bp.route('/api/events/<event_id>', methods=['DELETE'])
@login_required
def delete_event(event_id):
    """Delete an event"""
    event = FirebaseEvent.get_by_id(event_id)
    if not event or event.get('user_id') != current_user.id:
        return jsonify({'error': 'Event not found'}), 404

    FirebaseEvent.delete(event_id)
    return jsonify({'message': 'Event deleted successfully'})


# ---- Time Tracking Routes ----

@calendar_bp.route('/api/tasks/<task_id>/time-entries', methods=['GET'])
@login_required
def get_task_time_entries(task_id):
    """Get all time entries for a task"""
    task = FirebaseTask.get_by_id(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if not has_project_access(task['project_id']):
        return jsonify({'error': 'Access denied'}), 403

    try:
        entries = FirebaseTimeEntry.get_by_task(task_id)
        total_minutes = sum(e.get('duration_minutes', 0) for e in entries)

        for entry in entries:
            user = get_user_cached(entry['user_id'])
            if user:
                entry['username'] = user.get('username', 'Unknown')

        return jsonify({
            'entries': [format_time_entry(e) for e in entries],
            'total_minutes': total_minutes,
            'total_formatted': format_duration(total_minutes)
        })
    except Exception as e:
        print(f"Error fetching time entries: {e}")
        return jsonify({'entries': [], 'total_minutes': 0, 'total_formatted': '0h 0m'})


@calendar_bp.route('/api/tasks/<task_id>/time-entries', methods=['POST'])
@login_required
def create_time_entry(task_id):
    """Create a new time entry for a task"""
    if is_client_user():
        return jsonify({'error': 'Clients cannot log time'}), 403

    task = FirebaseTask.get_by_id(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if not has_project_access(task['project_id']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    duration_minutes = data.get('duration_minutes', 0)

    if 'hours' in data or 'minutes' in data:
        hours = data.get('hours', 0) or 0
        minutes = data.get('minutes', 0) or 0
        duration_minutes = int(hours) * 60 + int(minutes)

    if duration_minutes <= 0:
        return jsonify({'error': 'Duration must be greater than 0'}), 400

    entry_id = FirebaseTimeEntry.create(
        task_id=task_id,
        user_id=current_user.id,
        duration_minutes=duration_minutes,
        description=data.get('description', '')
    )

    entry = FirebaseTimeEntry.get_by_id(entry_id)

    total_minutes = FirebaseTimeEntry.get_total_time_for_task(task_id)

    return jsonify({
        'entry': format_time_entry(entry),
        'total_minutes': total_minutes,
        'total_formatted': format_duration(total_minutes)
    }), 201


@calendar_bp.route('/api/time-entries/<entry_id>', methods=['DELETE'])
@login_required
def delete_time_entry(entry_id):
    """Delete a time entry"""
    if is_client_user():
        return jsonify({'error': 'Clients cannot delete time entries'}), 403

    entry = FirebaseTimeEntry.get_by_id(entry_id)
    if not entry:
        return jsonify({'error': 'Time entry not found'}), 404

    if entry.get('user_id') != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    task_id = entry.get('task_id')
    FirebaseTimeEntry.delete(entry_id)

    total_minutes = FirebaseTimeEntry.get_total_time_for_task(task_id)

    return jsonify({
        'message': 'Time entry deleted successfully',
        'total_minutes': total_minutes,
        'total_formatted': format_duration(total_minutes)
    })
