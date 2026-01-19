"""Flask application - Wave 4 artifact.

Signal analysis: complexity=MAYBE, tools=YES
Code review: ✅ clean

Built using Sunwell's signal-guided generation:
1. Artifact discovery → 4 components in dependency order
2. Signal analysis per artifact → complexity routing
3. Code generation with medium model
4. Code review with tiny model → flagged potential issues
5. Strain triage with medium model → filtered false positives
"""

from flask import Flask
from models import db, Task
from routes import tasks_bp


def create_app() -> Flask:
    """Application factory."""
    app = Flask(__name__)
    
    # Configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todos.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions
    db.init_app(app)
    
    # Register blueprints
    app.register_blueprint(tasks_bp)
    
    # Create tables
    with app.app_context():
        db.create_all()
    
    return app


if __name__ == '__main__':
    app = create_app()
    print("Todo API running at http://localhost:5000")
    print("  GET  /tasks       - List all tasks")
    print("  POST /tasks       - Add task (JSON: {description: '...'})")
    print("  PUT  /tasks/<id>  - Complete task")
    print("  DELETE /tasks/<id> - Delete task")
    app.run(debug=True)
