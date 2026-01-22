# Getting Started with the Pokémon API (PokeAPI) in Python

> **TL;DR** – The Pokémon API is a free, public REST API that gives you structured data about Pokémon, moves, abilities, types, and more.  
> Use the `requests` library to fetch JSON, then parse it into Python objects.  
> Below you’ll find a quick‑start guide, a practical “get a Pokémon’s stats” example, and a list of common pitfalls to avoid.

---

## 1. What the API Offers

| Category | What you can query | Example endpoint |
|----------|--------------------|------------------|
| Pokémon | Name, ID, stats, types, abilities, moves, sprites, etc. | `/pokemon/{id|name}/` |
| Types | Type names, damage relations | `/type/{id|name}/` |
| Abilities | Ability descriptions, effect changes | `/ability/{id|name}/` |
| Moves | Power, accuracy, PP, target | `/move/{id|name}/` |
| Game data | Versions, generations, regions | `/generation/{id|name}/` |
| **Other** | Items, contests, locations, etc. | `/item/{id|name}/`, `/location/{id|name}/` |

> **Key take‑away:** Everything is represented as a JSON object. If you’re comfortable with Python dictionaries, you’re already halfway there.

---

## 2. Making Requests

### 2.1. Setup

```bash
pip install requests
```

```python
import requests

BASE_URL = "https://pokeapi.co/api/v2"
```

### 2.2. Helper Function

A small wrapper keeps our code DRY and adds basic error handling:

```python
def get_json(endpoint: str) -> dict:
    """
    Fetch JSON data from the PokeAPI.
    
    :param endpoint: API path, e.g. "/pokemon/pikachu"
    :return: Parsed JSON as a Python dict
    :raises HTTPError: If the request fails
    """
    url = f"{BASE_URL}{endpoint}"
    response = requests.get(url, timeout=10)
    if response.status_code == 404:
        raise ValueError(f"Resource not found: {url}")
    response.raise_for_status()  # Raises for 4xx/5xx
    return response.json()
```

> **Why a helper?**  
> * Centralizes URL building.  
> * Handles timeouts and HTTP errors.  
> * Makes testing and future changes (e.g., adding auth headers) easier.

---

## 3. Practical Example – Get a Pokémon’s Stats

Let’s fetch **Pikachu** and print its base stats (HP, Attack, Defense, Speed, etc.).

```python
def print_pokemon_stats(name: str) -> None:
    data = get_json(f"/pokemon/{name.lower()}")
    
    print(f"--- {data['name'].title()} (ID: {data['id']}) ---")
    
    # Stats are a list of dicts; each has 'stat' (name) and 'base_stat' (value)
    for stat in data['stats']:
        stat_name = stat['stat']['name'].replace('-', ' ').title()
        base_stat = stat['base_stat']
        print(f"{stat_name:10}: {base_stat}")
    
    # Types
    types = ", ".join(t['type']['name'].title() for t in data['types'])
    print(f"Types: {types}")
    
    # Abilities (just names)
    abilities = ", ".join(a['ability']['name'].replace('-', ' ').title()
                          for a in data['abilities'])
    print(f"Abilities: {abilities}")
    
    # Sprites (the default front image)
    print(f"Sprite: {data['sprites']['front_default']}")
```

Run it:

```python
if __name__ == "__main__":
    print_pokemon_stats("pikachu")
```

**Sample output**

```
--- Pikachu (ID: 25) ---
Hp          : 35
Attack      : 55
Defense     : 40
Special-Atk : 50
Special-Def : 50
Speed       : 90
Types: Electric
Abilities: Static, Lightning-rod
Sprite: https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/25.png
```

> **What’s happening?**  
> 1. `get_json` fetches `/pokemon/pikachu`.  
> 2. The JSON payload contains nested objects: `stats` is a list, each with a `stat` sub‑object.  
> 3. We iterate, clean up names (replace dashes, title‑case), and print nicely.

---

## 4. Common Gotchas & How to Avoid Them

| Gotcha | Why it happens | Fix / Best practice |
|--------|----------------|---------------------|
| **Hit the rate limit** | PokeAPI allows ~100 requests per minute from a single IP. | Use `time.sleep()` between bursts, or cache responses locally (e.g., with `requests-cache`). |
| **Wrong endpoint casing** | URLs are case‑sensitive; `/Pokemon` ≠ `/pokemon`. | Always use lower‑case (`/pokemon/{name}`). |
| **Not handling 404s** | Trying to fetch a non‑existent Pokémon throws `requests.exceptions.HTTPError`. | Catch `ValueError` from `get_json` or check `status_code` before accessing `.json()`. |
| **Large payloads** | Some endpoints (e.g., `/pokemon/?limit=1000`) return thousands of items. | Use pagination (`?limit=20&offset=40`) or fetch only what you need. |
| **Network errors / timeouts** | Unstable internet or API downtime. | Wrap calls in `try/except` and retry with exponential backoff. |
| **JSON decoding errors** | API occasionally returns malformed JSON or a non‑JSON body. | Call `response.json()` inside a `try/except json.JSONDecodeError`. |
| **Using the wrong base URL** | Mixing `http://` and `https://` can cause redirects and slower responses. | Stick with `https://pokeapi.co/api/v2`. |
| **Ignoring API documentation** | Missing required query parameters or misusing endpoints. | Read the docs on https://pokeapi.co/docs/v2 or the online Swagger UI. |
| **Assuming field order** | JSON is an unordered dictionary; never rely on order. | Use keys explicitly (`data['stats']`, `data['name']`, etc.). |
| **Hardcoding IDs** | IDs change if the API evolves. | Use names (string) or fetch the list endpoint to discover IDs. |

---

## 5. Extending the Example

### 5.1. Fetch All Pokémon Names (Pagination)

```python
def list_all_pokemon(limit: int = 20) -> list[str]:
    names = []
    offset = 0
    while True:
        data = get_json(f"/pokemon?limit={limit}&offset={offset}")
        names.extend(p['name'] for p in data['results'])
        if not data['next']:
            break
        offset += limit
    return names

print(list_all_pokemon(10))
```

### 5.2. Convert to a Dataclass

```python
from dataclasses import dataclass
from typing import List

@dataclass
class Stat:
    name: str
    value: int

@dataclass
class Pokemon:
    id: int
    name: str
    stats: List[Stat]
    types: List[str]
    abilities: List[str]
    sprite: str

def parse_pokemon(data: dict) -> Pokemon:
    stats = [Stat(s['stat']['name'], s['base_stat']) for s in data['stats']]
    types = [t['type']['name'] for t in data['types']]
    abilities = [a['ability']['name'] for a in data['abilities']]
    return Pokemon(
        id=data['id'],
        name=data['name'],
        stats=stats,
        types=types,
        abilities=abilities,
        sprite=data['sprites']['front_default'],
    )
```

Now you can work with typed objects instead of raw dicts.

---

## 6. Final Checklist

- [ ] Install `requests`.
- [ ] Use a helper function for consistent error handling.
- [ ] Respect pagination; avoid hammering the API.
- [ ] Handle 404s and decoding errors gracefully.
- [ ] Optionally cache results to reduce network load.
- [ ] Read the official docs for endpoint details.

Happy poké‑coding! 🎮🐾