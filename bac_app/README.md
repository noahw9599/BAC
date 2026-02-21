# BAC Tracker App

Modular BAC tracking with **Widmark-style math** and **graph visuals**, ready to reuse for a web or iOS app.

## Run (from project root)

```bash
pip install -r requirements.txt
python -m bac_app.main --demo
python -m bac_app.main --demo --graph bac_graph.png
```

Options: `--weight 180`, `--female`, `--graph FILE`.

## Layout (one concern per file)

| File | Role |
|------|------|
| `drinks.py` | Drink types, standard drink (14g), grams from volume/ABV |
| `calculations.py` | Widmark rise, BAC at time, BAC curve, elimination 0.015%/hr |
| `session.py` | Session (weight, sex, drink log), add_drink, bac_now, curve, hours_until_sober |
| `graph.py` | `curve_data()` for any UI; `save_bac_graph()` for PNG (matplotlib) |
| `main.py` | CLI demo and graph export |

## Use from code (or future iOS bridge)

```python
from bac_app import Session, curve_data, save_bac_graph

session = Session(weight_lb=160, is_male=True)
session.add_drink(0.0, "beer", count=2.0)
session.add_drink(1.0, "wine", count=1.0)

bac = session.bac_now(2.0)           # BAC at 2 hours
points = curve_data(session)        # [(t, bac), ...] for charts
save_bac_graph(session, "out.png")  # optional PNG
```

Same `Session` and `curve_data()` can drive a web frontend or iOS (Swift) with the same math.
