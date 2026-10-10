"""Pemeriksaan bermakna untuk tiga contoh soal dan kasus masukan tidak valid.

Uji ini memakai data soal apa adanya (berkas ``graf.txt`` serta contoh B dan C),
sehingga menangkap regresi pada jalur, bobot minimum, dan penanganan masukan
rusak.
"""

from pathlib import Path
import tempfile
import unittest

from algorithms import bellman_ford, dijkstra
from graph_io import load_graph


BASE = Path(__file__).resolve().parent.parent


class AssignmentExamples(unittest.TestCase):
    def test_first_example(self) -> None:
        graph, start, goal = load_graph(BASE / "graf.txt")
        for algorithm in (dijkstra, bellman_ford):
            with self.subTest(algorithm=algorithm.__name__):
                result = algorithm(graph, start, goal)
                self.assertEqual(result.path, ["V1", "V2", "V5", "V9", "V12", "V15"])
                self.assertEqual(result.cost, 505)

    def test_second_example(self) -> None:
        graph, start, _ = load_graph(BASE / "graf.txt")
        for algorithm in (dijkstra, bellman_ford):
            result = algorithm(graph, start, "V10")
            self.assertEqual(result.path, ["V1", "V4", "V6", "V10"])
            self.assertEqual(result.cost, 400)

    def test_third_example_and_bh_format(self) -> None:
        content = """graf = {
            'A': {'B': 4, 'C': 2},
            'B': {'A': 4, 'C': 1, 'D': 5},
            'C': {'A': 2, 'B': 1, 'E': 10, 'F': 3},
            'D': {'B': 5, 'E': 2, 'G': 4},
            'E': {'C': 10, 'D': 2, 'F': 2, 'H': 3},
            'F': {'C': 3, 'E': 2, 'I': 11},
            'G': {'D': 4, 'H': 1},
            'H': {'E': 3, 'G': 1, 'I': 5, 'J': 7},
            'I': {'F': 11, 'H': 5, 'J': 2},
            'J': {'H': 7, 'I': 2}
        }
        BH
        """
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "graf.txt"
            path.write_text(content, encoding="utf-8")
            graph, start, goal = load_graph(path)
        for algorithm in (dijkstra, bellman_ford):
            result = algorithm(graph, start, goal)
            self.assertEqual(result.path, ["B", "C", "F", "E", "H"])
            self.assertEqual(result.cost, 9)

    def test_disconnected_and_same_start_goal(self) -> None:
        graph = {"A": {"B": 2}, "B": {}, "C": {}}
        for algorithm in (dijkstra, bellman_ford):
            unreachable = algorithm(graph, "A", "C")
            self.assertEqual(unreachable.path, [])
            self.assertEqual(unreachable.cost, float("inf"))
            same = algorithm(graph, "A", "A")
            self.assertEqual(same.path, ["A"])
            self.assertEqual(same.cost, 0)

    def test_invalid_input_is_rejected(self) -> None:
        cases = [
            "graph = {'A': {'B': -1}, 'B': {}}\nA B",
            "graph = {'A': {'B': 1}, 'B': {}}\nA C",
            "graph = {'A': {'B': 1}}\nA B",
            "graph = __import__('os').system('echo unsafe')\nA B",
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "graf.txt"
            for content in cases:
                with self.subTest(content=content):
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_graph(path)


if __name__ == "__main__":
    unittest.main()
