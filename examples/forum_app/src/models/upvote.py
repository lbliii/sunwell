"""Upvote model for the forum app."""
from datetime import datetime
from app import db


class Upvote(db.Model):
    """Upvote on a post."""
    __tablename__ = 'upvotes'
    
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    
    # Unique constraint: one upvote per user per post
    __table_args__ = (
        db.UniqueConstraint('user_id', 'post_id', name='unique_user_post_upvote'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'created_at': self.created_at.isoformat(),
            'user_id': self.user_id,
            'post_id': self.post_id
        }
