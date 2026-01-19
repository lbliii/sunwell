from sqlalchemy import Column, Integer, ForeignKey, Boolean
from sqlalchemy.orm import relationship

class ForumUpvote(Base):
    __tablename__ = 'forum_upvotes'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    forum_post_id = Column(Integer, ForeignKey('forum_posts.id'), nullable=False)

    user = relationship("User", back_populates="upvotes")
    forum_post = relationship("ForumPost", back_populates="upvotes")

    def __repr__(self):
        return f"ForumUpvote(user_id={self.user_id}, forum_post_id={self.forum_post_id})"