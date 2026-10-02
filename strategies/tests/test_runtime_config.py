import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime_config import ConfigurationError, database_port, load_config, validate_database


class RuntimeConfigurationTests(unittest.TestCase):
    def test_local_file_loaded_without_overwriting_environment(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'DB_USER': 'environment-user'}, clear=True):
            root = Path(directory)
            (root / 'config').mkdir()
            (root / 'config/secrets.env').write_text("DB_USER=file-user\nDB_PASSWORD='literal-${DB_USER}-password'\n", encoding='utf-8')
            load_config(root)
            self.assertEqual(os.environ['DB_USER'], 'environment-user')
            self.assertEqual(os.environ['DB_PASSWORD'], 'literal-${DB_USER}-password')

    def test_explicit_file_is_the_only_source(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            root = Path(directory)
            (root / 'config').mkdir()
            (root / 'config/secrets.env').write_text('DB_USER=wrong-user\n', encoding='utf-8')
            external = root / 'shared.env'
            external.write_text('DB_USER=shared-user\n', encoding='utf-8')
            os.environ['STOCKLENS_CONFIG_FILE'] = str(external)
            self.assertEqual(load_config(root), external.resolve())
            self.assertEqual(os.environ['DB_USER'], 'shared-user')

    def test_explicit_missing_file_fails_without_disclosing_path(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            os.environ['STOCKLENS_CONFIG_FILE'] = str(Path(directory) / 'private-name.env')
            with self.assertRaises(ConfigurationError) as error:
                load_config(Path(directory))
            self.assertIn('STOCKLENS_CONFIG_FILE', str(error.exception))
            self.assertNotIn(directory, str(error.exception))

    def test_no_local_file_is_allowed_for_environment_only_deployment(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            load_config(Path(directory))
            self.assertNotIn('DB_PASSWORD', os.environ)

    def test_missing_database_fields_fail_without_disclosing_values(self):
        with self.assertRaises(ConfigurationError) as error:
            validate_database('', 3306, 'fictional-user', 'fictional-secret', '')
        self.assertIn('DB_HOST', str(error.exception))
        self.assertIn('DB_NAME', str(error.exception))
        self.assertNotIn('fictional', str(error.exception))

    def test_port_validation_does_not_echo_input(self):
        for value in ('private-invalid-value', '0', '65536', ''):
            with self.subTest(value=value), self.assertRaises(ConfigurationError) as error:
                database_port(value)
            self.assertIn('DB_PORT', str(error.exception))
            if value == 'private-invalid-value':
                self.assertNotIn(value, str(error.exception))

    def test_valid_database_settings_and_default_port(self):
        self.assertEqual(database_port(None), 3306)
        self.assertEqual(database_port('3307'), 3307)
        validate_database('db.example.invalid', 3307, 'demo-user', 'test-only-password', 'demo-db')
