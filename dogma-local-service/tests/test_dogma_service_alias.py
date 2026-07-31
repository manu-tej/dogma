"""The public package name and the implementation are the same thing again.

This file used to assert that a `dogma_service` shim re-exported `__version__`
from the real package, `biocursor_service`. That shim was the whole of the
public name: every import, test, traceback and error message said
`biocursor_service`, so the documented name and the one anybody actually
encountered had drifted apart, and the alias made the drift look intentional.

`dogma_service` is now the package. The assertions below keep what was worth
keeping — that the name resolves and carries a version — and add one that the
retired name is genuinely gone rather than merely shadowed.
"""

from __future__ import annotations

import importlib.util
import unittest

import dogma_service


class DogmaServicePackageTests(unittest.TestCase):
    def test_the_public_package_exports_a_version(self) -> None:
        self.assertRegex(dogma_service.__version__, r"^\d+\.\d+\.\d+$")

    def test_the_public_package_is_the_implementation(self) -> None:
        """Not a shim: the modules the CLI and MCP server live in are here."""
        from dogma_service import cli, mcp_server

        self.assertTrue(callable(cli.main))
        self.assertEqual(len(mcp_server.tool_names()), 9)

    def test_the_retired_name_is_gone(self) -> None:
        """A leftover `biocursor_service` on the path would let imports keep
        working while the rename looked complete — the same both-copies-present
        failure the skill move hit earlier in this branch."""
        self.assertIsNone(
            importlib.util.find_spec("biocursor_service"),
            "biocursor_service is still importable; the rename is incomplete",
        )


if __name__ == "__main__":
    unittest.main()
