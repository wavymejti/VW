"""
Unit tests for tools.memory_logger.
"""

import unittest
from tools.memory_logger import MemoryLogger, get_memory_logger, attach_memory_handler_to_root
import logging


class TestMemoryLogger(unittest.TestCase):
    """
    Test suite for in-memory log collection and operations.
    """

    def setUp(self):
        self.logger = MemoryLogger(max_capacity=5)

    def test_log_creation_and_retrieval(self):
        self.logger.info("Test message 1", category="TEST")
        self.logger.warning("Test message 2", category="TEST")

        logs = self.logger.get_logs()
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0]["message"], "Test message 1")
        self.assertEqual(logs[0]["level"], "INFO")
        self.assertEqual(logs[1]["level"], "WARNING")

    def test_capacity_eviction(self):
        for i in range(10):
            self.logger.info(f"Message {i}")

        logs = self.logger.get_logs()
        self.assertEqual(len(logs), 5)
        self.assertEqual(logs[0]["message"], "Message 5")
        self.assertEqual(logs[-1]["message"], "Message 9")

    def test_filtering(self):
        self.logger.info("Info msg", category="CAT_A")
        self.logger.error("Error msg", category="CAT_B")

        info_logs = self.logger.get_logs(level="INFO")
        self.assertEqual(len(info_logs), 1)
        self.assertEqual(info_logs[0]["message"], "Info msg")

        cat_b_logs = self.logger.get_logs(category="CAT_B")
        self.assertEqual(len(cat_b_logs), 1)
        self.assertEqual(cat_b_logs[0]["message"], "Error msg")

    def test_search_and_stats(self):
        self.logger.info("Alpha search item", category="CAT_A")
        self.logger.error("Beta search item", category="CAT_B")

        results = self.logger.search_logs("Alpha")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["category"], "CAT_A")

        stats = self.logger.get_stats()
        self.assertEqual(stats["total_logs"], 2)
        self.assertEqual(stats["by_level"]["INFO"], 1)
        self.assertEqual(stats["by_level"]["ERROR"], 1)


if __name__ == "__main__":
    unittest.main()
