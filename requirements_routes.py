"""
Requirements Routes Blueprint
Handles all requirement-related API endpoints for both team and client portals
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from firebase_models import (
    FirebaseRequirement, FirebaseProject, FirebaseProjectMember,
    FirebaseClientProjectAccess, FirebaseNotification, FirebaseUser,
    FirebaseClient
)
from datetime import datetime, timezone

requirements_bp = Blueprint('requirements', __name__)


# ---- Helper functions (duplicated to avoid circular imports) ----

def _is_client_user():
    """Check if current user is a client"""
    return hasattr(current_user, 'is_client') and current_user.is_client


def _has_project_access(project_id):
    """Check if current user has access to a project (team user)"""
    project = FirebaseProject.get_by_id(project_id)
    if not project:
        return False
    if project.get('owner_id') == current_user.id:
        return True
    member = FirebaseProjectMember.get_by_project_and_user(project_id, current_user.id)
    return member is not None


def _format_requirement(req):
    """Format requirement for JSON response"""
    created_at = req.get('created_at')
    fulfilled_at = req.get('fulfilled_at')
    updated_at = req.get('updated_at')

    # Get creator name
    creator_name = 'Unknown'
    created_by = req.get('created_by')
    if created_by:
        user = FirebaseUser.get_by_id(created_by)
        if user:
            creator_name = user.get('username', 'Unknown')

    # Get fulfiller name
    fulfiller_name = None
    fulfilled_by = req.get('fulfilled_by')
    if fulfilled_by:
        client = FirebaseClient.get_by_id(fulfilled_by)
        if client:
            fulfiller_name = client.get('name', 'Unknown')
        else:
            user = FirebaseUser.get_by_id(fulfilled_by)
            if user:
                fulfiller_name = user.get('username', 'Unknown')

    return {
        'id': req.get('id'),
        'project_id': req.get('project_id'),
        'title': req.get('title', ''),
        'description': req.get('description', ''),
        'priority': req.get('priority', 'medium'),
        'status': req.get('status', 'pending'),
        'created_by': created_by,
        'creator_name': creator_name,
        'created_at': created_at.isoformat() if created_at else None,
        'updated_at': updated_at.isoformat() if updated_at else None,
        'fulfilled_at': fulfilled_at.isoformat() if fulfilled_at else None,
        'fulfilled_by': fulfilled_by,
        'fulfiller_name': fulfiller_name
    }


# ============= Team-side endpoints =============

@requirements_bp.route('/api/projects/<project_id>/requirements', methods=['GET'])
@login_required
def get_requirements(project_id):
    """Get all requirements for a project (team view)"""
    if _is_client_user():
        return jsonify({'error': 'Access denied'}), 403
    if not _has_project_access(project_id):
        return jsonify({'error': 'Access denied'}), 403

    try:
        requirements = FirebaseRequirement.get_by_project(project_id)
        return jsonify([_format_requirement(r) for r in requirements])
    except Exception as e:
        print(f"Error fetching requirements: {e}")
        return jsonify([])


@requirements_bp.route('/api/projects/<project_id>/requirements', methods=['POST'])
@login_required
def create_requirement(project_id):
    """Create a new requirement"""
    if _is_client_user():
        return jsonify({'error': 'Access denied'}), 403
    if not _has_project_access(project_id):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'error': 'Title is required'}), 400

    priority = data.get('priority', 'medium')
    if priority not in ('low', 'medium', 'high'):
        priority = 'medium'

    req_id = FirebaseRequirement.create(
        project_id=project_id,
        title=title,
        description=data.get('description', ''),
        priority=priority,
        created_by=current_user.id
    )

    requirement = FirebaseRequirement.get_by_id(req_id)
    return jsonify(_format_requirement(requirement)), 201


@requirements_bp.route('/api/requirements/<req_id>', methods=['PUT'])
@login_required
def update_requirement(req_id):
    """Update a requirement (team only)"""
    if _is_client_user():
        return jsonify({'error': 'Access denied'}), 403

    requirement = FirebaseRequirement.get_by_id(req_id)
    if not requirement:
        return jsonify({'error': 'Requirement not found'}), 404

    if not _has_project_access(requirement['project_id']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    update_data = {}

    if 'title' in data:
        update_data['title'] = data['title']
    if 'description' in data:
        update_data['description'] = data['description']
    if 'priority' in data and data['priority'] in ('low', 'medium', 'high'):
        update_data['priority'] = data['priority']
    if 'status' in data and data['status'] in ('pending', 'fulfilled'):
        update_data['status'] = data['status']
        if data['status'] == 'pending':
            update_data['fulfilled_at'] = None
            update_data['fulfilled_by'] = None

    if update_data:
        FirebaseRequirement.update(req_id, update_data)

    updated = FirebaseRequirement.get_by_id(req_id)
    return jsonify(_format_requirement(updated))


@requirements_bp.route('/api/requirements/<req_id>', methods=['DELETE'])
@login_required
def delete_requirement(req_id):
    """Delete a requirement (team only)"""
    if _is_client_user():
        return jsonify({'error': 'Access denied'}), 403

    requirement = FirebaseRequirement.get_by_id(req_id)
    if not requirement:
        return jsonify({'error': 'Requirement not found'}), 404

    if not _has_project_access(requirement['project_id']):
        return jsonify({'error': 'Access denied'}), 403

    FirebaseRequirement.delete(req_id)
    return jsonify({'message': 'Requirement deleted successfully'})


# ============= Client-side endpoints =============

@requirements_bp.route('/api/client/projects/<project_id>/requirements', methods=['GET'])
@login_required
def get_client_requirements(project_id):
    """Get requirements for a project (client view)"""
    if not _is_client_user():
        return jsonify({'error': 'Access denied'}), 403

    client_id = current_user.id
    access = FirebaseClientProjectAccess.get_by_client_and_project(client_id, project_id)
    if not access:
        return jsonify({'error': 'Access denied'}), 403

    try:
        requirements = FirebaseRequirement.get_by_project(project_id)
        return jsonify([_format_requirement(r) for r in requirements])
    except Exception as e:
        print(f"Error fetching client requirements: {e}")
        return jsonify([])


@requirements_bp.route('/api/client/requirements/<req_id>/fulfill', methods=['PUT'])
@login_required
def fulfill_requirement(req_id):
    """Client marks a requirement as fulfilled"""
    if not _is_client_user():
        return jsonify({'error': 'Access denied'}), 403

    requirement = FirebaseRequirement.get_by_id(req_id)
    if not requirement:
        return jsonify({'error': 'Requirement not found'}), 404

    client_id = current_user.id
    access = FirebaseClientProjectAccess.get_by_client_and_project(
        client_id, requirement['project_id']
    )
    if not access:
        return jsonify({'error': 'Access denied'}), 403

    FirebaseRequirement.fulfill(req_id, fulfilled_by=client_id)

    # Notify the requirement creator
    try:
        project = FirebaseProject.get_by_id(requirement['project_id'])
        project_name = project['name'] if project else 'Unknown'
        FirebaseNotification.create(
            user_id=requirement['created_by'],
            notification_type='requirement_fulfilled',
            title='Requirement Fulfilled',
            message=f'Client {current_user.name} marked "{requirement["title"]}" as fulfilled in {project_name}',
            link=f'/project/{requirement["project_id"]}/dashboard',
            related_id=req_id
        )
    except Exception as e:
        print(f"Error creating requirement notification: {e}")

    updated = FirebaseRequirement.get_by_id(req_id)
    return jsonify(_format_requirement(updated))
