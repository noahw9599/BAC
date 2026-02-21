"""
BAC-over-time graph. Produces image file or returns data for web/iOS.
"""

from pathlib import Path
from typing import List, Tuple

from bac_app.session import Session


def curve_data(session: Session, step_hours: float = 0.25, max_hours: float = 12.0) -> List[Tuple[float, float]]:
    """(time_hours, bac_percent) for use in any frontend (web, iOS)."""
    return session.curve(step_hours=step_hours, max_hours=max_hours)


def save_bac_graph(
    session: Session,
    output_path: str = "bac_graph.png",
    step_hours: float = 0.25,
    max_hours: float = 12.0,
    title: str = "BAC over time",
) -> str:
    """
    Plot BAC curve with matplotlib and save to file.
    Returns path to saved file. Requires: pip install matplotlib
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        raise ImportError("matplotlib is required for save_bac_graph. pip install matplotlib")

    points = curve_data(session, step_hours=step_hours, max_hours=max_hours)
    if not points:
        times, bacs = [0], [0.0]
    else:
        times, bacs = zip(*points)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(times, bacs, color="#2563eb", linewidth=2, label="BAC")
    ax.fill_between(times, bacs, alpha=0.2, color="#2563eb")
    ax.axhline(y=0.08, color="#dc2626", linestyle="--", linewidth=1, label="Legal limit (0.08%)")
    ax.set_xlabel("Hours from start")
    ax.set_ylabel("BAC (%)")
    ax.set_title(title)
    ax.legend(loc="upper right")
    ax.set_ylim(bottom=0)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path
