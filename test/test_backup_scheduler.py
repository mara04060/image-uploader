import tempfile
import unittest
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import backup_scheduler


class BackupSchedulerUnitTests(unittest.TestCase):
    def test_successful_backup_uses_pg_dump_without_real_database(self):
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(backup_scheduler, "BACKUP_DIR", Path(directory)),
                patch.dict(
                    os.environ,
                    {
                        "POSTGRES_PASSWORD": "test-password",
                        "BACKUP_INTERVAL_MINUTES": "5",
                        "BACKUP_DIR": directory,
                    },
                    clear=True,
                ),
                patch.object(
                    backup_scheduler.subprocess,
                    "run",
                    return_value=SimpleNamespace(returncode=0, stderr=""),
                ) as run,
            ):
                result = backup_scheduler.create_backup()

            self.assertTrue(result)
            command = run.call_args.args[0]
            self.assertEqual(command[0], "pg_dump")
            self.assertIn("-d", command)
            self.assertIn("images_db", command)

    def test_failed_backup_removes_partial_file(self):
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(backup_scheduler, "BACKUP_DIR", Path(directory)),
                patch.dict(
                    os.environ,
                    {
                        "POSTGRES_PASSWORD": "test-password",
                        "BACKUP_INTERVAL_MINUTES": "5",
                        "BACKUP_DIR": directory,
                    },
                    clear=True,
                ),
                patch.object(
                    backup_scheduler.subprocess,
                    "run",
                    return_value=SimpleNamespace(
                        returncode=1, stderr="pg_dump failed"
                    ),
                ),
            ):
                result = backup_scheduler.create_backup()

            self.assertFalse(result)
            self.assertEqual(list(Path(directory).glob("*.sql")), [])

    def test_backup_config_rejects_invalid_interval(self):
        @backup_scheduler.validate_backup_config
        def get_interval():
            return backup_scheduler.BACKUP_INTERVAL_MINUTES

        for value in ("0", "-1", "abc"):
            with (
                patch.dict(
                    os.environ,
                    {
                        "POSTGRES_PASSWORD": "test-password",
                        "BACKUP_INTERVAL_MINUTES": value,
                    },
                    clear=True,
                ),
                self.assertRaises(backup_scheduler.ConfigurationError),
            ):
                get_interval()

    def test_backup_config_rejects_invalid_postgres_port(self):
        @backup_scheduler.validate_backup_config
        def get_port():
            return backup_scheduler.POSTGRES_PORT

        for value in ("0", "65536", "abc"):
            with (
                patch.dict(
                    os.environ,
                    {
                        "POSTGRES_PASSWORD": "test-password",
                        "POSTGRES_PORT": value,
                    },
                    clear=True,
                ),
                self.assertRaises(backup_scheduler.ConfigurationError),
            ):
                get_port()


if __name__ == "__main__":
    unittest.main()
