# Import necessary libraries
from flask import Flask, request, jsonify, g
import sqlite3
import os

app = Flask(__name__)
DATABASE = os.path.join(os.path.dirname(__file__), 'posts.db')


def get_db():
    """Get database connection for current request."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    """Close database connection at end of request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    """Initialize the database."""
    with app.app_context():
        db = get_db()
        db.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL
            )
        ''')
        db.commit()


# POST endpoint for creating a new post
@app.route('/posts', methods=['POST'])
def create_post():
    data = request.get_json()
    if not data or 'title' not in data or 'content' not in data:
        return jsonify({'error': 'Invalid request'}), 400
    
    db = get_db()
    cursor = db.execute(
        'INSERT INTO posts (title, content) VALUES (?, ?)',
        (data['title'], data['content'])
    )
    db.commit()
    
    return jsonify({'id': cursor.lastrowid}), 201


# GET endpoint for retrieving all posts
@app.route('/posts', methods=['GET'])
def get_posts():
    db = get_db()
    posts = db.execute('SELECT * FROM posts').fetchall()
    
    if not posts:
        return jsonify([])
    
    return jsonify([{'id': p['id'], 'title': p['title'], 'content': p['content']} for p in posts])


# GET endpoint for retrieving a single post by ID
@app.route('/posts/<int:post_id>', methods=['GET'])
def get_post(post_id):
    db = get_db()
    post = db.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()
    
    if not post:
        return jsonify({'error': 'Post not found'}), 404
    
    return jsonify({'id': post['id'], 'title': post['title'], 'content': post['content']})


# PUT endpoint for updating a post
@app.route('/posts/<int:post_id>', methods=['PUT'])
def update_post(post_id):
    data = request.get_json()
    if not data or 'title' not in data or 'content' not in data:
        return jsonify({'error': 'Invalid request'}), 400
    
    db = get_db()
    db.execute(
        'UPDATE posts SET title = ?, content = ? WHERE id = ?',
        (data['title'], data['content'], post_id)
    )
    db.commit()
    
    return jsonify({'message': 'Post updated successfully'})


# DELETE endpoint for deleting a post
@app.route('/posts/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    db = get_db()
    cursor = db.execute('DELETE FROM posts WHERE id = ?', (post_id,))
    db.commit()
    
    if cursor.rowcount == 0:
        return jsonify({'error': 'Post not found'}), 404
    
    return jsonify({'message': 'Post deleted successfully'})


# Initialize DB on first import
init_db()