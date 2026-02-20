"""Pytest fixtures for SparkAgent tests."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_file(temp_dir):
    """Create a sample file for testing."""
    file_path = temp_dir / "sample.txt"
    file_path.write_text("Hello, World!\nLine 2\nLine 3")
    return file_path


@pytest.fixture
def sample_dir(temp_dir):
    """Create a sample directory structure for testing."""
    (temp_dir / "subdir").mkdir()
    (temp_dir / "file1.txt").write_text("content1")
    (temp_dir / "file2.py").write_text("content2")
    (temp_dir / "subdir" / "nested.txt").write_text("nested content")
    return temp_dir
