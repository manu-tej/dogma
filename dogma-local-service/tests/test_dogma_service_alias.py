from __future__ import annotations

import unittest

import dogma_service


class DogmaServiceAliasTests(unittest.TestCase):
    def test_public_package_exports_version(self) -> None:
        self.assertRegex(dogma_service.__version__, r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
