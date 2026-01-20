"""Posts routes - Create, read, update, delete posts."""
from flask import Blueprint, request, jsonify
from app import db
from models.post import Post

posts_bp = Blueprint('posts', __name__)


@posts_bp.route('/posts', methods=['POST'])
def create_post():
    """Create a new post."""
    data = request.get_json()
    if not data or 'title' not in data or 'content' not in data:
        return jsonify({'error': 'Title and content are required'}), 400
    
    post = Post(
        title=data['title'],
        content=data['content'],
        user_id=data.get('user_id')
    )
    db.session.add(post)
    db.session.commit()
    
    return jsonify(post.to_dict()), 201


@posts_bp.route('/posts', methods=['GET'])
def get_posts():
    """Get all posts."""
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return jsonify([post.to_dict() for post in posts])


@posts_bp.route('/posts/<int:post_id>', methods=['GET'])
def get_post(post_id):
    """Get a single post by ID."""
    post = Post.query.get_or_404(post_id)
    return jsonify(post.to_dict())


@posts_bp.route('/posts/<int:post_id>', methods=['PUT'])
def update_post(post_id):
    """Update a post."""
    post = Post.query.get_or_404(post_id)
    data = request.get_json()
    
    if 'title' in data:
        post.title = data['title']
    if 'content' in data:
        post.content = data['content']
    
    db.session.commit()
    return jsonify(post.to_dict())


@posts_bp.route('/posts/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    """Delete a post."""
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    return jsonify({'message': 'Post deleted successfully'})
