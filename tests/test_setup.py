#!/usr/bin/python3
"""Subprocess tests for setup.sh, with a fake HOME. No network, ever.

Replicates the konnectarchy test_setup.py pattern: uninstall only removes
files this plugin owns (marked symlink target, marked credentials file),
and leaves foreign files alone.
"""

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "setup.sh"
PLUGIN_ID = "io.github.astorrer.omarchy-coros"


def run_setup(home: Path, *args: str, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": str(home), "OMARCHY_COROS_SETUP_SKIP_LOGIN_TEST": "1"}
    env.pop("XDG_CONFIG_HOME", None)
    env.pop("XDG_CACHE_HOME", None)
    env.pop("COROS_REGION", None)
    env.pop("COROS_EMAIL", None)
    env.pop("COROS_PASSWORD", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [str(SETUP), *args],
        env=env,
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )


class SetupUninstallTest(unittest.TestCase):
    def _owned_tree(self, home: Path) -> tuple[Path, Path, Path]:
        link = home / ".config" / "omarchy" / "plugins" / PLUGIN_ID
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(ROOT)
        cache = home / ".cache" / "omarchy-coros"
        cache.mkdir(parents=True, exist_ok=True)
        creds = home / ".config" / "omarchy-coros" / "credentials"
        creds.parent.mkdir(parents=True, exist_ok=True)
        creds.write_text(
            "# Written by omarchy-coros\nCOROS_EMAIL=a@b.c\n",
            encoding="utf-8",
        )
        return link, cache, creds

    def test_uninstall_removes_owned_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            link, cache, creds = self._owned_tree(home)
            result = run_setup(home, "uninstall")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(link.exists() or link.is_symlink())
            self.assertFalse(cache.exists())
            self.assertFalse(creds.exists())
            self.assertIn("Removed", result.stdout)

    def test_uninstall_leaves_foreign_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            link = home / ".config" / "omarchy" / "plugins" / PLUGIN_ID
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(Path(tmp) / "somewhere-else")
            creds = home / ".config" / "omarchy-coros" / "credentials"
            creds.parent.mkdir(parents=True, exist_ok=True)
            creds.write_text("COROS_EMAIL=a@b.c\n", encoding="utf-8")
            result = run_setup(home, "uninstall")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(link.is_symlink())
            self.assertTrue(creds.exists())
            self.assertIn("left alone", result.stdout)

    def test_uninstall_honors_xdg_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            home = base / "home"
            xdg_config = base / "config"
            xdg_cache = base / "cache"
            home.mkdir()
            link = home / ".config" / "omarchy" / "plugins" / PLUGIN_ID
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(ROOT)
            cache = xdg_cache / "omarchy-coros"
            cache.mkdir(parents=True, exist_ok=True)
            (cache / "token.json").write_text("{}", encoding="utf-8")
            creds = xdg_config / "omarchy-coros" / "credentials"
            creds.parent.mkdir(parents=True, exist_ok=True)
            creds.write_text(
                "# Written by omarchy-coros\nCOROS_EMAIL=a@b.c\n",
                encoding="utf-8",
            )
            home_cache = home / ".cache" / "omarchy-coros"
            home_cache.mkdir(parents=True, exist_ok=True)
            home_creds = home / ".config" / "omarchy-coros" / "credentials"
            home_creds.parent.mkdir(parents=True, exist_ok=True)
            home_creds.write_text(
                "# Written by omarchy-coros\nCOROS_EMAIL=home@b.c\n",
                encoding="utf-8",
            )
            result = run_setup(
                home,
                "uninstall",
                extra_env={
                    "XDG_CONFIG_HOME": str(xdg_config),
                    "XDG_CACHE_HOME": str(xdg_cache),
                },
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(link.exists() or link.is_symlink())
            self.assertFalse(cache.exists())
            self.assertFalse(creds.exists())
            self.assertTrue(home_cache.exists())
            self.assertTrue(home_creds.exists())

    def test_uninstall_cache_symlink_target_survives(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            target = home / ".cache" / "omarchy-coros-target"
            target.mkdir(parents=True)
            (target / "token.json").write_text("sentinel", encoding="utf-8")
            cache = home / ".cache" / "omarchy-coros"
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.symlink_to(target)
            result = run_setup(home, "uninstall")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(cache.is_symlink())
            self.assertTrue(target.is_dir())
            self.assertEqual((target / "token.json").read_text(encoding="utf-8"), "sentinel")

    def test_uninstall_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._owned_tree(home)
            first = run_setup(home, "uninstall")
            self.assertEqual(first.returncode, 0, first.stderr)
            second = run_setup(home, "uninstall")
            self.assertEqual(second.returncode, 0, second.stderr)
            for msg in ("No omarchy-coros dev symlink found", "No omarchy-coros cache found",
                        "No omarchy-coros credentials file found"):
                self.assertIn(msg, second.stdout)

    def test_uninstall_ignores_extra_args(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._owned_tree(home)
            result = run_setup(home, "uninstall", "extra")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((home / ".config" / "omarchy" / "plugins" / PLUGIN_ID).exists())


class SetupInstallTest(unittest.TestCase):
    def test_install_writes_marked_creds_and_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            result = run_setup(
                home,
                extra_env={
                    "COROS_EMAIL": "user@example.com",
                    "COROS_PASSWORD": "secret",
                    "COROS_REGION": "us",
                },
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            link = home / ".config" / "omarchy" / "plugins" / PLUGIN_ID
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), ROOT.resolve())
            creds = home / ".config" / "omarchy-coros" / "credentials"
            text = creds.read_text(encoding="utf-8")
            self.assertIn("# Written by omarchy-coros", text)
            self.assertIn("COROS_EMAIL=user@example.com", text)
            self.assertIn("COROS_REGION=us", text)
            self.assertNotIn("secret", result.stdout + result.stderr)
            self.assertEqual(stat.S_IMODE(creds.stat().st_mode), 0o600)

    def test_install_refuses_credentials_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            creds = home / ".config" / "omarchy-coros" / "credentials"
            creds.parent.mkdir(parents=True, exist_ok=True)
            victim = home / ".config" / "omarchy-coros" / "victim"
            victim.write_text("sentinel", encoding="utf-8")
            creds.symlink_to(victim)
            result = run_setup(
                home,
                extra_env={
                    "COROS_EMAIL": "user@example.com",
                    "COROS_PASSWORD": "secret",
                    "COROS_REGION": "us",
                },
            )
            self.assertEqual(result.returncode, 1)
            self.assertTrue(creds.is_symlink())
            self.assertEqual(victim.read_text(encoding="utf-8"), "sentinel")
            self.assertIn("symlink", result.stderr)

    def test_install_without_env_creds_links_anyway(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            result = run_setup(home)
            self.assertEqual(result.returncode, 0, result.stderr)
            link = home / ".config" / "omarchy" / "plugins" / PLUGIN_ID
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), ROOT.resolve())
            creds = home / ".config" / "omarchy-coros" / "credentials"
            self.assertFalse(creds.exists())
            self.assertIn("ready", result.stdout)

    def test_install_partial_env_creds_skips_creds(self):
        for extra_env in ({"COROS_EMAIL": "user@example.com"},
                          {"COROS_PASSWORD": "secret"}):
            with self.subTest(extra_env=extra_env):
                with tempfile.TemporaryDirectory() as tmp:
                    home = Path(tmp)
                    result = run_setup(home, extra_env=extra_env)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    link = home / ".config" / "omarchy" / "plugins" / PLUGIN_ID
                    self.assertTrue(link.is_symlink())
                    creds = home / ".config" / "omarchy-coros" / "credentials"
                    self.assertFalse(creds.exists())

    def test_install_refuses_invalid_region(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            result = run_setup(
                home,
                extra_env={
                    "COROS_EMAIL": "user@example.com",
                    "COROS_PASSWORD": "secret",
                    "COROS_REGION": "apac",
                },
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("Region must be eu or us.", result.stderr)
            creds = home / ".config" / "omarchy-coros" / "credentials"
            self.assertFalse(creds.exists())

    def test_install_default_region_is_eu_with_0700_conf_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            result = run_setup(
                home,
                extra_env={
                    "COROS_EMAIL": "user@example.com",
                    "COROS_PASSWORD": "secret",
                },
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            creds = home / ".config" / "omarchy-coros" / "credentials"
            self.assertIn("COROS_REGION=eu", creds.read_text(encoding="utf-8"))
            conf_dir = home / ".config" / "omarchy-coros"
            self.assertEqual(stat.S_IMODE(conf_dir.stat().st_mode), 0o700)

    def test_install_region_is_case_insensitive(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            result = run_setup(
                home,
                extra_env={
                    "COROS_EMAIL": "user@example.com",
                    "COROS_PASSWORD": "secret",
                    "COROS_REGION": "US",
                },
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            creds = home / ".config" / "omarchy-coros" / "credentials"
            self.assertIn("COROS_REGION=us", creds.read_text(encoding="utf-8"))

    def test_install_idempotent_already_linked(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self.assertEqual(run_setup(home).returncode, 0)
            second = run_setup(home)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("already correct", second.stdout)
            link = home / ".config" / "omarchy" / "plugins" / PLUGIN_ID
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), ROOT.resolve())

    def test_install_refuses_foreign_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            link = home / ".config" / "omarchy" / "plugins" / PLUGIN_ID
            link.parent.mkdir(parents=True)
            link.symlink_to(Path(tmp) / "elsewhere")
            result = run_setup(home, "setup")
            self.assertEqual(result.returncode, 1)
            self.assertIn("points elsewhere", result.stderr)
            self.assertEqual(link.readlink(), Path(tmp) / "elsewhere")

    def test_install_treats_unknown_args_as_setup(self):
        for arg in ("--help", "setup", "update", "--uninstall"):
            with self.subTest(arg=arg):
                with tempfile.TemporaryDirectory() as tmp:
                    home = Path(tmp)
                    result = run_setup(home, arg)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    link = home / ".config" / "omarchy" / "plugins" / PLUGIN_ID
                    self.assertTrue(link.is_symlink(), repr(arg))

    def test_install_without_python3_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            result = run_setup(home, extra_env={"PATH": str(Path(tmp) / "bin")})
            self.assertEqual(result.returncode, 1)
            self.assertIn("python3 not found", result.stderr)
            self.assertFalse((home / ".config" / "omarchy").exists())


if __name__ == "__main__":
    unittest.main()
