"""Basic tests that do not require Django."""
import os
import unittest
import toml
from nautobot_change_producer import NautobotChangeProducerConfig


class TestPackageVersion(unittest.TestCase):
    """Test Version in doc requirements is the same pyproject."""

    def test_version(self):
        """Verify that pyproject.toml dev dependencies have the same versions as in the docs requirements.txt."""
        parent_path = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        )
        poetry_path = os.path.join(parent_path, "pyproject.toml")
        poetry_version = toml.load(poetry_path)["tool"]["poetry"]["version"]
        self.assertEqual(poetry_version, NautobotChangeProducerConfig.version)
