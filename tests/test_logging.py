import logging
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.core.logging import get_logger


class LoggingTests(unittest.TestCase):
    def _reset_logger(self):
        logger = logging.getLogger("md-sync")
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)

    def setUp(self):
        self._reset_logger()

    def tearDown(self):
        self._reset_logger()

    def test_log_directory_can_be_moved_to_runtime_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(os.environ, {"SMMD_LOG_DIR": temporary}):
                logger = get_logger()
                logger.info("container-safe")
                for handler in list(logger.handlers):
                    handler.flush()
                    handler.close()
                    logger.removeHandler(handler)

            logs = list(Path(temporary).glob("md-sync.*.log"))
            self.assertEqual(len(logs), 1)
            self.assertIn("container-safe", logs[0].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
