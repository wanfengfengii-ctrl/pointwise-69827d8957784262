from dataclasses import dataclass


@dataclass(frozen=True)
class RecordingLayout:
    positions: tuple[str, ...]

    def __post_init__(self):
        if not self.positions or any(not isinstance(item, str) or not item.strip() for item in self.positions):
            raise ValueError('layout positions must be non-empty strings')
        if len(set(self.positions)) != len(self.positions):
            raise ValueError('layout positions must be unique')

    def contains(self, position: str) -> bool:
        return position in self.positions

    def order_key(self, position: str) -> int:
        if position not in self.positions:
            raise KeyError(position)
        return self.positions.index(position)
