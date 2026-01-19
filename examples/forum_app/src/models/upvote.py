from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from typing import Optional

class User:
    id = Column(Integer, primary_key=True)
    username = Column(String)

class UpvoteProtocol:
    def __init__(self, user_id: int):
        self.user_id = user_id

    @classmethod
    def from_user(cls, user: User) -> 'Upvote':
        return cls(user.id)

    def to_dict(self) -> dict:
        return {'user_id': self.user_id}

class Upvote:
    __tablename__ = 'upvotes'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    upvoted_by = relationship("User", back_populates="upvotes")

    def __init__(self, user_id: int):
        self.user_id = user_id

    @classmethod
    def from_user(cls, user: User) -> 'Upvote':
        return cls(user.id)

    def to_dict(self) -> dict:
        return {'user_id': self.user_id}