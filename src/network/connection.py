from dataclasses import dataclass


@dataclass
class Connection:
    source_id: str
    target_id: str
