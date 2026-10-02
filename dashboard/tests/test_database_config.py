import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from stocklens import db
from stocklens.config import configured_path
from stocklens.runtime_config import ConfigurationError


class DatabaseConfigurationTests(unittest.TestCase):
    def test_interpreter_path_keeps_virtual_environment_symlink(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            root = Path(directory)
            target = root / 'system-python'
            target.touch()
            interpreter = root / 'venv-python'
            interpreter.symlink_to(target)
            os.environ['STOCKLENS_STRATEGY_PYTHON'] = str(interpreter)
            self.assertEqual(configured_path('STOCKLENS_STRATEGY_PYTHON', target), interpreter)

    def test_database_url_preserves_special_characters_and_hides_password(self):
        with patch('stocklens.db.require_database_config'), \
             patch.multiple(db, DB_HOST='db.example.invalid', DB_USER='demo@user',
                            DB_PASSWORD='test-only@#%:password', DB_NAME='demo-db', DB_PORT=3307):
            engine = db.get_engine()
        self.addCleanup(engine.dispose)
        self.assertEqual(engine.url.username, 'demo@user')
        self.assertEqual(engine.url.password, 'test-only@#%:password')
        self.assertNotIn('test-only', str(engine.url))

    def test_missing_config_rejected_before_creating_engine(self):
        with patch('stocklens.db.require_database_config', side_effect=ConfigurationError('DB_HOST')), \
             patch('stocklens.db.create_engine') as create:
            with self.assertRaises(ConfigurationError):
                db.get_engine()
        create.assert_not_called()
