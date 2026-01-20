"""Upvotes routes - Upvote and remove upvote from posts."""
from flask import Blueprint, request, jsonify
from app import db
from models.upvote import Upvote
from models.post import Post

upvotes_bp = Blueprint('upvotes', __name__)


@upvotes_bp.route('/upvotes/post/<int:post_id>', methods=['POST'])
def upvote_post(post_id):
    """Upvote a post."""
    post = Post.query.get_or_404(post_id)
    data = request.get_json() or {}
    user_id = data.get('user_id')
    
    # Check if already upvoted (if user_id provided)
    if user_id:
        existing = Upvote.query.filter_by(user_id=user_id, post_id=post_id).first()
        if existing:
            return jsonify({'error': 'Already upvoted'}), 400
    
    upvote = Upvote(
        post_id=post_id,
        user_id=user_id
    )
    db.session.add(upvote)
    
    # Increment post upvote count
    post.upvote_count += 1
    db.session.commit()
    
    return jsonify({
        'message': 'Upvoted successfully',
        'upvote_count': post.upvote_count
    }), 201


@upvotes_bp.route('/upvotes/post/<int:post_id>', methods=['DELETE'])
def remove_upvote(post_id):
    """Remove upvote from a post."""
    post = Post.query.get_or_404(post_id)
    data = request.get_json() or {}
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400
    
    upvote = Upvote.query.filter_by(user_id=user_id, post_id=post_id).first()
    if not upvote:
        return jsonify({'error': 'No upvote found'}), 404
    
    db.session.delete(upvote)
    
    # Decrement post upvote count
    post.upvote_count = max(0, post.upvote_count - 1)
    db.session.commit()
    
    return jsonify({
        'message': 'Upvote removed',
        'upvote_count': post.upvote_count
    })


@upvotes_bp.route('/upvotes/post/<int:post_id>', methods=['GET'])
def get_upvotes(post_id):
    """Get upvote count for a post."""
    post = Post.query.get_or_404(post_id)
    return jsonify({
        'post_id': post_id,
        'upvote_count': post.upvote_count
    })
