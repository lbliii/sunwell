```python
from dataclasses import dataclass
from typing import List

@dataclass
class Post:
    id: int
    title: str
    content: str
    author: str
    created_at: str
    updated_at: str
    likes: int
    comments: List[str]

@dataclass
class User:
    id: int
    username: str
    email: str
    posts: List[Post]
```
