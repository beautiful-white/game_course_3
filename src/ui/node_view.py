import math
import pygame
from typing import List, Dict, Optional
from src.network.node import Node
from src.network.connection import Connection
from src.utils.colors import Colors

_R             = 18    # base node radius
_PACKET_PERIOD = 1800  # ms per packet traversal


class NodeView:
    def __init__(
        self,
        rect: pygame.Rect,
        nodes: List[Node],
        connections: List[Connection],
        font: pygame.font.Font,
    ):
        self.rect        = rect
        self.nodes       = nodes        # shared list — grows as nodes are discovered
        self.connections = connections  # shared list — grows dynamically
        self.font        = font
        self.small_font  = pygame.font.SysFont("monospace", 13)
        self.node_map: Dict[str, Node] = {n.id: n for n in nodes}
        self._glow_cache: Dict[tuple, pygame.Surface] = {}
        self.selected_id: Optional[str] = None

    # ─── helpers ────────────────────────────────────────────────────────────

    def _screen_pos(self, node: Node) -> tuple:
        return (self.rect.x + int(node.x), self.rect.y + int(node.y))

    _CORP_COLORS = {
        "Arasaka":     Colors.CORP_ARASAKA,
        "Militech":    Colors.CORP_MILITECH,
        "Kang Tao":    Colors.CORP_KANG_TAO,
        "Biotechnica": Colors.CORP_BIOTECHNICA,
        "Zetatech":    Colors.CORP_ZETATECH,
    }

    def _node_color(self, node: Node) -> tuple:
        if node.is_player:
            return Colors.NODE_PLAYER
        if node.is_hacked:
            return Colors.NODE_HACKED
        if node.is_task_target and not node.ip_visible:
            return Colors.NODE_TASK_TARGET
        if node.node_type == "mail":
            return Colors.NODE_MAIL
        if node.corporation:
            return self._CORP_COLORS.get(node.corporation, Colors.NODE_DEFAULT)
        if node.ip == "???":
            return Colors.NODE_UNKNOWN
        return Colors.NODE_DEFAULT

    def _base_glow(self, color: tuple) -> pygame.Surface:
        if color not in self._glow_cache:
            size = (_R + 24) * 2
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            cx   = size // 2
            for extra, alpha in [(20, 30), (13, 60), (7, 110)]:
                pygame.draw.circle(surf, (*color, alpha), (cx, cx), _R + extra)
            self._glow_cache[color] = surf
        return self._glow_cache[color]

    def get_node_at(self, sx: int, sy: int) -> Optional[Node]:
        for node in self.nodes:
            if not node.discovered:
                continue
            px, py = self._screen_pos(node)
            if math.hypot(sx - px, sy - py) <= _R + 8:
                return node
        return None

    # ─── drawing ────────────────────────────────────────────────────────────

    def _draw_connection(self, surface: pygame.Surface, a: Node, b: Node,
                         time_ms: int, idx: int):
        pa = self._screen_pos(a)
        pb = self._screen_pos(b)
        pygame.draw.line(surface, Colors.CONN_DEFAULT, pa, pb, 1)

        offset = (idx * 613) % _PACKET_PERIOD
        t  = ((time_ms + offset) % _PACKET_PERIOD) / _PACKET_PERIOD
        px = int(pa[0] + (pb[0] - pa[0]) * t)
        py = int(pa[1] + (pb[1] - pa[1]) * t)
        pygame.draw.circle(surface, Colors.CONN_PACKET, (px, py), 3)

    def _draw_node(self, surface: pygame.Surface, node: Node, time_ms: int):
        pos   = self._screen_pos(node)
        color = self._node_color(node)

        phase   = (hash(node.id) % 1000) / 1000.0 * math.tau
        t       = time_ms / 1000.0
        pulse   = (math.sin(t * 1.6 + phase) + 1) / 2
        flicker = (math.sin(t * 5.2 + phase * 1.9) + 1) / 2

        # Glow
        glow = self._base_glow(color)
        glow.set_alpha(int(60 + 160 * pulse))
        surface.blit(glow, (pos[0] - glow.get_width() // 2,
                             pos[1] - glow.get_height() // 2))

        # Body
        dark = tuple(c // 5 for c in color)
        pygame.draw.circle(surface, dark, pos, _R)

        # Main ring
        bright = tuple(min(255, int(c * (0.55 + 0.45 * pulse))) for c in color)
        pygame.draw.circle(surface, bright, pos, _R, 2)

        # Expanding outer ring
        outer_r     = _R + 5 + int(pulse * 12)
        outer_alpha = int(180 * (1 - pulse) ** 2)
        if outer_alpha > 6:
            sz = (outer_r + 3) * 2
            os = pygame.Surface((sz, sz), pygame.SRCALPHA)
            oc = sz // 2
            pygame.draw.circle(os, (*color, outer_alpha), (oc, oc), outer_r, 1)
            surface.blit(os, (pos[0] - oc, pos[1] - oc))

        # Center dot flicker
        dot_r = 2 + int(flicker * 3)
        dot_c = tuple(min(255, c + 80) for c in color)
        pygame.draw.circle(surface, dot_c, pos, dot_r)

        # Selected / connected ring
        if self.selected_id == node.id:
            sel_r = _R + 10 + int(pulse * 5)
            sz    = (sel_r + 3) * 2
            ss    = pygame.Surface((sz, sz), pygame.SRCALPHA)
            sc    = sz // 2
            pygame.draw.circle(ss, (*Colors.NODE_SELECTED, int(160 + 80 * pulse)),
                                (sc, sc), sel_r, 2)
            surface.blit(ss, (pos[0] - sc, pos[1] - sc))

        # Name label
        name_surf = self.font.render(node.name, True, Colors.NODE_LABEL)
        nx = pos[0] - name_surf.get_width() // 2
        ny = pos[1] + _R + 6
        surface.blit(name_surf, (nx, ny))
        next_y = ny + name_surf.get_height() + 2

        # Corporate badge — shown in company colour
        if node.corporation:
            corp_color = self._CORP_COLORS.get(node.corporation, Colors.NODE_DEFAULT)
            dim_corp   = tuple(max(0, c - 60) for c in corp_color)
            badge_surf = self.small_font.render(f"[{node.corporation}]", True, dim_corp)
            surface.blit(badge_surf, (pos[0] - badge_surf.get_width() // 2, next_y))
            next_y += badge_surf.get_height() + 1

        # IP label — hidden until ip_visible
        ip_text = node.ip if node.ip_visible else "???"
        ip_surf = self.small_font.render(ip_text, True, Colors.NODE_IP)
        surface.blit(ip_surf, (pos[0] - ip_surf.get_width() // 2, next_y))

    def draw(self, surface: pygame.Surface, time_ms: int):
        # Refresh node_map if new nodes were added
        if len(self.nodes) != len(self.node_map):
            self.node_map = {n.id: n for n in self.nodes}

        pygame.draw.rect(surface, Colors.NODE_AREA_BG, self.rect)

        # Only draw discovered nodes and connections between them
        vis_ids = {n.id for n in self.nodes if n.discovered}

        conn_idx = 0
        for conn in self.connections:
            if conn.source_id in vis_ids and conn.target_id in vis_ids:
                a = self.node_map.get(conn.source_id)
                b = self.node_map.get(conn.target_id)
                if a and b:
                    self._draw_connection(surface, a, b, time_ms, conn_idx)
                    conn_idx += 1

        for node in self.nodes:
            if node.discovered:
                self._draw_node(surface, node, time_ms)
