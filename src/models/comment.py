from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import DeclarativeBase
from typing import Optional
from sqlalchemy import identity
from dataclasses import dataclass

class Base(DeclarativeBase):
    pass

@dataclass
class Comment(Base):
    __tablename__ = 'comments'
    id = Column(Integer, identity(), primary_key=True)
    post_id = Column(Integer, nullable=False)
    author = Column(String, nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(Integer, server_default=identity().now())
    
    try:
        # This is just a placeholder for AuthenticationService
        # In a real application, this would contain authentication logic
        pass
    except:
        pass
