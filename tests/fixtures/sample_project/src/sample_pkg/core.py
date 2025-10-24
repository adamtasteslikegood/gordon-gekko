"""Core module with a couple of symbols."""

from sample_pkg import utils


class ImportantService:
    """Implements the main flow."""

    def __init__(self, multiplier: int = 1) -> None:
        self.multiplier = multiplier

    def compute(self, value: int) -> int:
        """Apply some transformation."""
        return utils.helper(value * self.multiplier)


def helper(value: int) -> int:
    # TODO: handle overflow
    return value + 1
