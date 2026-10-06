"""Regression and independent-oracle tests, using only unittest."""
from __future__ import annotations
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from algorithms import bellman_ford, dijkstra
from comparison import compare, comparison_data, costs_equal, export_json
from graph_io import load_graph

BASE = Path(__file__).resolve().parent
ALGORITHMS = (dijkstra, bellman_ford)


class AlgorithmEdgeCases(unittest.TestCase):
    def assert_valid_path(self, graph, start, goal, result, expected):
        self.assertEqual(result.cost, expected)
        if expected == math.inf:
            self.assertEqual(result.path, [])
        else:
            self.assertEqual(result.path[0], start)
            self.assertEqual(result.path[-1], goal)
            self.assertEqual(sum(graph[u][v] for u, v in zip(result.path, result.path[1:])), expected)
            self.assertEqual(len(result.path), len(set(result.path)))

    def test_zero_cycles_self_loops_equal_routes_and_stale_heap(self):
        graph = {'A': {'A': 0, 'B': 9, 'C': 1, 'D': 1},
                 'B': {'C': 0, 'E': 2}, 'C': {'B': 0, 'E': 2},
                 'D': {'E': 2}, 'E': {}}
        for algorithm in ALGORITHMS:
            result = algorithm(graph, 'A', 'E')
            self.assert_valid_path(graph, 'A', 'E', result, 3)
            self.assertEqual(result.path, algorithm(graph, 'A', 'E').path)

    def test_single_vertex(self):
        for algorithm in ALGORITHMS:
            self.assertEqual(algorithm({'A': {}}, 'A', 'A').path, ['A'])

    def test_directed_asymmetric_edges(self):
        graph = {'A': {'B': 2}, 'B': {'A': 8, 'C': 1}, 'C': {}}
        for algorithm in ALGORITHMS:
            self.assertEqual(algorithm(graph, 'A', 'C').cost, 3)
            self.assertEqual(algorithm(graph, 'B', 'A').cost, 8)
            self.assertEqual(algorithm(graph, 'C', 'A').cost, math.inf)

    def test_float_and_large_integer(self):
        for algorithm in ALGORITHMS:
            self.assertAlmostEqual(algorithm({'A': {'B': 0.1}, 'B': {'C': 0.2}, 'C': {}}, 'A', 'C').cost, 0.3)
            self.assertEqual(algorithm({'A': {'B': 10**400}, 'B': {}}, 'A', 'B').cost, 10**400)

    def test_overflow_is_not_unreachable(self):
        for algorithm in ALGORITHMS:
            with self.assertRaisesRegex(ValueError, 'kapasitas float'):
                algorithm({'A': {'B': 1e308}, 'B': {'C': 1e308}, 'C': {}}, 'A', 'C')

    def test_api_rejects_negative_and_unknown_endpoint(self):
        for algorithm in ALGORITHMS:
            with self.assertRaises(ValueError):
                algorithm({'A': {'B': -1}, 'B': {}}, 'A', 'B')
            with self.assertRaises(ValueError):
                algorithm({'A': {}}, 'A', 'B')

    def test_trace_limits_do_not_change_answers(self):
        graph, start, goal = load_graph(BASE / 'graf.txt')
        for algorithm in ALGORITHMS:
            limited = algorithm(graph, start, goal, max_steps=3)
            plain = algorithm(graph, start, goal, record_steps=False)
            self.assertEqual((limited.path, limited.cost), (plain.path, plain.cost))
            self.assertEqual(limited.metrics, plain.metrics)
            self.assertEqual(len(limited.steps), 4)
            self.assertTrue(limited.trace_truncated)
            self.assertEqual(limited.steps[-1].kind, 'done')
            self.assertEqual(plain.steps, [])
            self.assertFalse(plain.trace_truncated)

    def test_bellman_ford_reverse_order_requires_v_minus_one_passes(self):
        graph = {'D': {}, 'C': {'D': 1}, 'B': {'C': 1}, 'A': {'B': 1}}
        result = bellman_ford(graph, 'A', 'D')
        self.assertEqual(result.cost, 3)
        self.assertEqual(result.metrics.passes, 3)
        self.assertEqual(result.metrics.inspected_edges, 9)

    def test_random_graphs_against_floyd_warshall(self):
        # Independent dynamic-programming oracle, not one algorithm testing the other.
        rng = random.Random(1001)
        for case in range(35):
            vertices = [str(i) for i in range(rng.randrange(2, 9))]
            graph = {u: {v: rng.randrange(0, 15) for v in vertices if rng.random() < .3}
                     for u in vertices}
            distance = {(u, v): min(0 if u == v else math.inf, graph[u].get(v, math.inf))
                        for u in vertices for v in vertices}
            for k in vertices:
                for u in vertices:
                    for v in vertices:
                        distance[u, v] = min(distance[u, v], distance[u, k] + distance[k, v])
            for start in vertices:
                for goal in vertices:
                    for algorithm in ALGORITHMS:
                        with self.subTest(case=case, start=start, goal=goal, algorithm=algorithm.__name__):
                            self.assert_valid_path(graph, start, goal,
                                                   algorithm(graph, start, goal, record_steps=False),
                                                   distance[start, goal])


class InputValidation(unittest.TestCase):
    def parse(self, content):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'graf.txt'
            path.write_text(content, encoding='utf-8')
            return load_graph(path)

    def test_bom_comments_and_blank_lines(self):
        graph, start, goal = self.parse("\ufeff# graf uji\ngraph = {'A': {'B': 0}, 'B': {}} # selesai }\n\nA B # tujuan\n# komentar akhir\n")
        self.assertEqual((start, goal, graph['A']['B']), ('A', 'B', 0))

    def test_duplicate_keys_rejected(self):
        for content in ["graph={'A':{},'A':{}}\nA A", "graph={'A':{'B':1,'B':2},'B':{}}\nA B"]:
            with self.assertRaisesRegex(ValueError, 'duplikat'):
                self.parse(content)

    def test_malformed_and_nonfinite_inputs(self):
        for content in ['', 'graph={}\nA A', "graph={'A': []}\nA A",
                        "graph={'A B': {}}\nA B", "graph={'A': {'A': True}}\nA A",
                        "graph={'A': {'A': 1e999}}\nA A", "graph={'A': {'A': '2'}}\nA A",
                        "data={'A': {}}\nA A", "graph={'A': {}}\nA A A",
                        "graph={'A': {}}\nA B", "graph={1: {}}\n1 1"]:
            with self.subTest(content=content), self.assertRaises(ValueError):
                self.parse(content)

    def test_payload_is_never_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'should_not_exist'
            payload = f"graph = {{'A': {{'A': __import__('pathlib').Path({str(marker)!r}).touch()}}}}\nA A"
            with self.assertRaises(ValueError):
                self.parse(payload)
            self.assertFalse(marker.exists())


class ComparisonAndCLI(unittest.TestCase):
    def test_json_is_strict_and_contains_measurement_evidence(self):
        graph = {'A': {}, 'B': {}}
        comparison = compare(graph, 'A', 'B', repetitions=5, warmups=1)
        data = comparison_data(comparison, graph, 'A', 'B')
        self.assertTrue(data['consistent'])
        for result in data['results']:
            self.assertIsNone(result['cost'])
            self.assertFalse(result['reachable'])
            self.assertEqual(len(result['timing']['samples_ns']), 5)
            self.assertGreaterEqual(result['timing']['min_us'], 0)
            self.assertLessEqual(result['timing']['min_us'], result['timing']['median_us'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.json'
            export_json(path, data)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), data)

    def test_invalid_benchmark_counts(self):
        for count in (0, -1, 10001):
            with self.assertRaises(ValueError):
                compare({'A': {}}, 'A', 'A', repetitions=count)
        self.assertFalse(costs_equal(0, math.inf))

    def test_cli_from_another_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'output.json'
            result = subprocess.run([sys.executable, str(BASE / 'MMAIKelompokX.py'), '--cli',
                                     '--goal', 'V10', '--repeat', '3', '--export', str(output)],
                                    cwd=directory, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual([r['cost'] for r in data['results']], [400, 400])

    def test_cli_bad_input_returns_error(self):
        result = subprocess.run([sys.executable, str(BASE / 'MMAIKelompokX.py'), '--cli', '--goal', 'UNKNOWN'],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 2)
        self.assertIn('Gagal:', result.stderr)
        self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
