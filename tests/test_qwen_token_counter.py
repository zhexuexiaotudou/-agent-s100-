import unittest

from tools.token_budget.qwen_token_counter import QwenTokenCounter


class QwenTokenCounterTest(unittest.TestCase):
    def test_counts_basic_text_shapes(self):
        counter = QwenTokenCounter()
        self.assertGreater(counter.count_text_tokens("hello world"), 0)
        self.assertGreater(counter.count_text_tokens("你好，搜索 NAS 文档"), 0)
        self.assertGreater(counter.count_text_tokens("/mnt/nas/openclaw/Public/report.md"), 0)

    def test_counts_payload_and_messages(self):
        counter = QwenTokenCounter()
        payload_tokens = counter.count_payload_tokens({"query": "S100P OpenClaw", "top_k": 3})
        message_tokens = counter.count_messages_tokens([{"role": "user", "content": "search NAS docs"}])
        self.assertGreater(payload_tokens, 0)
        self.assertGreater(message_tokens, 0)

    def test_identity_is_recorded(self):
        counter = QwenTokenCounter()
        self.assertIn("backend", counter.identity)
        self.assertIn("tokenizer_identity_hash", counter.identity)


if __name__ == "__main__":
    unittest.main()

