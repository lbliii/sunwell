```python
from dataclasses import dataclass
from typing import List

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

@dataclass
class Post:
    id: int
    title: str
    content: str
    author: str
    created_at: DateTime
    updated_at: DateTime
    likes: int
    comments: List['Comment'] = dataclasses.field(default_factory=list)

@dataclass
class Comment:
    id: int
    post_id: int
    author: str
    content: str
    created_at: DateTime
    updated_at: DateTime

@dataclass
class User:
    id: int
    username: str
    email: str
    posts: List['Post'] = dataclasses.field(default_factory=list)

class PostProtocol(Base):
    __tablename__ = 'posts'

    id = Column(Integer, primary_key=True)
    title = Column(String)
    content = Column(String)
    author = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    likes = Column(Integer)
    comments = Column(Integer, ForeignKey('comments.id'))
```
