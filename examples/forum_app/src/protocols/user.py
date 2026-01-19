from typing import Optional

class User:
    def __init__(self, username: str, email: Optional[str] = None):
        self.user_name = username
        self.email = email

    def get_user(self):
        return {
            'username': self.user_name,
            'email': self.email
        }