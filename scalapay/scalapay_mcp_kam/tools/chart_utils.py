import ast
import json
import logging
import re

# Set up logging
logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _slice_outmost_braces(s: str) -> str:
    """Return the substring spanning the first complete {...} block."""
    start = s.find("{")
    if start == -1:
        return s
    depth = 0
    for i in range(start, len(s)):
        c = s[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    # If we never closed, return original (will fail later and log)
    return s


def _safe_to_float(val) -> float | None:
    """Convert a value to float if possible, else None."""
    try:
        if val is None:
            return None
        return float(str(val).strip())
    except Exception:
        return None


def _normalize_months_map(months_map: dict) -> dict[str, dict[int, float]]:
    """
    Normalize the months_map structure into {month: {year: value}}.
    Handles messy keys/values gracefully.
    """
    normalized: dict[str, dict[int, float]] = {}
    for month, yearly in months_map.items():
        if not isinstance(yearly, dict):
            # Sometimes the LLM might flatten: {"Jan 2024": 123}
            # Try to recover with regex
            m = re.match(r"([A-Za-z]+)\s*(\d{4})", str(month))
            if m:
                m_name, y_str = m.groups()
                val = _safe_to_float(yearly)
                if val is not None:
                    normalized.setdefault(m_name, {})[int(y_str)] = val
            continue

        clean_yearly: dict[int, float] = {}
        for year, val in yearly.items():
            try:
                year_int = int(str(year).strip())
            except Exception:
                continue
            fval = _safe_to_float(val)
            if fval is not None:
                clean_yearly[year_int] = fval

        if clean_yearly:
            normalized[month] = clean_yearly

    return normalized


def _extract_months_map(alfred_text) -> dict:
    """
    Accepts:
      - dict
      - Python dict string with single quotes
      - JSON string
      - Noisy text containing a dict substring
    Returns a dict like:
      { 'Jan': {'2022': 0, '2023': 34, ...}, ... }
    """
    # 1) Already a dict
    if isinstance(alfred_text, dict):
        return alfred_text

    # 2) Must be a string; trim and slice out {...}
    s = str(alfred_text).strip()
    s = _slice_outmost_braces(s)

    # 3) Try safest first: Python literal (handles single quotes)
    try:
        data = ast.literal_eval(s)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # 4) Try JSON as-is
    try:
        data = json.loads(s)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # 5) Last resort: convert single → double quotes and parse as JSON
    try:
        s_json = s.replace("'", '"')
        data = json.loads(s_json)
        if isinstance(data, dict):
            return data
    except Exception as e:
        logger.exception(f"Failed to parse Alfred mapping: {e}")

    return {}
