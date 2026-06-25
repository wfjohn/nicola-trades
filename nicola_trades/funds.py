import yaml
from pathlib import Path
from functools import lru_cache

CONFIG_PATH = Path(__file__).parent.parent / "config" / "funds.yaml"

ILLIQUID = {
    "Private Equity LP", "Private Debt", "Canadian Real Estate LP",
    "U.S. Real Estate LP", "Diversified Real Estate", "Value Add Real Estate LP",
    "Global Infrastructure LP", "Venture Capital LP", "Diversified Private Assets",
}
CREDIT = {
    "High Yield Bond", "Balanced Mortgage", "U.S. Mortgage",
}
LIQUID = {
    "Core Portfolio", "Bond", "Canadian Equity Income", "U.S. Equity Income",
    "International Leaders", "Global Small Cap Equity",
}


@lru_cache(maxsize=1)
def _mapping() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f).get("funds", {})


def canonical(fund_id: str, fallback: str = "") -> str:
    """Return the canonical fund name for a Fund ID, or fallback if unknown."""
    return _mapping().get(str(fund_id).strip(), fallback)


def group(name: str) -> str:
    """Return the fund group (Liquid / Credit / Illiquid / Other)."""
    if name in ILLIQUID:
        return "Illiquid"
    if name in CREDIT:
        return "Credit"
    if name in LIQUID:
        return "Liquid"
    return "Other"
