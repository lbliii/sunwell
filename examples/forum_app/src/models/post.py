from sqlalchemy.ext.declarative import declarative_base
from typing import Protocol

Base = declarative_base()

class Post(Protocol):
    id: int
    title: str
    content: str

class BlogPost(Base, Post):
    __tablename__ = 'blog_posts'
    id = Base.Column(Base.Integer, primary_key=True)
    title = Base.Column(Base.String(100), nullable=False)
    content = Base.Column(Base.Text(), nullable=False)