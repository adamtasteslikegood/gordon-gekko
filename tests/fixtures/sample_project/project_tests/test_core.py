"""Tests for the sample package."""

from sample_pkg.core import ImportantService


def test_compute_increments():
    service = ImportantService(multiplier=2)
    assert service.compute(3) == 7
