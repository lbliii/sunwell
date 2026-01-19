from typing import Optional

class Post:
    def __init__(self, title: str, content: str):
        self.TITLE = title
        self.CONTENT = content

    @staticmethod
    def from_dict(data: dict) -> Optional['Post']:
        if 'title' not in data or 'content' not in data:
            return None
        return Post(title=data['title']), content=data['content'])