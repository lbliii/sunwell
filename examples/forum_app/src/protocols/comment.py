from typing import Protocol, Any


class Comment(Protocol):
    def __init__(self, comment_text: str):
        self.TCommentText = comment_text

    @property
    def TCommentText(self) -> str:
        return self.__TCommentText

    @TCommentText.setter
    def TCommentText(self, value: str) -> None:
        if not isinstance(value, str)):
            raise TypeError('comment_text must be a string')
        self.__TCommentText = value


# Example usage of the Comment entity protocol
class UserComment(Comment):
    def __init__(self, comment_text: str, user_id: int):
        super().__init__(comment_text)
        self.user_id = user_id


# Example usage of the Protocol with a concrete class
class CommentEntity:
    def __init__(self, comment: Comment):
        self.comment = comment


# Example usage of the Protocol with a concrete class
class UserCommentEntity:
    def __init__(self, user_comment: UserComment):
        self.user_comment = user_comment