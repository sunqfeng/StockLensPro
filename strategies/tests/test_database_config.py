import os
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mysql_data_engine import MySqlDataEngine
from runtime_config import ConfigurationError


class DatabaseConfigurationTests(unittest.TestCase):
    def test_interpreter_path_keeps_virtual_environment_symlink(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            root = Path(directory)
            target = root / 'system-python'
            target.touch()
            interpreter = root / 'venv-python'
            interpreter.symlink_to(target)
            os.environ['STOCKLENS_TECH_SCORE_PYTHON'] = str(interpreter)
            config = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'config.py'))
            self.assertEqual(config['configured_path']('STOCKLENS_TECH_SCORE_PYTHON', target), interpreter)

    def make_config(self):
        env = dict(DB_HOST='db.example.invalid', DB_PORT='3307', DB_USER='demo@user',
                   DB_PASSWORD='test-only@#%:password', DB_NAME='demo-db')
        with patch.dict(os.environ, env, clear=True):
            return runpy.run_path(str(Path(__file__).resolve().parents[1] / 'config.py'))['MYSQL_CONFIG']

    def test_config_representation_does_not_expose_connection_values(self):
        config = self.make_config()
        for value in (config.host, config.user, config.password, config.database):
            self.assertNotIn(value, repr(config))

    def test_database_url_preserves_special_characters_and_hides_password(self):
        config = self.make_config()
        engine = MySqlDataEngine(config)
        self.addCleanup(engine.engine.dispose)
        self.assertEqual(engine.engine.url.username, config.user)
        self.assertEqual(engine.engine.url.password, config.password)
        self.assertNotIn(config.password, str(engine.engine.url))

    def test_missing_config_rejected_before_creating_engine(self):
        config = self.make_config()
        config.host = ''
        with patch('mysql_data_engine.create_engine') as create:
            with self.assertRaises(ConfigurationError):
                MySqlDataEngine(config)
        create.assert_not_called()
