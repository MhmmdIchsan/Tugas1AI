"""Canonical input examples from pages 3–4 of the assignment PDF.

Examples live separately from the editable ``graf.txt`` so the example chooser
always opens the original assignment data, whatever the current working folder.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Example:
    key: str
    title: str
    description: str
    filename: str
    expected_cost: int


EXAMPLES: tuple[Example, ...] = (
    Example(
        key="a",
        title="Contoh A · V1 → V15",
        description="15 simpul · tujuan V15 · bobot minimum 505",
        filename="contoh_a.txt",
        expected_cost=505,
    ),
    Example(
        key="b",
        title="Contoh B · V1 → V10",
        description="15 simpul · tujuan V10 · bobot minimum 400",
        filename="contoh_b.txt",
        expected_cost=400,
    ),
    Example(
        key="c",
        title="Contoh C · B → H",
        description="10 simpul · tujuan H · bobot minimum 9",
        filename="contoh_c.txt",
        expected_cost=9,
    ),
)


def example_path(example: Example) -> Path:
    """Return an absolute path without depending on the launch directory."""
    return Path(__file__).resolve().parent / "contoh" / example.filename
