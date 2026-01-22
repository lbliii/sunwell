# Getting Started with the Pokémon API (PokeAPI) in Python

## Learning objectives
- Identify what data PokeAPI exposes and how it is organized.  
- Build a simple HTTP request to the API from Python.  
- Parse the JSON response and extract a Pokémon’s stats.  
- Spot and avoid the most common pitfalls when working with the API.

## Prerequisites
- Python 3.8 + installed.  
- `pip` available to install packages.  
- Basic familiarity with making HTTP requests in Python (e.g., `requests`).

## Guided steps

### 1. Install the `requests` library
```bash
pip install requests
```

### 2. Explore the API surface
PokeAPI is a RESTful service that follows a predictable URL scheme.  
All endpoints are prefixed by the base URL `https://pokeapi.co/api/v2/`.  
The most common collections include:

| Resource | Example endpoint |
|----------|------------------|
| Pokémon | `/pokemon/{name or id}` |
| Ability | `/ability/{name or id}` |
| Move    | `/move/{name or id}` |

*Reference:* `pokeapi.py:1-3`

```python
# pokeapi.py
BASE_URL = "https://pokeapi.co/api/v2/"
POKEMON_ENDPOINT = "pokemon/"
```

### 3. Build a request to fetch a Pokémon

```python
# poke_example.py:1-8
import requests

BASE_URL = "https://pokeapi.co/api/v2/"
POKEMON_ENDPOINT = "pokemon/"

def get_pokemon(name: str) -> dict:
    url = f"{BASE_URL}{POKEMON_ENDPOINT}{name.lower()}"
    response = requests.get(url)
    response.raise_for_status()          # throws for 4xx/5xx
    return response.json()

# Example: fetch Bulbasaur
bulbasaur = get_pokemon("bulbasaur")
```

- `response.raise_for_status()` ensures you get an exception for HTTP errors, preventing silent failures.  
- The returned object is a Python dictionary parsed from JSON.

### 4. Extract the stats

Every Pokémon object contains a `stats` list, each item holding a stat name and its base value.

```python
# poke_example.py:10-18
def print_stats(pokemon: dict) -> None:
    name = pokemon["name"].title()
    print(f"{name} base stats:")
    for stat_entry in pokemon["stats"]:
        stat_name = stat_entry["stat"]["name"].replace("-", " ").title()
        base_value = stat_entry["base_stat"]
        print(f"  {stat_name}: {base_value}")

print_stats(bulbasaur)
```

*Output example:*
```
Bulbasaur base stats:
  HP: 45
  Attack: 49
  Defense: 49
  Special Attack: 65
  Special Defense: 65
  Speed: 45
```

### 5. Run the script

```bash
python poke_example.py
```

You should see the stat table above.  
If you want another Pokémon, change the string in `get_pokemon("bulbasaur")` to the desired name or numeric ID.

## Expected outcomes
After completing these steps you will be able to:

- Call any PokeAPI endpoint by assembling the URL.  
- Handle HTTP errors gracefully.  
- Navigate the JSON structure to pull out specific data.  
- Display the data in a readable format.

## Common gotchas

| Issue | Why it happens | Fix |
|-------|----------------|-----|
| **404 Not Found** | Wrong Pokémon name or ID; case‑sensitive endpoint. | Use `name.lower()` or verify the spelling on the site. |
| **Rate limiting** | PokeAPI allows 100 requests per IP per minute. | Cache responses locally or add `time.sleep()` between rapid calls. |
| **Large payload** | Some endpoints return thousands of entries. | Use pagination (`?offset=0&limit=20`) or request only the needed endpoint. |
| **Network errors** | DNS, proxy, or firewall blocking `https://pokeapi.co`. | Check your network settings or try a different machine. |
| **JSON parsing errors** | Response is not JSON (e.g., HTML error page). | Verify the status code before `response.json()`. |

## Next steps
- **Explore other endpoints:** Learn about moves, abilities, and game mechanics.  
- **Build a CLI tool:** Prompt users for a Pokémon name and display stats, types, and abilities.  
- **Persist data:** Store responses in a local SQLite database for offline use.  
- **Integrate with a web app:** Use Flask or FastAPI to serve Pokémon data to a browser.

Happy poké‑coding!