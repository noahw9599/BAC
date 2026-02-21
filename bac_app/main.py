"""
BAC tracker CLI demo. Run from project root: python -m bac_app.main
Creates a sample session, prints current BAC and curve, and optionally saves a graph.
"""

import argparse
import sys

from bac_app.session import Session
from bac_app.graph import curve_data, save_bac_graph


def main():
    parser = argparse.ArgumentParser(description="BAC tracker: log drinks and view BAC over time")
    parser.add_argument("--weight", type=float, default=160.0, help="Body weight (lb)")
    parser.add_argument("--male", action="store_true", default=True, help="Male (default)")
    parser.add_argument("--female", action="store_true", help="Female")
    parser.add_argument("--graph", type=str, metavar="FILE", help="Save BAC graph to FILE (e.g. bac_graph.png)")
    parser.add_argument("--demo", action="store_true", help="Run with demo drinks (2 beers at 0h, 1 at 1h)")
    args = parser.parse_args()

    session = Session(
        weight_lb=args.weight,
        is_male=not args.female,
    )

    if args.demo:
        session.add_drink(0.0, "beer", count=2.0)
        session.add_drink(1.0, "beer", count=1.0)
        print("Demo session: 2 beers at 0h, 1 beer at 1h")
    else:
        # Example: add drinks interactively or via more args; for now just demo
        session.add_drink(0.0, "beer", count=2.0)
        session.add_drink(1.0, "beer", count=1.0)
        print("Using demo session. Use --demo to confirm.")

    # Current BAC at end of logged drinks
    last_time = max(t for t, _ in session.events) if session.events else 0.0
    bac = session.bac_now(last_time)
    print(f"Weight: {session.weight_lb} lb, BAC at t={last_time}h: {bac:.3f}%")
    print(f"Hours until sober (from first drink): {session.hours_until_sober():1f}h")

    # Curve data (for API or iOS)
    curve = curve_data(session, max_hours=8.0)
    print(f"Curve points: {len(curve)} (time, bac) from 0 to 8h")

    if args.graph:
        try:
            path = save_bac_graph(session, output_path=args.graph, max_hours=8.0)
            print(f"Graph saved: {path}")
        except ImportError:
            print("matplotlib not installed. pip install matplotlib", file=sys.stderr)
            sys.exit(1)

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
