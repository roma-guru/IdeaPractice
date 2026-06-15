"""
Shared pytest fixtures for journal tests.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_analyse_recording():
    """Prevent analyse_recording from trying to connect to Redis in every test.

    Tests that specifically verify task dispatch (test_tasks.py) patch
    the function themselves inside the test body, which takes precedence.
    """
    with patch("journal.views.analyse_recording"):
        yield
