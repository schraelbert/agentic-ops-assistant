from __future__ import annotations

from domains.renewable_ops import DOMAIN as RENEWABLE_OPS

DOMAINS = {
    RENEWABLE_OPS["name"]: RENEWABLE_OPS,
}


def get_domain(name: str):
    try:
        return DOMAINS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown domain: {name}. Available: {', '.join(sorted(DOMAINS))}") from exc
