# bac_app

Core BAC modeling package used by the Flask web app.

## Responsibilities

- `drinks.py`: drink definitions and grams conversion helpers
- `catalog.py`: curated drink catalog and nutrition metadata
- `calculations.py`: BAC rise/decay model and curve generation
- `session.py`: session state and event logging
- `hangover.py`: stop-by and risk guidance helpers
- `graph.py`: optional static chart generation via matplotlib

## Example

```python
from bac_app.session import Session

session = Session(weight_lb=160, is_male=True)
session.add_drink_ago(hours_ago=1.0, drink_key="beer", count=2)
print(session.bac_now(0.0))
```

## Notes

- The model is intentionally simple and educational.
- Results should not be used as legal or medical proof of impairment.