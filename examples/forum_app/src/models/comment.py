from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

class Comment(db.Model):
    id = Column(Integer, primary_key=True)
    text = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    forum_post_id = Column(Integer, ForeignKey('forum_posts.id'), nullable=False)

    user = relationship("User", back_populates="comments")
    forum_post = relationship("ForumPost", back_populates="comments")