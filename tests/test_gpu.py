"""Tests for GPU memory housekeeping (torch.cuda mocked)."""
from unittest.mock import MagicMock

from app.core.gpu import release_cached_memory


def test_release_empties_cache_when_cuda_is_available(monkeypatch):
    import torch

    empty = MagicMock()
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "empty_cache", empty)

    release_cached_memory()

    empty.assert_called_once()


def test_release_is_a_no_op_without_cuda(monkeypatch):
    import torch

    empty = MagicMock()
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(torch.cuda, "empty_cache", empty)

    release_cached_memory()

    empty.assert_not_called()
