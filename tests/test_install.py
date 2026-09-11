#!/usr/bin/python3
"""Dev-install check: the plugin is symlinked into the Omarchy plugins dir.

Mirrors the konnectarchy dev loop:
  ln -s <repo> ~/.config/omarchy/plugins/io.github.astorrer.omarchy-coros
Skips when the Omarchy plugins dir does not exist (e.g. CI).
"""

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ID = "io.github.astorrer.omarchy-coros"


class InstallTest(unittest.TestCase):
    def test_dev_symlink(self):
        plugins = Path.home() / ".config" / "omarchy" / "plugins"
        if not plugins.is_dir():
            self.skipTest("no Omarchy plugins dir (not an Omarchy host)")
        link = plugins / PLUGIN_ID
        self.assertTrue(link.is_symlink(), f"{link} should be a symlink to the repo")
        self.assertEqual(link.resolve(), ROOT.resolve())


if __name__ == "__main__":
    if os.environ.get("OMARCHY_COROS_SKIP_INSTALL_TEST") == "1":
        print("skip install (OMARCHY_COROS_SKIP_INSTALL_TEST=1)")
        sys.exit(0)
    unittest.main()
