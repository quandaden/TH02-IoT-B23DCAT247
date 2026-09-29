from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SequenceObservation:
    status: str
    gap_count: int = 0
    should_store: bool = True


@dataclass
class _DeviceState:
    sequence: int
    uptime_s: int


class SequenceTracker:
    """Tracks duplicates, missing sequences and device restarts in memory."""

    def __init__(self) -> None:
        self._states: dict[str, _DeviceState] = {}

    def observe(
        self, device_id: str, sequence: int, uptime_s: int
    ) -> SequenceObservation:
        previous = self._states.get(device_id)
        if previous is None:
            self._states[device_id] = _DeviceState(sequence, uptime_s)
            return SequenceObservation("first")

        if sequence == previous.sequence and uptime_s == previous.uptime_s:
            return SequenceObservation("duplicate", should_store=False)

        restarted = uptime_s < previous.uptime_s or (
            sequence < previous.sequence and uptime_s <= 30
        )
        if restarted:
            self._states[device_id] = _DeviceState(sequence, uptime_s)
            return SequenceObservation("restart")

        if sequence < previous.sequence:
            return SequenceObservation("out_of_order", should_store=False)

        gap_count = max(0, sequence - previous.sequence - 1)
        self._states[device_id] = _DeviceState(sequence, uptime_s)
        if gap_count:
            return SequenceObservation("gap", gap_count=gap_count)
        return SequenceObservation("normal")

