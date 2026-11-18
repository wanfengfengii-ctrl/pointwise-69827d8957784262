from dataclasses import dataclass

from recording.layout import RecordingLayout


@dataclass(frozen=True)
class SlotMap:
    positions: tuple[str, ...]

    def resolve(self, slot: int) -> str:
        if isinstance(slot, bool) or not isinstance(slot, int) or slot < 0 or slot >= len(self.positions):
            raise ValueError('slot is outside the stripe mapping')
        return self.positions[slot]


def build_slot_map(layout: RecordingLayout, mapped_positions) -> SlotMap:
    if isinstance(mapped_positions, (str, bytes)) or not mapped_positions:
        raise ValueError('stripe mapping is required')
    positions = tuple(mapped_positions)
    if len(set(positions)) != len(positions):
        raise ValueError('stripe mapping cannot repeat a recording position')
    if any(not layout.contains(position) for position in positions):
        raise ValueError('stripe mapping contains an unknown recording position')
    return SlotMap(positions)
