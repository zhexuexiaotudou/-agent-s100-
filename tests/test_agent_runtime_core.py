import json
import tempfile
import unittest
from pathlib import Path

from src.agent_runtime.context_pack import ContextPackCompiler, sample_context_candidates
from src.agent_runtime.memory_manager import AgentMemoryManager, seed_memory
from src.agent_runtime.multimodal_index import MultimodalIndex, seed_multimodal_fixture
from src.agent_runtime.rag_pipeline import AgentRuntimeRag, seed_rag_fixture
from src.agent_runtime.tool_manifest import load_manifest, validate_internal_manifest


REPO_ROOT = Path(__file__).resolve().parents[1]


class AgentRuntimeCoreTest(unittest.TestCase):
    def test_context_pack_redacts_private_paths_and_excludes_acl_denied(self):
        pack = ContextPackCompiler().compile(
            query="Explain /mnt/nas/openclaw/Personal/private/source.txt",
            workspace="openclaw",
            user_id="admin",
            candidates=sample_context_candidates(1),
        )
        serial = json.dumps(pack, ensure_ascii=False)
        self.assertTrue(pack["ok"])
        self.assertEqual(pack["acl_denied_count"], 1)
        self.assertIn("<PRIVATE_HASH:", serial)
        self.assertNotIn("/mnt/nas/openclaw/Personal/private", serial)
        self.assertFalse(pack["qwen_execution_authority"])

    def test_memory_manager_seed_uses_redacted_local_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = AgentMemoryManager(Path(tmp) / "memory.sqlite3")
            stats = seed_memory(manager, event_count=50)
            self.assertGreaterEqual(stats["events"], 50)
            self.assertGreaterEqual(stats["facts"], 10)
            self.assertEqual(stats["raw_content_rows"], 0)
            self.assertEqual(stats["private_leak_count"], 0)

    def test_multimodal_index_metadata_only_counts_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = seed_multimodal_fixture(Path(tmp) / "Personal")
            payload = MultimodalIndex(Path(tmp) / "mm.sqlite3").scan(root)
            self.assertTrue(payload["ok"])
            self.assertGreaterEqual(payload["counts"]["document"], 10)
            self.assertGreaterEqual(payload["counts"]["image"], 10)
            self.assertGreaterEqual(payload["counts"]["video"], 3)
            self.assertGreaterEqual(payload["counts"]["audio"], 3)
            self.assertFalse(payload["raw_path_exported"])

    def test_rag_pipeline_cites_evidence_and_refuses_without_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = seed_rag_fixture(Path(tmp) / "Documents", count=12)
            rag = AgentRuntimeRag(Path(tmp) / "rag.sqlite3")
            sync = rag.sync_documents(root)
            self.assertGreaterEqual(sync["indexed_documents"], 12)
            answer = rag.answer("harness OpenClaw evidence refs")
            self.assertGreaterEqual(answer["evidence_count"], 1)
            self.assertTrue(answer["evidence_refs"])
            missing = rag.answer("no_such_term_for_agent_runtime_xyz")
            self.assertEqual(missing["evidence_count"], 0)
            self.assertTrue(missing["no_evidence_refusal"])

    def test_internal_tool_manifest_blocks_public_mcp_and_qwen_execution(self):
        manifest = load_manifest(REPO_ROOT / "configs" / "internal_tool_manifest.json")
        result = validate_internal_manifest(manifest)
        self.assertTrue(result["ok"])
        self.assertFalse(result["public_mcp_exposed"])
        self.assertFalse(result["qwen_tool_execution_authority"])
        self.assertEqual(result["mutating_not_dispatcher_only"], [])


if __name__ == "__main__":
    unittest.main()
