```python
from dataclasses import dataclass
from typing import List
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import DeclarativeBase
from sqlalchemy import select

class Base(DeclarativeBase):
    pass

@dataclass
class Comment(Base):
    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, index=True)
    author = Column(String)
    content = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    def to_dict(self):
        return {
            'id': self.id,
            'post_id': self.post_id,
            'author': self.author,
            'content': self.content,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

@dataclass
class PostProtocol(Base):
    id = Column(Integer, primary_key=True)
    title = Column(String)
    content = Column(String)
    author = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'author': self.author,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'likes': self.likes,
            'comments': self.comments
        }

class AuthenticationService:
    def __init__(self, secret_key):
        self.secret_key = secret_key

    def generate_token(self, user_id):
        import jwt
        payload = {
            'user_id': user_id,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + datetime.timedelta(minutes=30)
        }
        token = jwt.encode(payload, self.secret_key, algorithm='HS256')
        return token

    def verify_token(self, token):
        import jwt
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidSignatureError:
            return None

import datetime
if __name__ == '__main__':
    auth_service = AuthenticationService(secret_key='mysecret')
    token = auth_service.generate_token(123)
    print(token)
    payload = auth_service.verify_token(token)
    print(payload)
```