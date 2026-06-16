import math
import random
from typing import List, Optional

from src.network.connection import Connection
from src.network.exploits import ALL_EXPLOITS, ALL_EXPLOIT_IDS, EXPLOIT_BY_ID
from src.network.node import Node
from src.network.vulnerability import Vulnerability

# ─── cyberpunk companies ─────────────────────────────────────────────────────

_COMPANIES = ["Arasaka", "Militech", "Kang Tao", "Biotechnica", "Zetatech"]

_CORP_DEFS = {
    "Arasaka":     ("arasaka", ["vault",    "sec",    "ops",   "corp",   "admin", "intel"]),
    "Militech":    ("mtc",     ["ops",      "strike", "recon", "cmd",    "fire",  "sys"  ]),
    "Kang Tao":    ("kt",      ["research", "arms",   "prod",  "data",   "eng",   "dev"  ]),
    "Biotechnica": ("btech",   ["lab",      "gene",   "farm",  "bio",    "med",   "sync" ]),
    "Zetatech":    ("zeta",    ["dev",      "ai",     "cloud", "core",   "net",   "grid" ]),
}

_CORP_CHANCE = 0.20


def _corp_name(company: str) -> str:
    prefix, roles = _CORP_DEFS[company]
    return f"{prefix}-{random.choice(roles)}-{random.randint(1,99):02d}"


# ─── generic hostname / IP pools ─────────────────────────────────────────────

_PREFIXES = [
    "gw", "fw", "sw", "srv", "host", "node", "nas", "vpn", "dns",
    "web", "db", "api", "auth", "log", "mon", "bkp", "ftp", "smtp",
    "ldap", "proxy", "edge", "core", "router", "dc", "store",
]
_SUFFIXES = ["corp", "net", "sys", "svc", "int", "dmz", "lan", "prv"]


def _random_name() -> str:
    prefix = random.choice(_PREFIXES)
    n = random.randint(1, 99)
    if random.random() < 0.45:
        return f"{prefix}-{random.choice(_SUFFIXES)}-{n:02d}"
    return f"{prefix}-{n:02d}"


def _unique_name(used: set) -> str:
    for _ in range(600):
        name = _random_name()
        if name not in used:
            used.add(name)
            return name
    # Fallback: append extra digits to guarantee uniqueness
    while True:
        name = f"{_random_name()}-{random.randint(100, 999)}"
        if name not in used:
            used.add(name)
            return name


def _unique_corp_name(company: str, used: set) -> str:
    for _ in range(600):
        name = _corp_name(company)
        if name not in used:
            used.add(name)
            return name
    while True:
        name = f"{_corp_name(company)}-{random.randint(100, 999)}"
        if name not in used:
            used.add(name)
            return name


def _random_ip() -> str:
    pool = random.randint(0, 3)
    if pool == 0:
        return f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
    elif pool == 1:
        return f"172.{random.randint(16,31)}.{random.randint(0,255)}.{random.randint(1,254)}"
    elif pool == 2:
        return f"192.168.{random.randint(0,255)}.{random.randint(1,254)}"
    else:
        o1 = random.choice([45, 51, 88, 93, 104, 178, 185, 212, 217])
        return f"{o1}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"


# ─── vulnerability factories ──────────────────────────────────────────────────

def _make_vuln(exploit_id: str) -> Vulnerability:
    ed   = EXPLOIT_BY_ID[exploit_id]
    port = ed.std_port if random.random() < 0.5 else random.randint(1024, 65535)
    diff = random.choices(
        ["easy", "medium", "hard", "critical"],
        weights=[40, 35, 20, 5],
    )[0]
    return Vulnerability(
        id=exploit_id,
        name=ed.name,
        description=ed.description,
        port=port,
        difficulty=diff,
    )


def _pick_target_vulns(player_ids: List[str]) -> List[Vulnerability]:
    """Task target: random 1..N subset of what player can crack."""
    ids = player_ids or ["ssh_bruteforce"]
    n   = random.randint(1, len(ids))
    return [_make_vuln(eid) for eid in random.sample(ids, n)]


def _pick_sub_vulns(player_ids: List[str]) -> List[Vulnerability]:
    """Sub-node: 90% subset the player can crack, 10% adds one beyond."""
    ids = player_ids or ["ssh_bruteforce"]
    player_set = set(ids)
    extras = [eid for eid in ALL_EXPLOIT_IDS if eid not in player_set]
    n      = random.randint(1, len(ids))
    chosen = random.sample(ids, n)
    if extras and random.random() < 0.10:
        chosen.append(random.choice(extras))
    return [_make_vuln(eid) for eid in chosen]


def _pick_corp_vulns(player_ids: List[str]) -> List[Vulnerability]:
    """Corp server: always player_count + 1 extra (so always one step ahead)."""
    player_set = set(player_ids or ["ssh_bruteforce"])
    extras     = [eid for eid in ALL_EXPLOIT_IDS if eid not in player_set]
    if not extras:
        # Player owns every exploit — corp shows all
        return [_make_vuln(eid) for eid in ALL_EXPLOIT_IDS]
    corp_ids = list(player_ids or ["ssh_bruteforce"]) + [extras[0]]
    return [_make_vuln(eid) for eid in corp_ids]


# ─── position helper ─────────────────────────────────────────────────────────

def random_pos(
    existing: list, width: int, height: int,
    padding: int = 70, min_dist: int = 130,
) -> tuple:
    for _ in range(400):
        x = random.randint(padding, width - padding)
        y = random.randint(padding, height - padding)
        if all(math.hypot(x - px, y - py) >= min_dist for px, py in existing):
            return float(x), float(y)
    return (
        float(random.randint(padding, width - padding)),
        float(random.randint(padding, height - padding)),
    )


# ─── task network generator ──────────────────────────────────────────────────

_DEPTH_PROB   = [1.0, 0.75, 0.55, 0.35, 0.15]
_DEPTH_MAX_CH = [3,   2,    2,    2,    1   ]


def generate_task_network(
    area_w: int,
    area_h: int,
    existing_positions: list,
    player_exploits: Optional[List[str]] = None,
    used_names: Optional[set] = None,
):
    """
    Procedurally build a network around a task target.

    player_exploits: ordered list of exploit IDs the player has unlocked.
    used_names: mutable set of names already in use — updated in place.
    Returns (target_node, all_new_nodes, all_new_conns).
    """
    p_ids    = player_exploits or ["ssh_bruteforce"]
    used     = used_names if used_names is not None else set()
    pos_list = list(existing_positions)
    all_nodes: List[Node]       = []
    all_conns: List[Connection] = []

    def make_node(corp: Optional[str]) -> Node:
        x, y = random_pos(pos_list, area_w, area_h)
        pos_list.append((x, y))
        if corp:
            name  = _unique_corp_name(corp, used)
            vulns = _pick_corp_vulns(p_ids)
        else:
            name  = _unique_name(used)
            vulns = _pick_sub_vulns(p_ids)
        node = Node(
            name=name, ip=_random_ip(), x=x, y=y,
            discovered=False, ip_visible=True,
            corporation=corp, vulnerabilities=vulns,
        )
        all_nodes.append(node)
        return node

    def attach_children(parent: Node, depth: int):
        if depth >= len(_DEPTH_PROB):
            return
        if random.random() > _DEPTH_PROB[depth]:
            return
        for _ in range(random.randint(1, _DEPTH_MAX_CH[depth])):
            corp  = random.choice(_COMPANIES) if random.random() < _CORP_CHANCE else None
            child = make_node(corp)
            all_conns.append(Connection(parent.id, child.id))
            attach_children(child, depth + 1)

    # Task target: discovered but IP hidden
    tx, ty = random_pos(pos_list, area_w, area_h)
    pos_list.append((tx, ty))
    target_name = _unique_name(used)
    target = Node(
        name=target_name, ip=_random_ip(), x=tx, y=ty,
        discovered=True, ip_visible=False, is_task_target=True,
        vulnerabilities=_pick_target_vulns(p_ids),
    )
    all_nodes.append(target)
    attach_children(target, 0)

    return target, all_nodes, all_conns


# ─── initial network ─────────────────────────────────────────────────────────

def build_initial_network(area_w: int, area_h: int, used_names: Optional[set] = None):
    """Two-node starting network: home (left) + mail (right)."""
    if used_names is not None:
        used_names.update({"home", "mail"})

    hx = float(random.randint(80, area_w // 3))
    hy = float(random.randint(80, area_h - 80))
    mx = float(random.randint(area_w * 2 // 3, area_w - 120))
    my = float(random.randint(80, area_h - 80))

    home = Node(name="home", ip="192.168.0.100", x=hx, y=hy,
                is_player=True, node_type="player")
    mail = Node(name="mail", ip="192.168.0.1",   x=mx, y=my,
                node_type="mail")
    return [home, mail], [Connection(home.id, mail.id)]
