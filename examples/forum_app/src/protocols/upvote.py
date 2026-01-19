from typing import Protocol, Any


class UpvoteEntity(Protocol):
    def __init__(self) -> None: ...

    def upvote(self) -> "UpvoteEntity": ...


upvote_entity: UpvoteEntity = UpvoteEntity()
print(f"Upvote entity created: {upvote_entity}")