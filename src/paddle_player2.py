```python
class Player2Paddle:
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def move_up(self):
        self.y -= 5

    def move_down(self):
        self.y += 5

    def draw(self, screen):
        # This is a placeholder for drawing the paddle on the screen
        # Replace with your actual drawing code
        pygame.draw.rect(screen, (255, 255, 255), (self.x, self.y, self.width, self.height))
```