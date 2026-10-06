"""Main entry point for the shortest path assignment.

Rename this file to MMAIKelompok<N>.py using your actual group number.
Run it from any directory: python path/to/MMAIKelompokX.py
"""

from pathlib import Path

from ichsan.gui import ShortestPathApp


if __name__ == "__main__":
    ShortestPathApp(Path(__file__).with_name("graf.txt")).mainloop()
