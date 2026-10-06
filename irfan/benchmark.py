"""Reproduce the assignment examples and deterministic scaling experiments."""
from __future__ import annotations
import argparse
import csv
from pathlib import Path
import random
from comparison import compare, comparison_data, export_json
from graph_io import Graph, load_graph

BASE = Path(__file__).resolve().parent


def synthetic_graph(size: int, probability: float, seed: int) -> Graph:
    """Directed graph with a guaranteed chain from N0 to the final node."""
    rng = random.Random(seed)
    graph = {f'N{i}': {} for i in range(size)}
    for i in range(size - 1):
        graph[f'N{i}'][f'N{i+1}'] = rng.randint(1, 20)
    for source in graph:
        for destination in graph:
            if source != destination and rng.random() < probability:
                graph[source][destination] = rng.randint(1, 100)
    return graph


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeat', type=int, default=101)
    parser.add_argument('--output', type=Path, default=BASE / 'hasil')
    args = parser.parse_args()
    if not 1 <= args.repeat <= 10000:
        parser.error('--repeat harus 1–10000')
    args.output.mkdir(parents=True, exist_ok=True)
    cases = []
    for name, file in [('soal_a', 'graf.txt'), ('soal_b', 'contoh_V1_V10.txt'), ('soal_c', 'contoh_B_H.txt')]:
        graph, start, goal = load_graph(BASE / file)
        cases.append((name, graph, start, goal, file))
    for size in (20, 50, 100):
        for label, probability in [('jarang', .04), ('padat', .35)]:
            seed = 1001 + size
            graph = synthetic_graph(size, probability, seed)
            cases.append((f'{label}_{size}', graph, 'N0', f'N{size-1}',
                          f'synthetic seed={seed}; probability={probability}; guaranteed chain'))
    size = 100
    reverse = {f'N{i}': ({f'N{i+1}': 1} if i < size-1 else {}) for i in reversed(range(size))}
    cases.append(('rantai_terbalik_100', reverse, 'N0', 'N99', 'reverse-order directed chain'))
    rows, all_data = [], []
    for name, graph, start, goal, source in cases:
        comparison = compare(graph, start, goal, repetitions=args.repeat, warmups=5, record_steps=False)
        if not comparison.consistent:
            raise RuntimeError(f'Hasil algoritma berbeda: {name}')
        data = comparison_data(comparison, graph, start, goal, source)
        data['case'] = name
        all_data.append(data)
        for result in data['results']:
            timing = result['timing']
            rows.append({'case': name, 'vertices': len(graph), 'directed_edges': data['directed_edges'],
                         'algorithm': result['algorithm'], 'cost': result['cost'],
                         'median_us': round(timing['median_us'], 3),
                         'q1_us': round(timing['q1_us'], 3), 'q3_us': round(timing['q3_us'], 3),
                         'inspected_edges': result['metrics']['inspected_edges'],
                         'relaxations': result['metrics']['relaxations'],
                         'passes': result['metrics']['passes']})
        print(f"{name}: bobot {data['results'][0]['cost']}; " + ', '.join(
            f"{r['algorithm']} {r['timing']['median_us']:.3f} µs" for r in data['results']))
    export_json(args.output / 'benchmark.json', {'cases': all_data})
    with (args.output / 'benchmark.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == '__main__':
    main()
