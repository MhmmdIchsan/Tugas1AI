from pathlib import Path

from ichsan.gui import ShortestPathApp


if __name__ == "__main__":
    default_graf = Path(__file__).parent / "ardi" / "graf.txt"
    ShortestPathApp(default_graf).mainloop()

