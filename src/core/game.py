import math
import random
import pygame
from dataclasses import dataclass
from typing import Optional, List

from src.network.connection import Connection
from src.network.exploits import (
    ALL_EXPLOITS, ALL_EXPLOIT_IDS, EXPLOIT_BY_ID, EXPLOIT_BY_CMD,
)
from src.network.generator import build_initial_network, generate_task_network
from src.network.node import Node
from src.network.task import Task
from src.ui.console import Console
from src.ui.node_view import NodeView
from src.utils.colors import Colors

WINDOW_W        = 1280
WINDOW_H        = 720
NODE_AREA_RATIO = 0.62
FPS             = 60

_BRUTE_DUR  = {"easy": (3, 6), "medium": (8, 14), "hard": (18, 28), "critical": (35, 55)}
_HACK_DUR   = {"easy": (5, 9), "medium": (12, 20), "hard": (25, 38), "critical": (42, 65)}
_DIFF_ORDER = ["easy", "medium", "hard", "critical"]


# ─── active hack state ───────────────────────────────────────────────────────

@dataclass
class _ActiveHack:
    kind: str
    duration: float
    elapsed: float = 0.0
    node_ref: object = None
    port: int = 0
    log_idx: int = -1


# ─── game ────────────────────────────────────────────────────────────────────

class Game:
    def __init__(self):
        self.screen  = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        pygame.display.set_caption("HackTerm")
        self.clock   = pygame.time.Clock()
        self.running = True

        pygame.font.init()
        pygame.key.set_repeat(380, 38)   # hold-to-repeat (backspace, arrows)
        self.mono       = pygame.font.SysFont("monospace", 20)
        self.mono_small = pygame.font.SysFont("monospace", 14)

        node_h = int(WINDOW_H * NODE_AREA_RATIO)
        self.node_rect    = pygame.Rect(0, 0,      WINDOW_W, node_h)
        self.console_rect = pygame.Rect(0, node_h, WINDOW_W, WINDOW_H - node_h)

        self.all_nodes:  List[Node]       = []
        self.all_conns:  List[Connection] = []
        self.used_names: set              = set()
        nodes, conns = build_initial_network(
            self.node_rect.width, self.node_rect.height,
            used_names=self.used_names,
        )
        self.all_nodes.extend(nodes)
        self.all_conns.extend(conns)

        self.current_node:  Optional[Node] = None
        self.current_task:  Optional[Task] = None
        self.player_money:  float          = 0.0

        self.active_hack:            Optional[_ActiveHack] = None
        self.trace_timer:            Optional[float]       = None
        self.trace_node:             Optional[Node]        = None
        self.trace_initial_duration: Optional[float]       = None

        self.unlocked_exploits: set = {"ssh_bruteforce"}

        self.node_view = NodeView(self.node_rect, self.all_nodes, self.all_conns, self.mono)
        self.console   = Console(self.console_rect, self.mono)
        self._boot_console()

    # ─── boot ────────────────────────────────────────────────────────────────

    def _boot_console(self):
        C = Colors
        for text, color in [
            ("HackTerm v0.1  —  Network Infiltration Terminal", C.CONSOLE_SYSTEM),
            ("─" * 52,                                          C.CONSOLE_DIM),
            ("[SYS]  System boot complete.",                    C.CONSOLE_SYSTEM),
            ("[SYS]  2 nodes online: home, mail.",              C.CONSOLE_SYSTEM),
            ("",                                                C.CONSOLE_TEXT),
            ("[INFO] Connect to mail for contracts and exploit market.", C.CONSOLE_DIM),
            ("[INFO] Type 'help' for commands.",                 C.CONSOLE_DIM),
        ]:
            self.console.add_line(text, color)

    # ─── events ──────────────────────────────────────────────────────────────

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_PAGEUP:
                    self.console.scroll(-8)
                elif event.key == pygame.K_PAGEDOWN:
                    self.console.scroll(8)
                else:
                    cmd = self.console.handle_keydown(event)
                    if cmd:
                        self.handle_command(cmd)

            elif event.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                if self.console_rect.collidepoint(mx, my):
                    self.console.scroll(-event.y)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if self.node_rect.collidepoint(mx, my):
                    clicked = self.node_view.get_node_at(mx, my)
                    if clicked:
                        if not clicked.ip_visible:
                            self.console.add_line(
                                "[SYS] IP unknown — use 'tasks' on mail server first.",
                                Colors.CONSOLE_DIM,
                            )
                        else:
                            cmd = f"connect {clicked.ip}"
                            self.console.add_line(f"$ {cmd}")
                            self.handle_command(cmd)

    # ─── command dispatch ────────────────────────────────────────────────────

    def handle_command(self, raw: str):
        parts = raw.strip().split()
        if not parts:
            return
        name, args = parts[0].lower(), parts[1:]

        def need_port(exploit_id: str):
            if args:
                self._start_exploit(exploit_id, args[0])
            else:
                self.console.add_line(
                    f"[ERR] Usage: {name} {{port}}", Colors.CONSOLE_ERROR)

        dispatch = {
            "bgp":         lambda: self._cmd_bgp(),
            "connect":     lambda: (self._cmd_connect(args[0]) if args
                                    else self.console.add_line(
                                        "[ERR] Usage: connect {ip}", Colors.CONSOLE_ERROR)),
            "ftp_brute":   lambda: need_port("ftp_bruteforce"),
            "hack":        lambda: self._cmd_hack(),
            "help":        lambda: self._cmd_help(),
            "market":      lambda: self._cmd_market(args),
            "probe":       lambda: self._cmd_probe(),
            "rdp_brute":   lambda: need_port("rdp_bruteforce"),
            "smtp_relay":  lambda: need_port("smtp_relay"),
            "ssh_brute":   lambda: need_port("ssh_bruteforce"),
            "stack_flood": lambda: need_port("stack_overflow"),
            "tasks":       lambda: self._cmd_tasks(),
            "web_exploit": lambda: need_port("web_exploit"),
        }
        fn = dispatch.get(name)
        if fn:
            fn()
        else:
            self.console.add_line(
                f"[ERR] Unknown command: '{name}'.  Type 'help'.", Colors.CONSOLE_ERROR)

    # ─── commands ────────────────────────────────────────────────────────────

    def _cmd_help(self):
        C = Colors

        def exploit_line(cmd_name: str, exploit_id: str, desc: str) -> tuple:
            if exploit_id in self.unlocked_exploits:
                return (f"  {cmd_name:<18} — {desc}", C.CONSOLE_TEXT)
            ed = EXPLOIT_BY_ID[exploit_id]
            return (
                f"  {cmd_name:<18} — {desc}  [locked — €${ed.market_price:,}]",
                C.CONSOLE_DIM,
            )

        lines = [
            ("", C.CONSOLE_TEXT),
            ("Commands (alphabetical):", C.CONSOLE_SYSTEM),
            ("  bgp               — discover neighbor nodes  [requires root]", C.CONSOLE_TEXT),
            ("  connect {ip}      — connect to a remote node", C.CONSOLE_TEXT),
            exploit_line("ftp_brute {port}",   "ftp_bruteforce", "bruteforce FTP credentials"),
            ("  hack              — escalate to root if all vulns exploited", C.CONSOLE_TEXT),
            ("  help              — show this message", C.CONSOLE_TEXT),
            ("  market            — exploit shop  [mail only]", C.CONSOLE_TEXT),
            ("  probe             — scan node for exploitable vulnerabilities", C.CONSOLE_TEXT),
            exploit_line("rdp_brute {port}",   "rdp_bruteforce", "bruteforce RDP credentials"),
            exploit_line("smtp_relay {port}",  "smtp_relay",     "abuse misconfigured mail relay"),
            exploit_line("ssh_brute {port}",   "ssh_bruteforce", "bruteforce SSH credentials"),
            exploit_line("stack_flood {port}", "stack_overflow",  "overflow service call stack"),
            ("  tasks             — receive / view a hack contract  [mail only]", C.CONSOLE_TEXT),
            exploit_line("web_exploit {port}", "web_exploit",    "SQL injection via web interface"),
            ("", C.CONSOLE_TEXT),
            ("  PgUp / PgDn — scroll log        ↑ / ↓ — command history", C.CONSOLE_DIM),
            ("", C.CONSOLE_TEXT),
        ]
        for text, color in lines:
            self.console.add_line(text, color)

    def _cmd_connect(self, target: str):
        C = Colors
        if target == "???":
            self.console.add_line("[ERR] IP unknown.", C.CONSOLE_ERROR)
            return


        node = next((n for n in self.all_nodes if n.ip == target), None)
        if node is None:
            by_name = [n for n in self.all_nodes if n.name == target]
            if not by_name:
                self.console.add_line(
                    f"[ERR] No route to host: {target}", C.CONSOLE_ERROR)
                return
            if len(by_name) > 1:
                # Should never happen with unique names, but handle gracefully
                self.console.add_line(
                    f"[ERR] Ambiguous name '{target}' — use IP address.", C.CONSOLE_ERROR)
                return
            candidate = by_name[0]
            if not candidate.ip_visible:
                self.console.add_line(
                    f"[ERR] IP for '{target}' is not yet known.", C.CONSOLE_ERROR)
                return
            node = candidate
        if node.is_player:
            self.console.add_line("[SYS] Already home.", C.CONSOLE_DIM)
            return
        if node is self.current_node:
            self.console.add_line(f"[SYS] Already connected to {ip}.", C.CONSOLE_DIM)
            return

        self._leave_current_node()

        if node.is_task_target and not node.ip_visible:
            node.ip_visible = True

        self.current_node          = node
        self.node_view.selected_id = node.id
        corp_tag = f"  [{node.corporation}]" if node.corporation else ""
        self.console.add_line(
            f"[SYS] Connecting to {node.ip} ({node.name}){corp_tag}...", C.CONSOLE_SYSTEM)
        self.console.add_line("[SYS] Connection established.", C.CONSOLE_SYSTEM)

    def _leave_current_node(self):
        old = self.current_node
        if not old or old.is_player:
            return
        C = Colors

        if self.active_hack and self.active_hack.node_ref is old:
            self._interrupt_hack("[INTERRUPTED]")
            self.console.add_line("[SYS] Active operation aborted.", C.CONSOLE_WARN)

        if self.trace_timer is not None and self.trace_node is old:
            self.console.add_line("[CORP] Trace interrupted by disconnection.", C.CONSOLE_ERROR)
            self._clear_trace()

        patched = [v for v in old.vulnerabilities if v.cracked]
        for v in patched:
            v.cracked = False
        if patched:
            self.console.add_line(
                "[SYS] Vulnerabilities reset — server patched on exit.", C.CONSOLE_DIM)

    def _cmd_probe(self):
        C = Colors
        if not self.current_node:
            self.console.add_line("[ERR] Not connected.  Use: connect {ip}", C.CONSOLE_ERROR)
            return

        node = self.current_node
        self.console.add_line("", C.CONSOLE_TEXT)
        self.console.add_line(f"[PROBE] Scanning {node.ip} ({node.name})...", C.CONSOLE_SYSTEM)

        if not node.vulnerabilities:
            self.console.add_line("[PROBE] No exploitable vulnerabilities found.", C.CONSOLE_DIM)
            self.console.add_line("", C.CONSOLE_TEXT)
            return

        self.console.add_line(
            f"[PROBE] {len(node.vulnerabilities)} vulnerability(ies) found:", C.CONSOLE_SYSTEM)

        for v in node.vulnerabilities:
            diff_color = {
                "easy": C.CONSOLE_TEXT, "medium": C.CONSOLE_WARN,
                "hard": (255, 140, 40), "critical": C.CONSOLE_ERROR,
            }.get(v.difficulty, C.CONSOLE_TEXT)
            status = "  [CRACKED]" if v.cracked else ""
            color  = C.CONSOLE_DIM if v.cracked else diff_color
            self.console.add_line(
                f"  [{v.difficulty.upper():8s}]  {v.name}  port {v.port}{status}", color)
            self.console.add_line(f"               {v.description}", C.CONSOLE_DIM)

        if node.corporation and self.trace_timer is None:
            duration = random.uniform(28, 60)
            self.trace_timer            = duration
            self.trace_initial_duration = duration
            self.trace_node             = node
            self.console.add_line("", C.CONSOLE_TEXT)
            self.console.add_line(
                f"[CORP] {node.corporation.upper()} trace initiated!", C.CONSOLE_ERROR)
            self.console.add_line(
                f"[CORP] You have {int(duration)}s to complete the hack.", C.CONSOLE_WARN)

        self.console.add_line("", C.CONSOLE_TEXT)

    def _cmd_bgp(self):
        C = Colors
        if not self.current_node:
            self.console.add_line("[ERR] Not connected.  Use: connect {ip}", C.CONSOLE_ERROR)
            return
        if not self.current_node.is_player and not self.current_node.is_hacked:
            self.console.add_line(
                "[ERR] BGP requires root access.  Hack this node first.", C.CONSOLE_ERROR)
            return

        node = self.current_node
        self.console.add_line(
            f"[BGP]  Route discovery on {node.name} ({node.ip})...", C.CONSOLE_SYSTEM)

        neighbor_ids = {
            (c.target_id if c.source_id == node.id else c.source_id)
            for c in self.all_conns
            if c.source_id == node.id or c.target_id == node.id
        }
        newly = [n for n in self.all_nodes if n.id in neighbor_ids and not n.discovered]
        for n in newly:
            n.discovered = True

        if newly:
            self.console.add_line(f"[BGP]  {len(newly)} new neighbor(s):", C.CONSOLE_SYSTEM)
            for n in newly:
                tag  = f"  [{n.corporation}]" if n.corporation else ""
                ip_s = n.ip if n.ip_visible else "???"
                self.console.add_line(f"       {ip_s:<20} {n.name}{tag}", C.CONSOLE_TEXT)
        else:
            self.console.add_line("[BGP]  No new neighbors discovered.", C.CONSOLE_DIM)
        self.console.add_line("", C.CONSOLE_TEXT)

    def _start_exploit(self, exploit_id: str, port_str: str):
        """Shared entry point for all port-based exploit commands."""
        C  = Colors
        ed = EXPLOIT_BY_ID[exploit_id]

        if not self.current_node or self.current_node.is_player:
            self.console.add_line("[ERR] Connect to a remote node first.", C.CONSOLE_ERROR)
            return
        if self.active_hack:
            self.console.add_line("[ERR] Another operation is already in progress.", C.CONSOLE_ERROR)
            return
        if exploit_id not in self.unlocked_exploits:
            self.console.add_line(
                f"[ERR] {ed.name} tool not available.  Buy it via 'market' on mail.",
                C.CONSOLE_ERROR)
            return

        try:
            port = int(port_str)
        except ValueError:
            self.console.add_line(f"[ERR] Invalid port: '{port_str}'", C.CONSOLE_ERROR)
            return

        node = self.current_node
        vuln = next((v for v in node.vulnerabilities if v.id == exploit_id), None)
        if not vuln:
            self.console.add_line(
                f"[{ed.tag.strip()}] No {ed.name} service found on this node.",
                C.CONSOLE_ERROR)
            return
        if vuln.cracked:
            self.console.add_line(
                f"[{ed.tag.strip()}] Already exploited.", C.CONSOLE_DIM)
            return

        if port != vuln.port:
            self.console.add_line(
                f"[{ed.tag.strip()}] Connection refused on port {port}.",
                C.CONSOLE_ERROR)
            return

        lo, hi   = _BRUTE_DUR.get(vuln.difficulty, (8, 14))
        duration = random.uniform(lo, hi)

        self.console.add_line(
            f"[{ed.tag.strip()}] Targeting {node.ip}:{port}...", C.CONSOLE_SYSTEM)
        self.console.add_line(f"[{ed.tag.strip()}] [{'░'*20}] 0%", C.CONSOLE_SYSTEM)
        log_idx = len(self.console.lines) - 1

        self.active_hack = _ActiveHack(
            kind=exploit_id, duration=duration,
            node_ref=node, port=port, log_idx=log_idx)

    def _cmd_hack(self):
        C = Colors
        if not self.current_node or self.current_node.is_player:
            self.console.add_line("[ERR] Connect to a remote node first.", C.CONSOLE_ERROR)
            return
        if self.active_hack:
            self.console.add_line("[ERR] Another operation is already in progress.", C.CONSOLE_ERROR)
            return

        node = self.current_node
        if not node.vulnerabilities:
            self.console.add_line("[ERR] No vulnerability data.  Run 'probe' first.", C.CONSOLE_ERROR)
            return

        uncracked = [v for v in node.vulnerabilities if not v.cracked]
        if uncracked:
            self.console.add_line(
                "[HACK] Error: vulnerabilities not currently active.", C.CONSOLE_ERROR)
            self.console.add_line(
                "[HACK] Exploit all vulnerabilities before escalating.", C.CONSOLE_DIM)
            return

        max_diff = max(
            (v.difficulty for v in node.vulnerabilities),
            key=lambda d: _DIFF_ORDER.index(d) if d in _DIFF_ORDER else 0,
        )
        lo, hi   = _HACK_DUR.get(max_diff, (12, 20))
        duration = random.uniform(lo, hi)

        self.console.add_line("[HACK] Injecting root exploit...", C.CONSOLE_SYSTEM)
        self.console.add_line(f"[HACK] [{'░'*20}] 0%", C.CONSOLE_SYSTEM)
        log_idx = len(self.console.lines) - 1

        self.active_hack = _ActiveHack(
            kind="hack", duration=duration, node_ref=node, log_idx=log_idx)

    def _cmd_tasks(self):
        C = Colors
        if not self.current_node or self.current_node.node_type != "mail":
            self.console.add_line(
                "[ERR] Mail server only.  Connect to 'mail' first.", C.CONSOLE_ERROR)
            return

        if self.current_task and not self.current_task.completed:
            t   = self.current_task
            sep = "─" * 46
            self.console.add_line("", C.CONSOLE_TEXT)
            self.console.add_line("[MAIL] Active contract:", C.CONSOLE_SYSTEM)
            self.console.add_line(sep, C.CONSOLE_DIM)
            self.console.add_line(f"[TASK] Target:  {t.target_node.ip}", C.CONSOLE_ERROR)
            self.console.add_line(f"[TASK] Reward:  €${t.reward:,.0f}", Colors.NODE_SELECTED)
            self.console.add_line("[TASK] Gain root access to complete.", C.CONSOLE_DIM)
            self.console.add_line(sep, C.CONSOLE_DIM)
            self.console.add_line("", C.CONSOLE_TEXT)
            return

        self.console.add_line("[MAIL] Fetching contracts...", C.CONSOLE_SYSTEM)

        player_ordered = [eid for eid in ALL_EXPLOIT_IDS if eid in self.unlocked_exploits]
        target, new_nodes, new_conns = generate_task_network(
            self.node_rect.width, self.node_rect.height,
            [(n.x, n.y) for n in self.all_nodes],
            player_exploits=player_ordered,
            used_names=self.used_names,
        )
        reward = round(random.uniform(800, 8000) / 50) * 50
        self.all_nodes.extend(new_nodes)
        self.all_conns.extend(new_conns)
        self.current_task = Task(target_node=target, reward=reward)

        sep = "─" * 46
        self.console.add_line("", C.CONSOLE_TEXT)
        self.console.add_line("[MAIL] New contract received:", C.CONSOLE_SYSTEM)
        self.console.add_line(sep, C.CONSOLE_DIM)
        self.console.add_line("[TASK] Objective: gain root access on target node.", C.CONSOLE_TEXT)
        self.console.add_line(f"[TASK] Target IP:  {target.ip}", C.CONSOLE_ERROR)
        self.console.add_line(f"[TASK] Reward:     €${reward:,.0f}", Colors.NODE_SELECTED)
        self.console.add_line(sep, C.CONSOLE_DIM)
        self.console.add_line("[TASK] Target marked red on map — connect to reveal.", C.CONSOLE_DIM)
        self.console.add_line("", C.CONSOLE_TEXT)

    def _cmd_market(self, args: list):
        C = Colors
        if not self.current_node or self.current_node.node_type != "mail":
            self.console.add_line(
                "[ERR] Market is only accessible from the mail server.", C.CONSOLE_ERROR)
            return

        if args and args[0] == "buy":
            if len(args) < 2:
                self.console.add_line("[ERR] Usage: market buy {command}", C.CONSOLE_ERROR)
                return
            self._market_buy(args[1])
            return

        self.console.add_line("", C.CONSOLE_TEXT)
        self.console.add_line("[MARKET] ▓ Dark Net Exploit Market ▓", C.CONSOLE_SYSTEM)
        self.console.add_line("─" * 55, C.CONSOLE_DIM)
        self.console.add_line(
            f"  {'STATUS':<8}  {'COMMAND':<14} {'EXPLOIT':<24} PRICE",
            C.CONSOLE_DIM)
        self.console.add_line("─" * 55, C.CONSOLE_DIM)

        for ed in ALL_EXPLOITS:
            if ed.id in self.unlocked_exploits:
                status, price_str, color = "[OWNED]", "    ---", C.CONSOLE_DIM
            else:
                status, price_str, color = "[ BUY ]", f"€${ed.market_price:>5,}", C.CONSOLE_WARN
            self.console.add_line(
                f"  {status}  {ed.cmd:<14} {ed.name:<24} {price_str}", color)

        self.console.add_line("─" * 55, C.CONSOLE_DIM)
        self.console.add_line(
            f"[MARKET] Balance: €${self.player_money:,.0f}", C.CONSOLE_SYSTEM)
        self.console.add_line(
            "[MARKET] To purchase:  market buy {command}", C.CONSOLE_DIM)
        self.console.add_line("", C.CONSOLE_TEXT)

    def _market_buy(self, cmd: str):
        C  = Colors
        ed = EXPLOIT_BY_CMD.get(cmd)
        if not ed:
            self.console.add_line(f"[ERR] Unknown exploit: '{cmd}'.  Run 'market' to see list.",
                                   C.CONSOLE_ERROR)
            return
        if ed.market_price == 0:
            self.console.add_line(
                f"[MARKET] '{cmd}' is included by default and is not for sale.", C.CONSOLE_DIM)
            return
        if ed.id in self.unlocked_exploits:
            self.console.add_line(f"[MARKET] You already own '{cmd}'.", C.CONSOLE_DIM)
            return
        if self.player_money < ed.market_price:
            self.console.add_line(
                f"[MARKET] Insufficient funds.  Need €${ed.market_price:,},"
                f" have €${self.player_money:,.0f}.",
                C.CONSOLE_ERROR)
            return

        self.player_money -= ed.market_price
        self.unlocked_exploits.add(ed.id)
        self.console.add_line("", C.CONSOLE_TEXT)
        self.console.add_line(f"[MARKET] '{cmd}' ({ed.name}) acquired.", C.CONSOLE_SYSTEM)
        self.console.add_line(
            f"[MARKET] Balance: €${self.player_money:,.0f}", C.CONSOLE_TEXT)
        self.console.add_line("", C.CONSOLE_TEXT)

    # ─── async hack progress ─────────────────────────────────────────────────

    @staticmethod
    def _bar_tag(kind: str) -> str:
        if kind == "hack":
            return "[HACK]"
        ed = EXPLOIT_BY_ID.get(kind)
        return f"[{ed.tag.strip()[:4]:4s}]" if ed else "[EXPL]"

    def _update_hack(self, dt_ms: int):
        if not self.active_hack:
            return
        h         = self.active_hack
        h.elapsed += dt_ms / 1000.0
        progress  = min(1.0, h.elapsed / h.duration)

        if 0 <= h.log_idx < len(self.console.lines):
            filled = int(20 * progress)
            bar    = "█" * filled + "░" * (20 - filled)
            pct    = int(progress * 100)
            _, clr = self.console.lines[h.log_idx]
            self.console.lines[h.log_idx] = (
                f"{self._bar_tag(h.kind)} [{bar}] {pct}%", clr)

        if progress >= 1.0:
            self._finish_hack()

    def _interrupt_hack(self, label: str = "[INTERRUPTED]"):
        h = self.active_hack
        if not h:
            return
        if 0 <= h.log_idx < len(self.console.lines):
            _, clr = self.console.lines[h.log_idx]
            self.console.lines[h.log_idx] = (
                f"{self._bar_tag(h.kind)} {'░'*20} {label}", clr)
        self.active_hack = None

    def _finish_hack(self):
        h = self.active_hack
        self.active_hack = None

        if 0 <= h.log_idx < len(self.console.lines):
            _, clr = self.console.lines[h.log_idx]
            self.console.lines[h.log_idx] = (
                f"{self._bar_tag(h.kind)} [{'█'*20}] DONE", clr)

        if h.kind == "hack":
            self._resolve_hack(h)
        else:
            self._resolve_exploit(h)

    def _resolve_exploit(self, h: _ActiveHack):
        if h.node_ref is not self.current_node:
            return
        node = h.node_ref
        vuln = next((v for v in node.vulnerabilities if v.id == h.kind), None)
        if not vuln:
            return
        ed        = EXPLOIT_BY_ID[h.kind]
        vuln.cracked = True
        self.console.add_line(
            f"[{ed.tag.strip()}] {ed.name} exploited on {node.ip}:{h.port}.",
            Colors.CONSOLE_TEXT)
        self.console.add_line("", Colors.CONSOLE_TEXT)

    def _resolve_hack(self, h: _ActiveHack):
        C = Colors
        if h.node_ref is not self.current_node:
            return
        node           = h.node_ref
        node.is_hacked = True

        if node.corporation:
            max_diff = max(
                (v.difficulty for v in node.vulnerabilities),
                key=lambda d: _DIFF_ORDER.index(d) if d in _DIFF_ORDER else 0,
                default="easy",
            )
            diff_multi  = {"easy": 1.0, "medium": 1.2, "hard": 1.5, "critical": 2.0}[max_diff]
            init_dur    = self.trace_initial_duration or 44.0
            time_factor = max(0.0, min(1.0, (60.0 - init_dur) / 32.0))
            corp_reward = min(5000, int((1000 + int(4000 * time_factor)) * diff_multi))
            corp_reward = round(corp_reward / 50) * 50
            self.player_money += corp_reward
            self.console.add_line(
                f"[CORP] Infiltration bounty: €${corp_reward:,}", Colors.NODE_SELECTED)

        if self.trace_node is node:
            self._clear_trace()

        self.console.add_line(
            f"[HACK] ROOT ACCESS GRANTED — {node.name} ({node.ip})", C.CONSOLE_SYSTEM)

        # Task completion check
        if self.current_task and self.current_task.target_node is node:
            reward             = self.current_task.reward
            self.player_money += reward
            self.current_task  = None
            sep = "─" * 46
            self.console.add_line(sep, C.CONSOLE_DIM)
            self.console.add_line("[TASK] Mission accomplished!", Colors.NODE_SELECTED)
            self.console.add_line(f"[TASK] Payment:  €${reward:,.0f}", Colors.NODE_SELECTED)
            self.console.add_line(f"[TASK] Balance:  €${self.player_money:,.0f}", C.CONSOLE_SYSTEM)
            self.console.add_line(sep, C.CONSOLE_DIM)
        self.console.add_line("", C.CONSOLE_TEXT)

    # ─── trace timer ─────────────────────────────────────────────────────────

    def _clear_trace(self):
        self.trace_timer            = None
        self.trace_node             = None
        self.trace_initial_duration = None

    def _update_trace(self, dt_ms: int):
        if self.trace_timer is None:
            return
        self.trace_timer -= dt_ms / 1000.0
        if self.trace_timer <= 0:
            self._trace_timeout()

    def _trace_timeout(self):
        C    = Colors
        node = self.trace_node
        corp = (node.corporation or "UNKNOWN").upper() if node else "UNKNOWN"

        if self.active_hack and self.active_hack.node_ref is node:
            self._interrupt_hack("[ABORTED]")

        if node:
            for v in node.vulnerabilities:
                v.cracked = False

        stolen            = self.player_money
        self.player_money = 0.0
        self._clear_trace()

        self.console.add_line("", C.CONSOLE_TEXT)
        self.console.add_line(
            f"[CORP] !! TRACE COMPLETE — {corp} security response !!",
            C.CONSOLE_ERROR)
        self.console.add_line(
            "[CORP] All node vulnerabilities remotely patched.", C.CONSOLE_ERROR)
        if stolen > 0:
            self.console.add_line(
                f"[CORP] {corp} seized €${stolen:,.0f} from all linked accounts.",
                C.CONSOLE_ERROR)
        self.console.add_line("", C.CONSOLE_TEXT)

    # ─── draw ────────────────────────────────────────────────────────────────

    def _draw_hud(self):
        font = self.mono_small
        y    = 6
        if self.current_node and not self.current_node.is_player:
            txt   = f"  ■ {self.current_node.name}  [{self.current_node.ip}]"
            color = Colors.CONSOLE_SYSTEM
        elif self.current_node:
            txt, color = "  ■ HOME", Colors.NODE_PLAYER
        else:
            txt, color = "  ○ OFFLINE", Colors.CONSOLE_DIM
        self.screen.blit(font.render(txt, True, color), (6, y))

        money = font.render(f"€$ {self.player_money:,.0f}  ", True, Colors.NODE_SELECTED)
        self.screen.blit(money, (WINDOW_W - money.get_width() - 4, y))

    def _draw_trace_timer(self, time_ms: int):
        if self.trace_timer is None or self.trace_node is None:
            return
        secs = max(0, int(self.trace_timer))
        m, s = divmod(secs, 60)
        corp = (self.trace_node.corporation or "UNKNOWN").upper()

        pulse = (math.sin(time_ms / 350.0) + 1) / 2
        r     = int(200 + 55 * pulse)

        text = f"  ▶  TRACE: {corp}  ·  {m}:{s:02d}  ◀  "
        surf = self.mono.render(text, True, (r, 25, 25))
        x    = (WINDOW_W - surf.get_width()) // 2
        y    = self.node_rect.bottom - surf.get_height() - 8

        bg = pygame.Surface((surf.get_width() + 20, surf.get_height() + 8), pygame.SRCALPHA)
        bg.fill((50, 0, 0, 190))
        self.screen.blit(bg, (x - 10, y - 4))
        self.screen.blit(surf, (x, y))

    def draw(self, time_ms: int):
        self.node_view.draw(self.screen, time_ms)
        self._draw_hud()
        self._draw_trace_timer(time_ms)
        self.console.draw(self.screen)
        pygame.draw.line(
            self.screen, Colors.DIVIDER,
            (0, self.node_rect.bottom), (WINDOW_W, self.node_rect.bottom), 2)
        pygame.display.flip()

    # ─── main loop ───────────────────────────────────────────────────────────

    def run(self):
        while self.running:
            dt      = self.clock.tick(FPS)
            time_ms = pygame.time.get_ticks()
            self.handle_events()
            self._update_hack(dt)
            self._update_trace(dt)
            self.console.update(dt)
            self.draw(time_ms)
