"""Task routes - Wave 3 artifact.

Signal analysis: complexity=MAYBE, tools=YES
Code review: 🟡 warm (standard CRUD, false positive per triage)
Strain triage: "Standard CRUD operations...inherently safe"
"""

from flask import Blueprint, request, jsonify
from models import Task, db

tasks_bp = Blueprint('tasks', __name__)


@tasks_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """List all tasks."""
    tasks = Task.query.order_by(Task.created_at.desc()).all()
    return jsonify([t.to_dict() for t in tasks])


@tasks_bp.route('/tasks', methods=['POST'])
def add_task():
    """Add a new task."""
    data = request.get_json()
    
    if not data or 'description' not in data:
        return jsonify({'error': 'description required'}), 400
    
    task = Task(description=data['description'])
    db.session.add(task)
    db.session.commit()
    
    return jsonify(task.to_dict()), 201


@tasks_bp.route('/tasks/<int:task_id>', methods=['PUT'])
def complete_task(task_id: int):
    """Mark a task as completed."""
    task = Task.query.get_or_404(task_id)
    task.completed = True
    db.session.commit()
    
    return jsonify(task.to_dict())


@tasks_bp.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id: int):
    """Delete a task."""
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    
    return jsonify({'deleted': True, 'id': task_id})
