"""Routes package - exports all blueprints."""
from routes.posts import posts_bp
from routes.users import users_bp
from routes.comments import comments_bp
from routes.upvotes import upvotes_bp

__all__ = ['posts_bp', 'users_bp', 'comments_bp', 'upvotes_bp']
