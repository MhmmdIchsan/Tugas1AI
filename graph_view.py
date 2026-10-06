"""Graph canvas adapted from Irfan's renderer, with Ichsan playback integration.

Dark canvas, Bézier edges, particles, pulses, predecessor tree and path reveal
are retained. View transforms never change graph weights or replay state.
"""
from __future__ import annotations
import math
from time import perf_counter
import tkinter as tk
import tkinter.font as tkfont
from comparison import format_number
from layout import graph_positions

BG = "#0b1120"
SURFACE = "#0f172a"
CARD = "#131c31"
CARD2 = "#1b2640"
BORDER = "#26324d"
INK = "#e2e8f0"
MUTED = "#8394b0"
EDGE = "#34425f"
TREE = "#5b7bb8"
CYAN = "#22d3ee"
GREEN = "#34d399"
RED = "#fb7185"
AMBER = "#fbbf24"
VIOLET = "#a78bfa"
BLUE = "#60a5fa"
ALGO_COLORS = {"Dijkstra": "#38bdf8", "Bellman–Ford": "#c084fc"}
STORY_COLORS = {"idle": MUTED, "pass": BLUE, "visit": VIOLET, "inspect": CYAN,
                "skip": MUTED, "relax": AMBER, "done": GREEN}
FRAME_MS = 33
INF = math.inf


def mix(color: str, other: str, amount: float) -> str:
    """Blend two #rrggbb colors; Tk canvas has no alpha, so glows are blends."""
    a = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(other[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * amount):02x}" for x, y in zip(a, b))


def bezier(curve, t: float) -> tuple[float, float]:
    """Point on a quadratic Bézier (start, control, end); edges and particles share it."""
    (x0, y0), (mx, my), (x2, y2) = curve
    a, b, c = (1 - t) ** 2, 2 * (1 - t) * t, t * t
    return a * x0 + b * mx + c * x2, a * y0 + b * my + c * y2


def sample(curve, end: float = 1.0, count: int = 14) -> list[float]:
    return [coord for k in range(count + 1) for coord in bezier(curve, end * k / count)]


def ease(t: float) -> float:
    return 1 - (1 - min(max(t, 0.0), 1.0)) ** 3


def num(value) -> str:
    return "∞" if value == INF else format_number(value)


class GraphCanvas(tk.Canvas):
    def __init__(self, master, on_hover=None, on_endpoint=None, **kwargs):
        kwargs['bg'] = CARD
        super().__init__(master, **kwargs)
        self.canvas = self
        families = set(tkfont.families(self))
        self.family = next((f for f in ('Inter', 'Segoe UI', 'Noto Sans', 'DejaVu Sans') if f in families), 'sans-serif')
        self.mono = next((f for f in ('JetBrains Mono', 'Consolas', 'DejaVu Sans Mono') if f in families), 'monospace')
        self.on_hover, self.on_endpoint = on_hover, on_endpoint
        self.graph, self.results, self.positions, self.pixel_positions = {}, {}, {}, {}
        self.edge_paths, self.dist, self.prev = {}, {}, {}
        self.start = self.goal = ''
        self.events, self.visited = [], set()
        self.current = self.active_edge = self.updated = self.hovered = self.dragged = None
        self.finished = self.busy = False
        self.radius = 22
        self.bounds = (60., 70., 1., 1.)
        self.edge_started = self.reveal_started = 0.
        self.algorithm = tk.StringVar(self, value='Dijkstra')
        self.speed = tk.DoubleVar(self, value=420)
        self.zoom = 1.
        self.pan = (0., 0.)
        self.pan_anchor = None
        self.bind('<Configure>', self._on_resize)
        self.bind('<Motion>', self._hover)
        self.bind('<Leave>', self._leave)
        self.bind('<ButtonPress-1>', self._press)
        self.bind('<B1-Motion>', self._drag)
        self.bind('<ButtonRelease-1>', self._release)
        self.bind('<Button-3>', self._context_menu)
        self.bind('<MouseWheel>', lambda e: self._zoom(1.12 if e.delta > 0 else 1/1.12, e.x, e.y))
        self.bind('<Button-4>', lambda e: self._zoom(1.12, e.x, e.y))
        self.bind('<Button-5>', lambda e: self._zoom(1/1.12, e.x, e.y))
        self.frame_timer = self.after(FRAME_MS, self._frame)

    def set_graph(self, graph, start, goal):
        changed = graph is not self.graph
        self.graph, self.start, self.goal = graph, start, goal
        self.radius = 22 if len(graph) <= 20 else max(11, 22-(len(graph)-20)//6)
        if changed:
            self.positions = graph_positions(graph)
            self.zoom, self.pan = 1., (0., 0.)
        self.hovered = self.dragged = None
        self.dist = {v: 0 if v == start else INF for v in graph}
        self.prev, self.results, self.visited, self.events = {}, {}, set(), []
        self.current = self.active_edge = self.updated = None
        self.finished = False
        self.draw_graph()

    def set_playback(self, state, animate=True, delay=420):
        now = perf_counter()
        new_result = self.results.get(state.result.name) is not state.result
        changed_edge = self.active_edge != state.active_edge
        if changed_edge or (state.updated and animate):
            self.edge_started = now
        if state.finished and (not self.finished or new_result):
            self.reveal_started = now if animate else now - 100
        self.algorithm.set(state.result.name)
        self.results = {state.result.name: state.result}
        self.events = state.result.steps
        self.dist, self.prev = dict(state.distances), dict(state.previous)
        self.visited = set(state.visited)
        self.current, self.active_edge, self.updated = state.current, state.active_edge, state.updated
        self.finished = state.finished
        self.speed.set(delay)
        self.draw_graph()

    def _status_of(self, vertex):
        if vertex in self.visited:
            return 'final'
        result = self.results.get(self.algorithm.get())
        if self.finished and result and not result.trace_truncated:
            if vertex in result.path or (result.name == 'Bellman–Ford' and self.dist.get(vertex, INF) != INF):
                return 'final'
        return 'sementara' if self.dist.get(vertex, INF) != INF else 'belum'

    def _press(self, event):
        self.dragged = self._node_at(event.x, event.y)
        self.pan_anchor = None if self.dragged else (event.x, event.y, *self.pan)

    def _release(self, _event):
        self.dragged = self.pan_anchor = None

    def _leave(self, _event):
        self.hovered = None
        if self.on_hover:
            self.on_hover(None)

    def _drag(self, event):
        if self.dragged:
            left, top, sx, sy = self.bounds
            self.positions[self.dragged] = ((event.x-left)/sx, (event.y-top)/sy)
            self.draw_graph()
        elif self.pan_anchor:
            x, y, px, py = self.pan_anchor
            self.pan = (px+event.x-x, py+event.y-y)
            self.draw_graph()

    def _context_menu(self, event):
        node = self._node_at(event.x, event.y)
        if node is None or self.busy or self.on_endpoint is None:
            return
        menu = tk.Menu(self, tearoff=0, bg=CARD2, fg=INK, activebackground=SURFACE, activeforeground=CYAN)
        menu.add_command(label=f'Jadikan {node} titik awal', command=lambda: self.on_endpoint('start', node))
        menu.add_command(label=f'Jadikan {node} tujuan', command=lambda: self.on_endpoint('goal', node))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
            menu.destroy()

    def _zoom(self, factor, x=None, y=None):
        width, height = self._canvas_size()
        x, y = width/2 if x is None else x, height/2 if y is None else y
        old = self.zoom
        self.zoom = min(3., max(.5, self.zoom*factor))
        ratio = self.zoom/old
        px, py = self.pan
        self.pan = (x-width/2-(x-width/2-px)*ratio, y-height/2-(y-height/2-py)*ratio)
        self.draw_graph()

    def zoom_in(self):
        self._zoom(1.12)

    def zoom_out(self):
        self._zoom(1/1.12)

    def reset_view(self):
        self.positions = graph_positions(self.graph)
        self.zoom, self.pan = 1., (0., 0.)
        self.draw_graph()

    def dispose(self):
        if self.frame_timer is not None:
            self.after_cancel(self.frame_timer)
            self.frame_timer = None

    def _font(self, size: int, weight: str = "normal", mono: bool = False):
        return (self.mono if mono else self.family, size, weight)

    def _canvas_size(self) -> tuple[int, int]:
        return max(self.canvas.winfo_width(), 120), max(self.canvas.winfo_height(), 120)

    def _node_at(self, x: float, y: float) -> str | None:
        return next((v for v, (vx, vy) in self.pixel_positions.items()
                     if math.hypot(x - vx, y - vy) <= self.radius + 4), None)

    def _hover(self, event) -> None:
        node = self._node_at(event.x, event.y)
        if node != self.hovered:
            self.hovered = node
            self.canvas.configure(cursor="fleur" if node else "")
            if self.on_hover:
                self.on_hover(node)

    def _on_resize(self, _event=None) -> None:
        canvas = self.canvas
        canvas.delete("grid")
        width, height = self._canvas_size()
        dot = mix(BORDER, CARD, 0.35)
        for x in range(16, width, 28):
            for y in range(16, height, 28):
                canvas.create_rectangle(x, y, x + 1, y + 1, fill=dot, outline="", tags="grid")
        canvas.tag_lower("grid")
        self.draw_graph()

    def draw_graph(self) -> None:
        if not hasattr(self, "canvas"):
            return
        canvas = self.canvas
        canvas.delete("graph")
        width, height = self._canvas_size()
        if not self.graph:
            canvas.create_text(width / 2, height / 2, text="Buka graf.txt untuk memulai", fill=MUTED,
                               font=self._font(13), tags="graph")
            return
        r = self.radius
        sx, sy = max(width-120., 1.)*self.zoom, max(height-156., 1.)*self.zoom
        self.bounds = (width/2-sx/2+self.pan[0], height/2-sy/2+self.pan[1], sx, sy)
        left, top, span_x, span_y = self.bounds
        positions = {v: (left + x * span_x, top + y * span_y) for v, (x, y) in self.positions.items()}
        self.pixel_positions = positions
        result = self.results.get(self.algorithm.get())
        tree = {(p, v) for v, p in self.prev.items()}
        self.edge_paths = {}
        drawn, labels = set(), []
        for vertex, neighbors in self.graph.items():
            for neighbor, weight in neighbors.items():
                reciprocal = self.graph[neighbor].get(vertex) == weight
                key = tuple(sorted((vertex, neighbor))) if reciprocal else (vertex, neighbor)
                x1, y1 = positions[vertex]
                if vertex == neighbor:
                    if key not in drawn:
                        drawn.add(key)
                        canvas.create_line(x1 - r * .6, y1 - r * .8, x1 - r * 1.7, y1 - r * 2.6,
                                           x1 + r * 1.7, y1 - r * 2.6, x1 + r * .6, y1 - r * .8,
                                           smooth=True, fill=EDGE, width=1.6, arrow="last", tags="graph")
                        labels.append((x1, y1 - r * 2.3, weight, EDGE))
                    continue
                x2, y2 = positions[neighbor]
                distance = max(math.hypot(x2 - x1, y2 - y1), 0.001)
                ux, uy = (x2 - x1) / distance, (y2 - y1) / distance
                # Opposite arcs with different weights bend to opposite sides.
                bend = 0 if reciprocal or vertex not in self.graph[neighbor] else 36
                tail = r + (2 if reciprocal else 5)
                curve = ((x1 + ux * (r + 2), y1 + uy * (r + 2)),
                         ((x1 + x2) / 2 - uy * bend, (y1 + y2) / 2 + ux * bend),
                         (x2 - ux * tail, y2 - uy * tail))
                self.edge_paths[(vertex, neighbor)] = curve
                if key in drawn:
                    continue
                drawn.add(key)
                in_tree = (vertex, neighbor) in tree or (reciprocal and (neighbor, vertex) in tree)
                color = TREE if in_tree else EDGE
                canvas.create_line(*(sample(curve) if bend else (*curve[0], *curve[2])), fill=color,
                                   width=2.6 if in_tree else 1.6, capstyle="round",
                                   arrow="none" if reciprocal else "last", arrowshape=(10, 12, 4), tags="graph")
                labels.append((*bezier(curve, 0.5), weight, color))
        for x, y, weight, color in labels:
            text = canvas.create_text(x, y, text=format_number(weight), fill=INK if color == TREE else MUTED,
                                      font=self._font(8, mono=True), tags=("graph", "label"))
            x0, y0, x1, y1 = canvas.bbox(text)
            box = canvas.create_rectangle(x0 - 4, y0 - 1, x1 + 4, y1 + 1, fill=CARD, outline=color,
                                          tags=("graph", "label"))
            canvas.tag_lower(box, text)
        route = set(result.path) if self.finished and result else set()
        for vertex, (x, y) in positions.items():
            known = self.dist.get(vertex, INF) != INF
            accent = (GREEN if vertex == self.start else RED if vertex == self.goal
                      else AMBER if vertex == self.current else CYAN if vertex in route
                      else VIOLET if vertex in self.visited else TREE if known else EDGE)
            if accent in (GREEN, RED, CYAN):
                for blend, extra in ((0.9, 10), (0.82, 5)):
                    canvas.create_oval(x - r - extra, y - r - extra, x + r + extra, y + r + extra,
                                       fill=mix(accent, CARD, blend), outline="", tags=("graph", "node"))
            fill = CARD2 if accent == EDGE else mix(accent, CARD, 0.78)
            canvas.create_oval(x - r, y - r, x + r, y + r, fill=fill, outline=accent, width=2.5,
                               tags=("graph", "node"))
            canvas.create_text(x, y, text=vertex, fill=INK, font=self._font(max(7, int(r * 0.42)), "bold"),
                               tags=("graph", "node"))
            if self.events:
                canvas.create_text(x + r * 0.75, y - r * 0.85, text=num(self.dist.get(vertex, INF)), anchor="sw",
                                   fill=AMBER if vertex == self.updated else INK if known else MUTED,
                                   font=self._font(8, "bold", mono=True), tags=("graph", "node"))
            marker = ("AWAL · TUJUAN" if vertex == self.start == self.goal else "AWAL" if vertex == self.start
                      else "TUJUAN" if vertex == self.goal else "")
            if marker:
                canvas.create_text(x, y + r + 12, text=marker, fill=accent, font=self._font(7, "bold"),
                                   tags=("graph", "node"))
        name = self.algorithm.get()
        if self.finished and result:
            banner = (f"Jalur terpendek   {' → '.join(result.path)}   ·   bobot {num(result.cost)}"
                      if result.path else f"{self.goal} tidak terjangkau dari {self.start}")
            color = CYAN if result.path else RED
        else:
            banner, color = f"{name}   ·   {self.start} → {self.goal}", ALGO_COLORS.get(name, CYAN)
        text = canvas.create_text(30, 26, anchor="nw", text=banner, fill=color, font=self._font(10, "bold"), width=max(100, width-70), justify="left",
                                  tags="graph")
        x0, y0, x1, y1 = canvas.bbox(text)
        box = canvas.create_rectangle(x0 - 12, y0 - 7, x1 + 12, y1 + 7, fill=mix(color, CARD, 0.86),
                                      outline=mix(color, CARD, 0.4), tags="graph")
        canvas.tag_lower(box, text)
        hint = canvas.create_text(width - 20, 22, anchor="ne", text="seret simpul · klik kanan: jadikan awal/tujuan",
                                  fill=mix(MUTED, CARD, 0.3), font=self._font(9), tags="graph")
        if canvas.bbox(hint)[0] < x1 + 24:
            canvas.delete(hint)
        x = 22
        for label, color in (("Awal", GREEN), ("Tujuan", RED), ("Diproses", AMBER), ("Ditetapkan", VIOLET),
                             ("Jarak diketahui", TREE), ("Jalur terpendek", CYAN)):
            canvas.create_oval(x, height - 28, x + 10, height - 18, fill=color, outline="", tags="graph")
            item = canvas.create_text(x + 16, height - 23, text=label, anchor="w", fill=MUTED,
                                      font=self._font(9), tags="graph")
            x = canvas.bbox(item)[2] + 18
            if x > width - 110:
                break

    def _frame(self) -> None:
        """Animation clock: redraw only the cheap fx/tip layers every frame."""
        self.frame_timer = self.after(FRAME_MS, self._frame)
        canvas, now = self.canvas, perf_counter()
        canvas.delete("fx", "tip")
        width, height = self._canvas_size()
        if self.busy:
            angle = now * 360 % 360
            canvas.create_oval(width / 2 - 40, height / 2 - 40, width / 2 + 40, height / 2 + 64,
                               fill=CARD, outline="", tags="tip")
            canvas.create_arc(width / 2 - 22, height / 2 - 22, width / 2 + 22, height / 2 + 22, start=-angle,
                              extent=270, style="arc", outline=CYAN, width=4, tags="tip")
            canvas.create_text(width / 2, height / 2 + 42, text="Menghitung…", fill=MUTED,
                               font=self._font(9), tags="tip")
        if not self.graph or not self.pixel_positions:
            return
        r, positions = self.radius, self.pixel_positions
        pulse = (math.sin(now * 6) + 1) / 2
        if self.current in positions and not self.finished:
            x, y = positions[self.current]
            for spread, blend in ((5 + pulse * 7, 0.35 + pulse * 0.5), (3, 0.2)):
                e = r + spread
                canvas.create_oval(x - e, y - e, x + e, y + e, outline=mix(AMBER, CARD, blend), width=2,
                                   tags="fx")
        curve = self.edge_paths.get(self.active_edge) if self.active_edge else None
        if curve:
            points = sample(curve)
            canvas.create_line(*points, fill=mix(AMBER, CARD, 0.65), width=8, capstyle="round", tags="fx")
            canvas.create_line(*points, fill=AMBER, width=2.5, capstyle="round", tags="fx")
            duration = min(max(self.speed.get(), 150), 700) / 1000
            px, py = bezier(curve, ease((now - self.edge_started) / duration))
            canvas.create_oval(px - 7, py - 7, px + 7, py + 7, fill=mix(AMBER, CARD, 0.45), outline="", tags="fx")
            canvas.create_oval(px - 3.5, py - 3.5, px + 3.5, py + 3.5, fill="#fff7d6", outline="", tags="fx")
        result = self.results.get(self.algorithm.get())
        if self.finished and result and len(result.path) > 1:
            segments = list(zip(result.path, result.path[1:]))
            progress = (now - self.reveal_started) / 0.22
            for index, edge in enumerate(segments):
                part = min(progress - index, 1)
                if part <= 0:
                    break
                if edge in self.edge_paths:
                    points = sample(self.edge_paths[edge], part)
                    canvas.create_line(*points, fill=mix(CYAN, CARD, 0.7), width=11, capstyle="round", tags="fx")
                    canvas.create_line(*points, fill=CYAN, width=4, capstyle="round", tags="fx")
            if progress >= len(segments):
                travel = (now - self.reveal_started) * 0.5 % 1 * len(segments)
                edge = segments[int(travel)]
                if edge in self.edge_paths:
                    px, py = bezier(self.edge_paths[edge], travel % 1)
                    canvas.create_oval(px - 5, py - 5, px + 5, py + 5, fill="#e0fbff", outline="", tags="fx")
        anchor = canvas.find_withtag("label") or canvas.find_withtag("node")
        if anchor:
            canvas.tag_lower("fx", anchor[0])
        if self.hovered in positions and self.dragged is None:
            vertex = self.hovered
            x, y = positions[vertex]
            lines = (f"{vertex}", f"jarak     {num(self.dist.get(vertex, INF))}",
                     f"via       {self.prev.get(vertex, '—')}", f"status    {self._status_of(vertex)}",
                     f"tetangga  {len(self.graph[vertex])}")
            text = canvas.create_text(x + r + 14, y - r, anchor="nw", text="\n".join(lines), fill=INK,
                                      font=self._font(9, mono=True), tags="tip")
            x0, y0, x1, y1 = canvas.bbox(text)
            dx = -(x1 - x0) - 2 * r - 28 if x1 > width - 8 else 0
            dy = min(height - 12 - y1, 0) + max(12 - y0, 0)
            if dx or dy:
                canvas.move(text, dx, dy)
                x0, y0, x1, y1 = canvas.bbox(text)
            box = canvas.create_rectangle(x0 - 10, y0 - 8, x1 + 10, y1 + 8, fill=SURFACE, outline=BORDER,
                                          tags="tip")
            canvas.tag_lower(box, text)

