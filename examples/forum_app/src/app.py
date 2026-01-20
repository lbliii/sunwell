"""Forum App - Main Flask Application

A simple forum with posts, comments, users, and upvotes.
"""
from flask import Flask, render_template_string
from flask_sqlalchemy import SQLAlchemy
import os

# Initialize extensions
db = SQLAlchemy()

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = 'dev-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(
        os.path.dirname(__file__), 'forum.db'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions with app
    db.init_app(app)
    
    # Import and register blueprints
    from routes.posts import posts_bp
    from routes.users import users_bp
    from routes.comments import comments_bp
    from routes.upvotes import upvotes_bp
    
    app.register_blueprint(posts_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(comments_bp)
    app.register_blueprint(upvotes_bp)
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    # Home page route
    @app.route('/')
    def home():
        from models.post import Post
        from models.user import User
        posts = Post.query.order_by(Post.created_at.desc()).all()
        return render_template_string(HOME_TEMPLATE, posts=posts)
    
    return app

# Simple HTML template for the home page
HOME_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Forum App</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            line-height: 1.6;
            padding: 2rem;
        }
        .container { max-width: 800px; margin: 0 auto; }
        h1 { 
            color: #58a6ff; 
            margin-bottom: 1.5rem;
            font-size: 2rem;
        }
        .new-post {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }
        .new-post h2 { 
            color: #c9d1d9; 
            font-size: 1rem;
            margin-bottom: 1rem;
        }
        input, textarea {
            width: 100%;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 0.75rem;
            color: #c9d1d9;
            font-size: 1rem;
            margin-bottom: 0.75rem;
        }
        input:focus, textarea:focus {
            outline: none;
            border-color: #58a6ff;
        }
        textarea { min-height: 100px; resize: vertical; }
        button {
            background: #238636;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 0.75rem 1.5rem;
            font-size: 1rem;
            cursor: pointer;
            transition: background 0.2s;
        }
        button:hover { background: #2ea043; }
        .posts { display: flex; flex-direction: column; gap: 1rem; }
        .post {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 1.5rem;
        }
        .post-title {
            color: #58a6ff;
            font-size: 1.25rem;
            margin-bottom: 0.5rem;
        }
        .post-meta {
            color: #8b949e;
            font-size: 0.875rem;
            margin-bottom: 0.75rem;
        }
        .post-content { color: #c9d1d9; }
        .post-actions {
            display: flex;
            gap: 1rem;
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 1px solid #30363d;
        }
        .action-btn {
            background: transparent;
            color: #8b949e;
            padding: 0.5rem;
            font-size: 0.875rem;
        }
        .action-btn:hover { color: #c9d1d9; background: #30363d; }
        .empty {
            text-align: center;
            color: #8b949e;
            padding: 3rem;
        }
        .success {
            background: #238636;
            color: white;
            padding: 1rem;
            border-radius: 6px;
            margin-bottom: 1rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🗣️ Forum</h1>
        
        <div class="new-post">
            <h2>Create a new post</h2>
            <form id="postForm">
                <input type="text" id="title" placeholder="Post title" required>
                <textarea id="content" placeholder="What's on your mind?" required></textarea>
                <button type="submit">Post</button>
            </form>
        </div>
        
        <div class="posts">
            {% if posts %}
                {% for post in posts %}
                <div class="post">
                    <h3 class="post-title">{{ post.title }}</h3>
                    <div class="post-meta">
                        Posted by {{ post.author.username if post.author else 'Anonymous' }} 
                        · {{ post.upvote_count }} upvotes
                    </div>
                    <p class="post-content">{{ post.content }}</p>
                    <div class="post-actions">
                        <button class="action-btn" onclick="upvote({{ post.id }})">👍 Upvote</button>
                        <button class="action-btn" onclick="showComments({{ post.id }})">💬 Comments</button>
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <div class="empty">
                    <p>No posts yet. Be the first to post!</p>
                </div>
            {% endif %}
        </div>
    </div>
    
    <script>
        document.getElementById('postForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const title = document.getElementById('title').value;
            const content = document.getElementById('content').value;
            
            const response = await fetch('/posts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, content })
            });
            
            if (response.ok) {
                window.location.reload();
            }
        });
        
        async function upvote(postId) {
            await fetch(`/upvotes/post/${postId}`, { method: 'POST' });
            window.location.reload();
        }
        
        function showComments(postId) {
            alert('Comments feature coming soon!');
        }
    </script>
</body>
</html>
'''

# Run the app
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
