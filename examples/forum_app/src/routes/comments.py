"""Comments routes - Create, read, update, delete comments."""
from flask import Blueprint, request, jsonify
from app import db
from models.comment import Comment
from models.post import Post

comments_bp = Blueprint('comments', __name__)


@comments_bp.route('/posts/<int:post_id>/comments', methods=['POST'])
def create_comment(post_id):
    """Create a new comment on a post."""
    # Verify post exists
    Post.query.get_or_404(post_id)
    
    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify({'error': 'Content is required'}), 400
    
    comment = Comment(
        content=data['content'],
        post_id=post_id,
        user_id=data.get('user_id')
    )
    db.session.add(comment)
    db.session.commit()
    
    return jsonify(comment.to_dict()), 201


@comments_bp.route('/posts/<int:post_id>/comments', methods=['GET'])
def get_comments(post_id):
    """Get all comments for a post."""
    # Verify post exists
    Post.query.get_or_404(post_id)
    
    comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at).all()
    return jsonify([comment.to_dict() for comment in comments])


@comments_bp.route('/comments/<int:comment_id>', methods=['GET'])
def get_comment(comment_id):
    """Get a single comment by ID."""
    comment = Comment.query.get_or_404(comment_id)
    return jsonify(comment.to_dict())


@comments_bp.route('/comments/<int:comment_id>', methods=['PUT'])
def update_comment(comment_id):
    """Update a comment."""
    comment = Comment.query.get_or_404(comment_id)
    data = request.get_json()
    
    if 'content' in data:
        comment.content = data['content']
    
    db.session.commit()
    return jsonify(comment.to_dict())


@comments_bp.route('/comments/<int:comment_id>', methods=['DELETE'])
def delete_comment(comment_id):
    """Delete a comment."""
    comment = Comment.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()
    return jsonify({'message': 'Comment deleted successfully'})
