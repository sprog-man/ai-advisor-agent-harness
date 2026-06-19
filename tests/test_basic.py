"""Basic tests for project structure."""
import pytest
from src import __version__


def test_version():
    """Test version is defined."""
    assert __version__ == "0.1.0"


def test_import_core():
    """Test core module imports."""
    from src.core import IntentParser, TaskDecomposer
    assert IntentParser is not None
    assert TaskDecomposer is not None


def test_import_memory():
    """Test memory module imports."""
    from src.memory import HotMemory, WarmMemory
    assert HotMemory is not None
    assert WarmMemory is not None


def test_import_reflection():
    """Test reflection module imports."""
    from src.reflection import ConflictDetector, SelfCorrection
    assert ConflictDetector is not None
    assert SelfCorrection is not None


def test_import_learning():
    """Test learning module imports."""
    from src.learning import BadCaseCatcher, CaseClassifier
    assert BadCaseCatcher is not None
    assert CaseClassifier is not None


def test_import_production():
    """Test production module imports."""
    from src.production import GrayTest, CircuitBreaker
    assert GrayTest is not None
    assert CircuitBreaker is not None


def test_import_utils():
    """Test utils module imports."""
    from src.utils import Config, Logger
    assert Config is not None
    assert Logger is not None