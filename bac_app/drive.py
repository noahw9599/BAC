"""Drive-risk advisory helpers.

This module provides conservative messaging for driving decisions based on
estimated BAC. It is educational only and never guarantees legal/safe driving.
"""

LEGAL_LIMIT_BAC = 0.08
CONSERVATIVE_LIMIT_BAC = 0.02


def get_drive_advice(bac_now: float, hours_until_sober_from_now: float) -> dict:
    """Return conservative drive-risk guidance from estimated BAC."""
    if bac_now >= LEGAL_LIMIT_BAC:
        return {
            "status": "do_not_drive",
            "title": "Above legal limit",
            "message": "Estimated BAC is at or above 0.08%. Do not drive.",
            "action": "Use a rideshare, taxi, or sober driver now.",
            "legal_limit_bac": LEGAL_LIMIT_BAC,
        }

    if bac_now >= 0.05:
        return {
            "status": "do_not_drive",
            "title": "Likely impaired",
            "message": "Estimated BAC is below 0.08% but still in a high-risk impairment range.",
            "action": "Do not drive. Wait and use a non-driving option.",
            "legal_limit_bac": LEGAL_LIMIT_BAC,
        }

    if bac_now >= CONSERVATIVE_LIMIT_BAC:
        wait_h = max(1.0, round(hours_until_sober_from_now, 1))
        return {
            "status": "do_not_drive",
            "title": "Alcohol still present",
            "message": "Estimated BAC is low but not near zero. Driving is still risky.",
            "action": f"Do not drive. Wait about {wait_h}h and recheck.",
            "legal_limit_bac": LEGAL_LIMIT_BAC,
        }

    if bac_now > 0:
        return {
            "status": "caution",
            "title": "Residual alcohol",
            "message": "Estimated BAC is very low but not zero.",
            "action": "Safest choice is still not to drive.",
            "legal_limit_bac": LEGAL_LIMIT_BAC,
        }

    return {
        "status": "ok",
        "title": "No alcohol logged",
        "message": "Estimated BAC is 0.000 right now.",
        "action": "If you have not consumed alcohol, impairment risk is lower.",
        "legal_limit_bac": LEGAL_LIMIT_BAC,
    }
