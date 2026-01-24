```python
import pygame

# Initialize Pygame
pygame.init()

# Screen dimensions
width = 800
height = 600

# Colors
black = (0, 0, 0)
white = (255, 255, 255)
red = (255, 0, 0)
green = (0, 255, 0)
blue = (0, 0, 255)

# Create the screen
screen = pygame.display.set_mode((width, height))
pygame.display.set_caption("Game Elements")

# --- Game Element Handles ---

# Player Rectangle
player_handle = pygame.Rect(width // 2 - 50, height // 2 - 30, 100, 60)

# Ball Circle
ball_handle = pygame.Rect(width // 2 - 20, height // 2 - 20, 40, 40)

# Paddle Rectangle
paddle_handle = pygame.Rect(width // 4, height // 2 - 20, 10, 60)

# --- Game Loop ---
running = True
clock = pygame.time.Clock()

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # --- Update Game Logic ---
    # (Implement your game logic here - movement, collisions, etc.)

    # --- Draw Game Elements ---
    screen.fill(black)  # Clear the screen

    # Draw Player Rectangle
    pygame.draw.rect(screen, red, player_handle)

    # Draw Ball Circle
    pygame.draw.circle(screen, green, (width // 2, height // 2), 20)

    # Draw Paddle Rectangle
    pygame.draw.rect(screen, blue, paddle_handle)

    # Update the display
    pygame.display.flip()

    # Control the frame rate
    clock.tick(60)

# Quit Pygame
pygame.quit()
```
