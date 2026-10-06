"""Verify the selectable examples against the assignment's expected answers."""

import os
from pathlib import Path
import tempfile
import unittest

from algorithms import bellman_ford, dijkstra
from examples import EXAMPLES, example_path
from graph_io import load_graph


class SelectableExamples(unittest.TestCase):
    def test_all_assignment_examples(self) -> None:
        expected = {
            "a": (15, ["V1", "V2", "V5", "V9", "V12", "V15"], 505),
            "b": (15, ["V1", "V4", "V6", "V10"], 400),
            "c": (10, ["B", "C", "F", "E", "H"], 9),
        }
        self.assertEqual({example.key for example in EXAMPLES}, set(expected))
        self.assertEqual(len(EXAMPLES), len(expected))
        for example in EXAMPLES:
            graph, start, goal = load_graph(example_path(example))
            node_count, route, cost = expected[example.key]
            self.assertEqual(len(graph), node_count)
            self.assertEqual((start, goal), (route[0], route[-1]))
            self.assertEqual(example.expected_cost, cost)
            for algorithm in (dijkstra, bellman_ford):
                with self.subTest(example=example.key, algorithm=algorithm.__name__):
                    result = algorithm(graph, start, goal)
                    self.assertEqual(result.path, route)
                    self.assertEqual(result.cost, cost)

    def test_paths_ignore_launch_directory_and_custom_graph(self) -> None:
        previous_directory = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                # A user's own graf.txt must not replace the built-in examples.
                Path("graf.txt").write_text("graph = {'Z': {}}\nZ Z", encoding="utf-8")
                for example in EXAMPLES:
                    with self.subTest(example=example.key):
                        path = example_path(example)
                        self.assertTrue(path.is_absolute())
                        graph, start, goal = load_graph(path)
                        self.assertEqual(dijkstra(graph, start, goal).cost, example.expected_cost)
            finally:
                os.chdir(previous_directory)

    def test_compact_endpoints_still_supported(self) -> None:
        example = next(example for example in EXAMPLES if example.key == "c")
        source = example_path(example).read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "graf.txt"
            path.write_text(source.replace("\nB H", "\nBH"), encoding="utf-8")
            graph, start, goal = load_graph(path)
            self.assertEqual((start, goal), ("B", "H"))
            self.assertEqual(dijkstra(graph, start, goal).cost, 9)


if __name__ == "__main__":
    unittest.main()
