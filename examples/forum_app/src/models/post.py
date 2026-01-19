from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

class Post(Base):
    __tablename__ = 'posts'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(100))
    content = Column(String(500))
    author_id = Column(Integer, ForeignKey('users.id'))
    author = relationship('User', back_populates='posts')