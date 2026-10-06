"""Real Tk smoke tests; skipped explicitly when Tk/display is unavailable."""
from pathlib import Path
import time
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parent


class GUIIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            probe = tk.Tk()
            probe.destroy()
        except (ImportError, RuntimeError) as exc:
            raise unittest.SkipTest(f'Tkinter tidak tersedia: {exc}')
        except Exception as exc:
            if isinstance(exc, tk.TclError):
                raise unittest.SkipTest(f'Layar GUI tidak tersedia: {exc}')
            raise

    def setUp(self):
        from gui import ShortestPathApp
        self.app = ShortestPathApp(BASE / 'graf.txt')
        self.errors = []
        self.app.report_callback_exception = lambda *args: self.errors.append(args)
        self.wait_until(lambda: self.app.comparison is not None)

    def tearDown(self):
        self.app.close()
        self.assertFalse(self.errors, self.errors)

    def wait_until(self, condition):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            self.app.update()
            if condition():
                return
            time.sleep(.01)
        self.fail('GUI tidak menyelesaikan pekerjaan dalam 5 detik')

    def test_animation_reset_algorithm_switch_and_final(self):
        app = self.app
        self.assertEqual(app.results['Dijkstra'].cost, 505)
        app.next_step()
        self.assertEqual(app.step_index, 1)
        app.toggle_play()
        self.assertTrue(app.playing)
        app.next_step()
        self.assertFalse(app.playing)
        self.assertIsNone(app.timer)
        app.show_final()
        self.assertTrue(app.finished)
        self.assertEqual(app.step_index, len(app.events))
        app.algorithm.set('Bellman–Ford')
        app.reset_animation()
        self.assertEqual(app.step_index, 0)
        app.show_final()
        self.assertEqual(app.distance_table.item(app.row_ids['V15'], 'values')[1], '505')
        app.reset_animation()
        self.assertFalse(app.finished)
        self.assertEqual(app.distance_table.item(app.row_ids['V15'], 'values')[1], '∞')

    def test_endpoint_change_and_error_recovery(self):
        app = self.app
        app.goal_var.set('V10')
        app.calculate()
        self.wait_until(lambda: not app.busy)
        self.assertEqual(app.results['Dijkstra'].cost, 400)
        with patch('gui.messagebox.showerror') as error:
            app.open_file(BASE / 'nonexistent.txt')
            error.assert_called_once()
        self.assertEqual(app.results['Dijkstra'].cost, 400)
        app.open_file(BASE / 'contoh_B_H.txt')
        self.wait_until(lambda: not app.busy)
        self.assertEqual(app.results['Dijkstra'].cost, 9)
        app.show_final()

    def test_directed_loops_unreachable_and_single_node_render(self):
        app = self.app
        for file in ['berarah.txt', 'bobot_nol.txt', 'tidak_terjangkau.txt', 'awal_sama_tujuan.txt']:
            app.open_file(BASE / 'examples' / file)
            self.wait_until(lambda: not app.busy)
            app.show_final()
            app.geometry('1000x740')
            app.update()
            self.assertGreater(len(app.canvas.find_all()), 0)
        app.graph, app.start, app.goal = {'Solo': {}}, 'Solo', 'Solo'
        app.positions = {'Solo': (.5, .5)}
        app.start_var.set('Solo')
        app.goal_var.set('Solo')
        app.calculate()
        self.wait_until(lambda: not app.busy)
        app.show_final()
        self.assertEqual(app.results['Dijkstra'].path, ['Solo'])


if __name__ == '__main__':
    unittest.main()
