"""Check replay state used by stepping, seeking, and resetting the GUI."""

import math
import unittest
from unittest.mock import patch

from algorithms import bellman_ford, dijkstra
from examples import EXAMPLES, example_path
from graph_io import load_graph
from playback import Playback


class PlaybackTests(unittest.TestCase):
    def setUp(self) -> None:
        # B and D first receive a tentative route, then a strictly better one.
        self.graph = {
            "A": {"B": 5, "C": 1},
            "B": {"D": 1},
            "C": {"B": 1, "D": 10},
            "D": {},
        }

    def test_initial_state_and_reset_after_completion(self) -> None:
        result = dijkstra(self.graph, "A", "D")
        state = Playback(self.graph, "A", "D", result)
        for completed in (False, True):
            with self.subTest(after_completion=completed):
                if completed:
                    state.seek(len(result.steps))
                    self.assertTrue(state.finished)
                    state.reset()
                self.assertEqual(state.index, 0)
                self.assertEqual(state.distances, {"A": 0, "B": math.inf, "C": math.inf, "D": math.inf})
                self.assertEqual(state.previous, {})
                self.assertEqual(state.visited, set())
                self.assertIsNone(state.current)
                self.assertIsNone(state.active_edge)
                self.assertFalse(state.finished)
                self.assertEqual(state.iteration, 0)

    def test_seek_restores_tentative_routes_in_both_directions(self) -> None:
        result = dijkstra(self.graph, "A", "D")
        state = Playback(self.graph, "A", "D", result)
        first_b = next(i + 1 for i, step in enumerate(result.steps)
                       if step.kind == "relax" and step.neighbor == "B")
        better_b = next(i + 1 for i, step in enumerate(result.steps)
                        if step.kind == "relax" and step.node == "C" and step.neighbor == "B")
        for cursor in (better_b, first_b, better_b):
            with self.subTest(cursor=cursor):
                state.seek(cursor)
                if cursor == first_b:
                    self.assertEqual(state.distances, {"A": 0, "B": 5, "C": math.inf, "D": math.inf})
                    self.assertEqual(state.previous, {"B": "A"})
                    self.assertEqual(state.visited, {"A"})
                    self.assertEqual(state.current, "A")
                    self.assertEqual(state.active_edge, ("A", "B"))
                else:
                    self.assertEqual(state.distances, {"A": 0, "B": 2, "C": 1, "D": math.inf})
                    self.assertEqual(state.previous, {"B": "C", "C": "A"})
                    self.assertEqual(state.visited, {"A", "C"})
                    self.assertEqual(state.current, "C")
                    self.assertEqual(state.active_edge, ("C", "B"))
                self.assertEqual(state.index, cursor)
                self.assertFalse(state.finished)

    def test_full_replay_matches_every_assignment_result(self) -> None:
        for example in EXAMPLES:
            graph, start, goal = load_graph(example_path(example))
            for algorithm in (dijkstra, bellman_ford):
                with self.subTest(example=example.key, algorithm=algorithm.__name__):
                    result = algorithm(graph, start, goal)
                    state = Playback(graph, start, goal, result)
                    while state.advance():
                        pass
                    self.assertTrue(state.finished)
                    self.assertEqual(state.index, len(result.steps))
                    self.assertEqual(state.distances[goal], example.expected_cost)
                    route = [goal]
                    while route[-1] != start:
                        route.append(state.previous[route[-1]])
                    self.assertEqual(list(reversed(route)), result.path)
                    self.assertIsNone(state.current)
                    self.assertIsNone(state.active_edge)
                    self.assertFalse(state.advance())

    def test_unreachable_and_same_endpoint_completion(self) -> None:
        graph = {"A": {"B": 2}, "B": {}, "C": {}}
        for algorithm in (dijkstra, bellman_ford):
            for goal, cost, route in (("C", math.inf, []), ("A", 0, ["A"])):
                with self.subTest(algorithm=algorithm.__name__, goal=goal):
                    result = algorithm(graph, "A", goal)
                    state = Playback(graph, "A", goal, result)
                    state.seek(len(result.steps))
                    self.assertTrue(state.finished)
                    self.assertEqual(state.distances[goal], cost)
                    self.assertEqual(result.path, route)
                    self.assertNotIn("C", state.previous)
                    self.assertIn("tidak terjangkau" if not route else "ditemukan", state.title)
                    state.seek(0)
                    self.assertFalse(state.finished)
                    self.assertEqual(state.previous, {})

    def test_seeking_does_not_retime_or_rerun_algorithms(self) -> None:
        for algorithm in (dijkstra, bellman_ford):
            with self.subTest(algorithm=algorithm.__name__):
                result = algorithm(self.graph, "A", "D")
                runtime = result.runtime_ns
                state = Playback(self.graph, "A", "D", result)
                with patch("algorithms.perf_counter_ns", side_effect=AssertionError("Replay must not run or time a search")):
                    state.seek(len(result.steps) + 100)
                    self.assertEqual(state.index, len(result.steps))
                    self.assertTrue(state.finished)
                    state.seek(-10)
                    self.assertEqual(state.index, 0)
                    self.assertFalse(state.finished)
                    state.seek(len(result.steps) // 2)
                    state.seek(len(result.steps))
                self.assertIs(state.result, result)
                self.assertEqual(state.result.runtime_ns, runtime)


if __name__ == "__main__":
    unittest.main()
