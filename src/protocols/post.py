```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class Post:
    id: Optional[int] = None
    title: str
    content: str
    author: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    likes: int = 0
    comments: list = []
```
