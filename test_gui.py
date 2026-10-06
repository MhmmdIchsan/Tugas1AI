"""Integrated Tkinter user flows; skipped on machines without a Tk display."""

import math
from pathlib import Path
import tempfile
import tkinter as tk
import traceback
import unittest
from unittest.mock import patch

from examples import EXAMPLES, example_path
from gui import BELLMAN, DEFAULT_SOURCE, DIJKSTRA, ShortestPathApp


class GuiFlows(unittest.TestCase):
    def setUp(self) -> None:
        self.callback_errors: list[str] = []
        try:
            # Use canonical data: users are allowed to edit their own graf.txt.
            self.app = ShortestPathApp(example_path(EXAMPLES[0]))
        except tk.TclError as exc:
            if any(text in str(exc).lower() for text in ("no display", "couldn't connect to display", "no $display")):
                self.skipTest(f"Tk display unavailable: {exc}")
            raise
        self.app.withdraw()
        self.app.report_callback_exception = lambda *args: self.callback_errors.append("".join(traceback.format_exception(*args)))
        self.pump()

    def tearDown(self) -> None:
        try:
            self.pump()
        finally:
            self.app.close()
        self.assertEqual(self.callback_errors, [], "Tk callback exceptions:\n" + "\n".join(self.callback_errors))

    def pump(self) -> None:
        self.app.update_idletasks()
        self.app.update()
        self.assertEqual(self.callback_errors, [], "Tk callback exceptions:\n" + "\n".join(self.callback_errors))

    def select_example(self, example) -> None:
        self.app.source.set(example.title)
        self.app._select_source()
        self.pump()

    def test_select_all_examples_and_display_results_in_both_time_units(self) -> None:
        self.assertEqual(self.app.source.get(), DEFAULT_SOURCE)
        for example in EXAMPLES:
            with self.subTest(example=example.key):
                self.select_example(example)
                self.assertEqual(self.app.source_path, example_path(example))
                self.assertEqual(self.app.source.get(), example.title)
                self.assertEqual(set(self.app.results), {DIJKSTRA, BELLMAN})
                self.assertEqual(set(self.app.start_selector.cget("values")), set(self.app.graph))
                for name, result in self.app.results.items():
                    self.assertEqual(result.cost, example.expected_cost)
                    card = self.app.card_values[name]
                    self.assertEqual(card["cost"].get(), str(example.expected_cost))
                    self.assertEqual(card["path"].get(), " → ".join(result.path))
                    self.assertRegex(card["time"].get(), r"^\d+\.\d{6} s\s+\(\d+\.\d µs\)$")
                self.assertEqual(self.app.playback.index, 0)
                self.assertFalse(self.app.playback.finished)

    def test_change_and_swap_endpoints_without_rewriting_source(self) -> None:
        self.select_example(EXAMPLES[0])
        original = self.app.source_path.read_text(encoding="utf-8")
        self.app.goal_value.set("V10")
        self.app._change_endpoints()
        self.assertEqual((self.app.start, self.app.goal), ("V1", "V10"))
        self.assertTrue(all(result.cost == 400 for result in self.app.results.values()))
        self.app.swap_endpoints()
        self.pump()
        self.assertEqual((self.app.start_value.get(), self.app.goal_value.get()), ("V10", "V1"))
        for result in self.app.results.values():
            self.assertEqual(result.path, ["V10", "V6", "V4", "V1"])
            self.assertEqual(result.cost, 400)
        self.assertEqual(self.app.source_path.read_text(encoding="utf-8"), original)
        self.assertEqual(self.app.playback.index, 0)

    def test_algorithm_switch_seek_back_reset_and_final_state(self) -> None:
        self.select_example(EXAMPLES[2])
        for name in (BELLMAN, DIJKSTRA):
            with self.subTest(algorithm=name):
                self.app.algorithm.set(name)
                self.app._select_algorithm()
                measured_result = self.app.results[name]
                self.assertIs(self.app.playback.result, measured_result)
                self.app._seek("10")
                self.assertEqual(self.app.playback.index, 10)
                self.assertEqual(self.app.progress_value.get(), 10)
                self.app.previous_step()
                self.assertEqual(self.app.playback.index, 9)
                self.app.next_step()
                self.assertEqual(self.app.playback.index, 10)
                self.app.show_final()
                self.pump()
                self.assertTrue(self.app.playback.finished)
                self.assertEqual(self.app.playback.distances["H"], 9)
                self.assertEqual(str(self.app.distance_table.item("H", "values")[1]), "9")
                self.assertIn("ditemukan", self.app.step_title.get())
                self.app.reset_animation()
                self.assertEqual(self.app.playback.index, 0)
                self.assertFalse(self.app.playback.finished)
                self.assertTrue(math.isinf(self.app.playback.distances["H"]))
                self.assertEqual(self.app.distance_table.item("H", "values")[1], "∞")
                self.assertIs(self.app.playback.result, measured_result)

    def test_pause_and_source_switch_cancel_playback_timer(self) -> None:
        self.app.speed.set("0.5×")
        self.app.toggle_play()
        timer = self.app.timer
        self.assertTrue(self.app.playing)
        self.assertIn(timer, self.app.tk.call("after", "info"))
        self.app.toggle_play()
        self.assertFalse(self.app.playing)
        self.assertIsNone(self.app.timer)
        self.assertNotIn(timer, self.app.tk.call("after", "info"))
        self.app.toggle_play()
        old_timer = self.app.timer
        self.select_example(EXAMPLES[2])
        self.assertFalse(self.app.playing)
        self.assertIsNone(self.app.timer)
        self.assertNotIn(old_timer, self.app.tk.call("after", "info"))
        self.assertEqual(self.app.playback.index, 0)
        self.assertEqual((self.app.start, self.app.goal), ("B", "H"))

    def test_export_contains_current_results_without_recomputation(self) -> None:
        self.select_example(EXAMPLES[2])
        results = self.app.results
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hasil.txt"
            with patch("gui.filedialog.asksaveasfilename", return_value=str(path)), \
                    patch("gui.messagebox.showinfo") as info, \
                    patch("gui.dijkstra", side_effect=AssertionError("Export must not rerun a search")), \
                    patch("gui.bellman_ford", side_effect=AssertionError("Export must not rerun a search")):
                self.app.export_results()
            info.assert_called_once()
            report = path.read_text(encoding="utf-8")
        self.assertIs(self.app.results, results)
        self.assertIn("Awal: B | Tujuan: H", report)
        self.assertIn("B → C → F → E → H", report)
        self.assertEqual(report.count("Bobot minimum: 9"), 2)
        self.assertIn(DIJKSTRA, report)
        self.assertIn(BELLMAN, report)
        self.assertEqual(report.count(" µs)"), 2)
        self.assertIn(" s (", report)

    def test_invalid_file_preserves_graph_results_and_source_selection(self) -> None:
        self.select_example(EXAMPLES[1])
        graph, results = self.app.graph, self.app.results
        previous_path, previous_label = self.app.source_path, self.app.source.get()
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid.txt"
            invalid.write_text("graph = {'A': {'B': -1}, 'B': {}}\nA B", encoding="utf-8")
            self.app.source_paths["Berkas rusak"] = invalid
            self.app.source.set("Berkas rusak")
            with patch("gui.messagebox.showerror") as error:
                self.app._select_source()
            error.assert_called_once()
        self.pump()
        self.assertIs(self.app.graph, graph)
        self.assertIs(self.app.results, results)
        self.assertEqual(self.app.source_path, previous_path)
        self.assertEqual(self.app.source.get(), previous_label)
        self.assertEqual((self.app.start, self.app.goal), ("V1", "V10"))


if __name__ == "__main__":
    unittest.main()
