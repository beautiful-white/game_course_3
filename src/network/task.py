from dataclasses import dataclass
from src.network.node import Node


@dataclass
class Task:
    target_node: Node
    reward: float
    completed: bool = False
