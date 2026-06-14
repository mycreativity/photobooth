"""Unit tests for booth agent system metrics (per-core CPU)."""

from unittest.mock import mock_open, patch

from photobooth.services.agent import BoothAgent


def _agent() -> BoothAgent:
    # __init__ only stores config — no network/threads until start().
    return BoothAgent({"booth_id": "test", "server": {"enabled": False}})


class TestPerCoreCpu:
    """Cover the /proc/stat delta-based per-core CPU calculation."""

    def test_first_sample_returns_empty(self):
        """No previous snapshot yet → nothing to diff against."""
        agent = _agent()
        snap = "cpu  0 0 0 0 0\ncpu0 50 0 50 100 0\ncpu1 10 0 10 80 0\n"
        with patch("builtins.open", mock_open(read_data=snap)):
            assert agent._get_cpu_cores() == []

    def test_second_sample_computes_per_core_usage(self):
        """Busy fraction over the interval, per core, in order."""
        agent = _agent()
        snap1 = "cpu  0 0 0 0 0\ncpu0 50 0 50 100 0\ncpu1 10 0 10 80 0\n"
        # core0: idle_delta=100, total_delta=200 -> 50%
        # core1: idle_delta=300, total_delta=400 -> 25%
        snap2 = "cpu  0 0 0 0 0\ncpu0 100 0 100 200 0\ncpu1 60 0 60 380 0\n"
        with patch("builtins.open", mock_open(read_data=snap1)):
            agent._get_cpu_cores()  # primes the previous snapshot
        with patch("builtins.open", mock_open(read_data=snap2)):
            assert agent._get_cpu_cores() == [50, 25]

    def test_idle_interval_reports_zero(self):
        """No change between samples → 0% busy, not a divide-by-zero."""
        agent = _agent()
        snap = "cpu0 50 0 50 100 0\n"
        with patch("builtins.open", mock_open(read_data=snap)):
            agent._get_cpu_cores()
        with patch("builtins.open", mock_open(read_data=snap)):
            assert agent._get_cpu_cores() == [0]

    def test_aggregate_cpu_line_is_ignored(self):
        """The summary 'cpu ' line must not be counted as a core."""
        agent = _agent()
        snap1 = "cpu  999 0 999 999 0\ncpu0 50 0 50 100 0\n"
        snap2 = "cpu  999 0 999 999 0\ncpu0 100 0 100 200 0\n"
        with patch("builtins.open", mock_open(read_data=snap1)):
            agent._get_cpu_cores()
        with patch("builtins.open", mock_open(read_data=snap2)):
            assert agent._get_cpu_cores() == [50]  # exactly one core

    def test_unavailable_proc_stat_returns_empty(self):
        """Non-Linux / unreadable /proc/stat must not raise."""
        agent = _agent()
        with patch("builtins.open", side_effect=OSError):
            assert agent._get_cpu_cores() == []
