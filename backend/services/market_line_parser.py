from __future__ import annotations

import re


def extract_line(
    outcome_name: str,
) -> float | None:
    match = re.search(
        r"\((-?\d+(?:\.\d+)?)\)",
        outcome_name,
    )

    if match:
        return float(
            match.group(1)
        )

    match = re.search(
        r"(Over|Under)\s+(\d+(?:\.\d+)?)",
        outcome_name,
    )

    if match:
        return float(
            match.group(2)
        )

    return None