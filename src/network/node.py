from dataclasses import dataclass, field
from typing import List, Optional
import uuid


@dataclass
class Node:
    name: str = "unknown"
    ip: str = "0.0.0.0"
    x: float = 0.0
    y: float = 0.0
    is_player: bool = False
    is_hacked: bool = False
    is_task_target: bool = False
    discovered: bool = True    # visible on the node map
    ip_visible: bool = True    # show real IP in label; False = shows "???"
    node_type: str = "server"  # player | mail | server | firewall | database | router
    corporation: Optional[str] = None  # Arasaka | Militech | Kang Tao | Biotechnica | Zetatech
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    vulnerabilities: List = field(default_factory=list)  # List[Vulnerability]
