"""
Dashboard Routes Blueprint
Handles dashboard home page and overview APIs
"""

from flask import Blueprint, request, jsonify, redirect, url_for, render_template
from flask_login import login_required, current_user
from firebase_models import (
    FirebaseUser, FirebaseProject, FirebaseTask, FirebaseProjectMember,
    FirebaseEvent, FirebaseAttendance
)
from datetime import datetime, timezone, timedelta
from helpers import format_task, format_event, get_user_all_tasks, get_project_cached

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    """Redirect to dashboard"""
    return redirect(url_for('dashboard.home_dashboard'))


@dashboard_bp.route('/dashboard')
@login_required
def home_dashboard():
    """Show dashboard home page"""
    return render_template('home_dashboard.html')


@dashboard_bp.route('/api/dashboard/overview', methods=['GET'])
@login_required
def get_dashboard_overview():
    """Get dashboard overview data (optimized)"""
    owned_projects = FirebaseProject.get_by_owner(current_user.id)
    member_records = FirebaseProjectMember.get_by_user(current_user.id)

    member_project_ids = [m['project_id'] for m in member_records]
    member_projects = []
    if member_project_ids:
        for pid in member_project_ids:
            p = FirebaseProject.get_by_id(pid)
            if p:
                member_projects.append(p)

    all_projects = {p['id']: p for p in owned_projects + member_projects}
    project_ids = list(all_projects.keys())

    my_tasks = FirebaseTask.get_by_assigned_user(current_user.id)

    total_projects = len(all_projects)
    my_tasks_count = len(my_tasks)
    completed_tasks = len([t for t in my_tasks if t.get('status') == 'done'])
    in_progress_tasks = len([t for t in my_tasks if t.get('status') == 'in_progress'])
    overdue_tasks = len([t for t in my_tasks if t.get('due_date') and t['due_date'] < datetime.now(timezone.utc) and t.get('status') != 'done'])

    recent_tasks = [t for t in my_tasks if t.get('status') != 'done']
    max_dt = datetime.max.replace(tzinfo=timezone.utc)
    recent_tasks.sort(key=lambda x: (x.get('due_date') or max_dt, x.get('created_at') or max_dt))
    recent_tasks = recent_tasks[:5]

    for task in recent_tasks:
        project = all_projects.get(task['project_id'])
        task['project_name'] = project['name'] if project else 'Unknown'

    try:
        upcoming_events = FirebaseEvent.get_upcoming_by_user(current_user.id, datetime.now(timezone.utc))
    except Exception as e:
        print(f"Error fetching upcoming events: {e}")
        upcoming_events = []

    recent_projects_list = list(all_projects.values())[:4]
    for project in recent_projects_list:
        project['task_count'] = 0
        project['member_count'] = 1

    return jsonify({
        'stats': {
            'total_projects': total_projects,
            'total_tasks': my_tasks_count,
            'my_tasks': my_tasks_count,
            'completed_tasks': completed_tasks,
            'in_progress_tasks': in_progress_tasks,
            'overdue_tasks': overdue_tasks
        },
        'recent_tasks': [format_task(t) for t in recent_tasks],
        'upcoming_events': [format_event(e) for e in upcoming_events],
        'recent_projects': recent_projects_list
    })


@dashboard_bp.route('/api/dashboard/all-tasks', methods=['GET'])
@login_required
def get_dashboard_all_tasks():
    """Get all tasks from user's projects for dashboard"""
    all_tasks = get_user_all_tasks(current_user.id)

    for task in all_tasks:
        project = FirebaseProject.get_by_id(task['project_id'])
        task['project_name'] = project['name'] if project else 'Unknown'

    all_tasks.sort(key=lambda x: x.get('updated_at', datetime.min), reverse=True)

    return jsonify([format_task(t) for t in all_tasks])


@dashboard_bp.route('/api/dashboard/all-projects', methods=['GET'])
@login_required
def get_dashboard_all_projects():
    """Get all projects with detailed stats for dashboard"""
    owned_projects = FirebaseProject.get_by_owner(current_user.id)
    member_records = FirebaseProjectMember.get_by_user(current_user.id)

    member_project_ids = [m['project_id'] for m in member_records]
    member_projects = [FirebaseProject.get_by_id(pid) for pid in member_project_ids]
    member_projects = [p for p in member_projects if p]

    all_projects = []

    for project in owned_projects:
        tasks = FirebaseTask.get_by_project(project['id'])
        members = FirebaseProjectMember.get_by_project(project['id'])
        project['is_owner'] = True
        project['task_count'] = len(tasks)
        project['member_count'] = len(members) + 1
        project['completed_tasks'] = len([t for t in tasks if t.get('status') == 'done'])
        project['in_progress_tasks'] = len([t for t in tasks if t.get('status') == 'in_progress'])
        all_projects.append(project)

    for project in member_projects:
        tasks = FirebaseTask.get_by_project(project['id'])
        members = FirebaseProjectMember.get_by_project(project['id'])
        user_membership = next((m for m in member_records if m['project_id'] == project['id']), None)
        user_role = user_membership.get('role', 'member') if user_membership else 'member'
        project['is_owner'] = False
        project['is_admin'] = user_role == 'admin'
        project['user_role'] = user_role
        project['task_count'] = len(tasks)
        project['member_count'] = len(members) + 1
        project['completed_tasks'] = len([t for t in tasks if t.get('status') == 'done'])
        project['in_progress_tasks'] = len([t for t in tasks if t.get('status') == 'in_progress'])
        all_projects.append(project)

    return jsonify(all_projects)


@dashboard_bp.route('/profile')
@login_required
def profile():
    """Show user profile page"""
    return render_template('profile.html')


@dashboard_bp.route('/api/profile', methods=['GET'])
@login_required
def get_profile():
    """Get current user profile"""
    user_data = FirebaseUser.get_by_id(current_user.id)
    return jsonify({
        'id': user_data['id'],
        'username': user_data.get('username', ''),
        'email': user_data.get('email', ''),
        'full_name': user_data.get('full_name', ''),
        'created_at': user_data.get('created_at', datetime.utcnow()).isoformat()
    })


@dashboard_bp.route('/api/profile', methods=['PUT'])
@login_required
def update_profile():
    """Update user profile"""
    data = request.json

    if 'username' in data:
        existing = FirebaseUser.get_by_username(data['username'])
        if existing and existing['id'] != current_user.id:
            return jsonify({'error': 'Username already taken'}), 400

    if 'email' in data:
        existing = FirebaseUser.get_by_email(data['email'])
        if existing and existing['id'] != current_user.id:
            return jsonify({'error': 'Email already registered'}), 400

    update_data = {}
    if 'username' in data:
        update_data['username'] = data['username']
    if 'email' in data:
        update_data['email'] = data['email']
    if 'full_name' in data:
        update_data['full_name'] = data['full_name']

    FirebaseUser.update(current_user.id, update_data)

    user_data = FirebaseUser.get_by_id(current_user.id)
    return jsonify({
        'id': user_data['id'],
        'username': user_data.get('username', ''),
        'email': user_data.get('email', ''),
        'full_name': user_data.get('full_name', ''),
        'created_at': user_data.get('created_at', datetime.utcnow()).isoformat()
    })


@dashboard_bp.route('/api/profile/password', methods=['PUT'])
@login_required
def change_password():
    """Change user password"""
    data = request.json
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not current_password or not new_password:
        return jsonify({'error': 'Both current and new password are required'}), 400

    if not current_user.check_password(current_password):
        return jsonify({'error': 'Current password is incorrect'}), 400

    if len(new_password) < 6:
        return jsonify({'error': 'New password must be at least 6 characters'}), 400

    FirebaseUser.set_password(current_user.id, new_password)
    return jsonify({'message': 'Password changed successfully'})


@dashboard_bp.route('/reports')
@login_required
def reports():
    """Show reports page"""
    return render_template('reports.html')


@dashboard_bp.route('/api/reports/user-stats', methods=['GET'])
@login_required
def get_user_stats():
    """Get user statistics for reports"""
    tasks = FirebaseTask.get_by_assigned_user(current_user.id)
    owned_projects = FirebaseProject.get_by_owner(current_user.id)
    member_records = FirebaseProjectMember.get_by_user(current_user.id)

    completed_tasks = len([t for t in tasks if t.get('status') == 'done'])
    in_progress_tasks = len([t for t in tasks if t.get('status') == 'in_progress'])
    todo_tasks = len([t for t in tasks if t.get('status') == 'todo'])
    on_hold_tasks = len([t for t in tasks if t.get('status') == 'on_hold'])
    total_tasks = len(tasks)
    overdue_tasks = len([t for t in tasks if t.get('due_date') and t['due_date'] < datetime.now(timezone.utc) and t.get('status') != 'done'])

    active_tasks = [t for t in tasks if t.get('status') != 'done']
    high_priority = len([t for t in active_tasks if t.get('priority') == 'high'])
    medium_priority = len([t for t in active_tasks if t.get('priority') == 'medium'])
    low_priority = len([t for t in active_tasks if t.get('priority') == 'low'])

    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

    owned_projects_count = len(owned_projects)
    member_projects_count = len(member_records)
    total_projects = owned_projects_count + member_projects_count

    return jsonify({
        'total_assigned': total_tasks,
        'completed': completed_tasks,
        'in_progress': in_progress_tasks,
        'todo': todo_tasks,
        'on_hold': on_hold_tasks,
        'overdue': overdue_tasks,
        'completion_rate': round(completion_rate, 1),
        'high_priority': high_priority,
        'medium_priority': medium_priority,
        'low_priority': low_priority,
        'owned_projects': owned_projects_count,
        'member_projects': member_projects_count,
        'total_projects': total_projects
    })


@dashboard_bp.route('/api/reports/attendance-stats', methods=['GET'])
@login_required
def get_attendance_stats():
    """Get attendance statistics for the current user for reports page"""
    now = datetime.now(timezone.utc)
    year  = int(request.args.get('year',  now.year))
    month = int(request.args.get('month', now.month))

    # Build month date range
    start = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    records = FirebaseAttendance.get_by_user_date_range(current_user.id, start, end - timedelta(seconds=1))

    present   = sum(1 for r in records if r.get('status') == 'present')
    half_day  = sum(1 for r in records if r.get('status') == 'half-day')
    absent    = sum(1 for r in records if r.get('status') in ('absent',) and not r.get('leave_type'))
    sick      = sum(1 for r in records if r.get('leave_type') == 'sick')
    casual    = sum(1 for r in records if r.get('leave_type') == 'casual')
    total_hours = sum((r.get('work_hours') or 0) for r in records)
    avg_hours = round(total_hours / present, 2) if present > 0 else 0

    # Count working days in the month (Mon–Sat) that have passed
    total_working_days = 0
    cursor = start
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    while cursor < end and cursor <= today:
        if cursor.weekday() < 6:  # Mon–Sat
            total_working_days += 1
        cursor += timedelta(days=1)

    attendance_rate = round((present + half_day * 0.5) / total_working_days * 100, 1) if total_working_days > 0 else 0

    # Last 6 months trend
    trend = []
    for i in range(5, -1, -1):
        m_date = (now.replace(day=1) - timedelta(days=i * 28)).replace(day=1)
        m_start = m_date.replace(hour=0, minute=0, second=0, microsecond=0)
        if m_date.month == 12:
            m_end = m_date.replace(year=m_date.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            m_end = m_date.replace(month=m_date.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
        m_recs = FirebaseAttendance.get_by_user_date_range(current_user.id, m_start, m_end - timedelta(seconds=1))
        m_present = sum(1 for r in m_recs if r.get('status') == 'present')
        m_half    = sum(1 for r in m_recs if r.get('status') == 'half-day')
        trend.append({
            'month': m_date.strftime('%b'),
            'present': m_present,
            'half_day': m_half
        })

    return jsonify({
        'present': present,
        'half_day': half_day,
        'absent': absent,
        'sick_leave': sick,
        'casual_leave': casual,
        'total_hours': round(total_hours, 1),
        'avg_hours_per_day': avg_hours,
        'working_days': total_working_days,
        'attendance_rate': attendance_rate,
        'trend': trend,
        'month': month,
        'year': year
    })
