import unittest

from stocklens.tasks import APP_DIR, get_task_command, get_all_task_definitions


class HotStockTaskDefinitionTests(unittest.TestCase):
    def test_hot_stock_collection_is_available_as_builtin_task(self):
        task = get_all_task_definitions()["collect_xueqiu_hot_stocks"]

        self.assertEqual(task.category, "市场热度")
        self.assertEqual(task.cwd, APP_DIR)
        self.assertEqual(
            get_task_command("collect_xueqiu_hot_stocks"),
            list(task.base_command),
        )
        self.assertEqual(task.base_command[-1], "scripts/collect_xueqiu_hot_stocks.py")


if __name__ == "__main__":
    unittest.main()
