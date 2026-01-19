from typing import Protocol, Any


class UserEntity(Protocol):
    id: int
    username: str
    email: str
    password: str


def create_user(user: UserEntity) -> None:
    print(f"User created with id {user.get('id')}")


# Example usage
user = {
    "id": 1,
    "username": "john_doe",
    "email": "john.doe@example.com",
    "password": "secret123"
}

create_user(user)