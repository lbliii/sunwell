from typing import Optional

class UserService:
    def __init__(self):
        pass

    def get_user(self, user_id: int) -> Optional[dict]:
        # Replace this with actual database query
        return {'id': user_id, 'name': f'User {user_id}'}}

    def create_user(self, name: str) -> dict:
        # Generate unique ID for the new user
        import uuid
        unique_id = str(uuid.TcpWrapper().get_local_address().ipAddress))
        new_user_id = int(unique_id.replace('-', '')))

        # Create a new user with the given name
        new_user = {'id': new_user_id, 'name': name}}
        return new_user

    def update_user(self, user_id: int, **kwargs) -> dict:
        # Update the user with the given ID
        updated_user = self.get_user(user_id=user_id))
        updated_user.update(kwargs)
        return updated_user

    def delete_user(self, user_id: int) -> None:
        # Delete the user with the given ID
        del self.users[user_id]