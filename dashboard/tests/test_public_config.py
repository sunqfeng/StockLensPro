import os
import runpy
import unittest
from pathlib import Path
from unittest.mock import patch


class PublicConfigurationTests(unittest.TestCase):
    def test_database_settings_come_from_environment_not_source(self):
        env = dict(DB_HOST='db.example.invalid', DB_PORT='3307', DB_USER='demo_user',
                   DB_PASSWORD='test-only-password', DB_NAME='demo_database')
        with patch.dict(os.environ, env, clear=True):
            config = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'stocklens/config.py'))
        for key, value in env.items():
            self.assertEqual(config[key], int(value) if key == 'DB_PORT' else value)


if __name__ == '__main__':
    unittest.main()
