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
    comments: List['Comment']

@dataclass
class Comment:
    id: int
    post_id: int
    author: str
    content: str
    created_at: str
    updated_at: str
```
