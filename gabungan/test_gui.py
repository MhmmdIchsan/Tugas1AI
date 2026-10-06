"""Integration checks for the three merged UI components on a real Tk display."""
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import time
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parent


class MergedGUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            probe = tk.Tk()
            probe.destroy()
        except ImportError as exc:
            raise unittest.SkipTest(f'Tkinter tidak tersedia: {exc}')
        except Exception as exc:
            if isinstance(exc, tk.TclError):
                raise unittest.SkipTest(f'Layar GUI tidak tersedia: {exc}')
            raise

    def setUp(self):
        from gui import ShortestPathApp
        self.errors = []
        self.app = ShortestPathApp(BASE / 'graf.txt')
        self.app.report_callback_exception = lambda *args: self.errors.append(args)
        self.wait_until(lambda: self.app.playback is not None)

    def tearDown(self):
        self.app.close()
        self.assertFalse(self.errors, self.errors)

    def wait_until(self, condition):
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            self.app.update()
            if condition():
                return
            time.sleep(.01)
        self.fail(f'GUI timeout; callback errors: {self.errors}')

    def assert_synchronized(self):
        from playback import number
        state, canvas, table = self.app.playback, self.app.canvas, self.app.distance_table
        self.assertEqual(canvas.dist, state.distances)
        self.assertEqual(canvas.prev, state.previous)
        self.assertEqual(canvas.current, state.current)
        self.assertEqual(canvas.finished, state.finished)
        for vertex in self.app.graph:
            row = table.item(vertex, 'values')
            self.assertEqual(row[1], number(state.distances[vertex]))
            self.assertEqual(row[2], state.previous.get(vertex, '—'))

    def test_examples_and_component_sync(self):
        for name, expected in [('contoh_a.txt', 505), ('contoh_b.txt', 400), ('contoh_c.txt', 9)]:
            self.app.open_file(BASE / 'contoh' / name)
            self.wait_until(lambda: not self.app.busy)
            for algorithm in ('Dijkstra', 'Bellman–Ford'):
                self.app.algorithm.set(algorithm)
                self.app._select_algorithm()
                self.app.show_final()
                self.assertEqual(self.app.playback.result.cost, expected)
                self.assert_synchronized()
                self.app.update()
                self.assertTrue(self.app.canvas.find_withtag('node'))
                self.wait_until(lambda: bool(self.app.canvas.find_withtag('fx')))

    def test_forward_backward_seek_and_reset(self):
        app = self.app
        timing = app.comparison
        for _ in range(10):
            app.next_step()
            self.assert_synchronized()
        snapshot = dict(app.playback.distances)
        app.previous_step()
        self.assertEqual(app.playback.index, 9)
        self.assert_synchronized()
        app.next_step()
        self.assertEqual(app.playback.distances, snapshot)
        app._seek('4')
        self.assertEqual(app.playback.index, 4)
        self.assert_synchronized()
        app.show_final()
        self.assertTrue(app.playback.finished)
        app.reset_animation()
        self.assertEqual(app.playback.index, 0)
        self.assertEqual(app.playback.distances['V15'], float('inf'))
        self.assert_synchronized()
        self.assertIs(app.comparison, timing)

    def test_play_pause_and_switch_algorithm(self):
        app = self.app
        app.toggle_play()
        self.assertTrue(app.playing)
        self.assertIsNotNone(app.timer)
        app.next_step()
        self.assertFalse(app.playing)
        self.assertIsNone(app.timer)
        index = app.playback.index
        self.wait_until(lambda: bool(app.canvas.find_withtag('fx')))
        self.assertEqual(app.playback.index, index)
        app.algorithm.set('Bellman–Ford')
        app._select_algorithm()
        self.assertEqual(app.playback.index, 0)
        self.assert_synchronized()

    def test_context_endpoint_swap_and_invalid_file_recovery(self):
        app = self.app
        app.canvas.on_endpoint('goal', 'V10')
        self.wait_until(lambda: not app.busy)
        self.assertEqual(app.results['Dijkstra'].cost, 400)
        app.swap_endpoints()
        self.wait_until(lambda: not app.busy)
        self.assertEqual((app.start, app.goal), ('V10', 'V1'))
        self.assertEqual(app.results['Dijkstra'].cost, 400)
        saved = app.comparison
        with patch('gui.messagebox.showerror') as error:
            app.open_file(BASE / 'missing.txt')
            error.assert_called_once()
        self.assertIs(app.comparison, saved)
        self.assert_synchronized()

    def test_canvas_drag_zoom_pan_reset_and_hover(self):
        canvas = self.app.canvas
        original = dict(canvas.positions)
        vertex = self.app.start
        x, y = canvas.pixel_positions[vertex]
        canvas._hover(SimpleNamespace(x=x, y=y))
        self.assertEqual(canvas.hovered, vertex)
        self.assertIn(vertex, self.app.canvas_hint.get())
        canvas._press(SimpleNamespace(x=x, y=y))
        canvas._drag(SimpleNamespace(x=x+20, y=y+10))
        canvas._release(None)
        self.assertNotEqual(original[vertex], canvas.positions[vertex])
        canvas.zoom_in()
        self.assertGreater(canvas.zoom, 1)
        canvas._press(SimpleNamespace(x=5, y=5))
        canvas._drag(SimpleNamespace(x=25, y=15))
        self.assertNotEqual(canvas.pan, (0., 0.))
        canvas._release(None)
        canvas.reset_view()
        self.assertEqual(canvas.positions, original)
        self.assertEqual(canvas.zoom, 1)
        self.assertEqual(self.app.playback.index, 0)

    def test_edge_cases_and_resize(self):
        for name in ('berarah.txt', 'bobot_nol.txt', 'tidak_terjangkau.txt', 'awal_sama_tujuan.txt'):
            self.app.open_file(BASE / 'examples' / name)
            self.wait_until(lambda: not self.app.busy)
            self.app.show_final()
            self.assert_synchronized()
            self.app.geometry('1100x760')
            self.app.update()
            self.app.results_panel.notebook.select(0)
            self.app.update()
            button = self.app.results_panel.export_button
            self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                                 self.app.winfo_rooty() + self.app.winfo_height())
            self.app.results_panel.notebook.select(1)

    def test_export_json_and_text(self):
        with tempfile.TemporaryDirectory() as directory:
            for ext in ('json', 'txt'):
                path = Path(directory) / ('result.'+ext)
                with patch('gui.filedialog.asksaveasfilename', return_value=str(path)), patch('gui.messagebox.showinfo'):
                    self.app.export_results()
                text = path.read_text(encoding='utf-8')
                if ext == 'json':
                    self.assertEqual([r['cost'] for r in json.loads(text)['results']], [505, 505])
                else:
                    self.assertIn('505', text)
                    self.assertIn('31 pengukuran', text)


if __name__ == '__main__':
    unittest.main()
