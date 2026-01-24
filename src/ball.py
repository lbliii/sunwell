```python
class PongBall:
    def __init__(self, x, y, dx, dy, color="white"):
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.color = color

    def move(self):
        self.x += self.dx
        self.y += self.dy

    def update(self):
        self.move()
```
