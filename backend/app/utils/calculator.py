"""
Calculator Utilities
--------------------
Generic math helpers for the application.
NOTE: PCR calculation is the canonical version in pcr_service.py.
      This module is kept for other future utility functions.
"""


def format_crore(value: int | float) -> str:
    """Convert a raw OI number to a human-readable Crore string."""
    crore = value / 1_00_00_000
    return f"{crore:.2f} Cr"


def percentage_change(old: float, new: float) -> float:
    """Return the percentage change between two values."""
    if old == 0:
        return 0.0
    return round(((new - old) / old) * 100, 2)
