```python
def display_scores(scores):
    """Displays the scores for each player.

    Args:
        scores: A dictionary where keys are player names and values are their scores.
    """
    for player, score in scores.items():
        print(f"{player}: {score}")

if __name__ == '__main__':
    player_scores = {"Alice": 85, "Bob": 92, "Charlie": 78, "David": 95}
    display_scores(player_scores)
```
