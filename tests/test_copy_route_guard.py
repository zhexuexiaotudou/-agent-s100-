from __future__ import annotations

import time
import unittest
from dataclasses import replace

from src.harness.copy_route_guard import (
    approval_phrase,
    assert_no_private_leak,
    clone_candidate,
    confirm,
    create_signed_approval_token,
    dry_run,
    execute,
    preview,
    rollback,
    validate_signed_approval_token,
    validation_reasons,
)
from src.harness.copy_route_types import CopyCandidate, CopyRouteFeatureFlags


GOOD_SHA = "a" * 64


def candidate(**overrides):
    base = CopyCandidate(
        action_type="copy",
        source_relative_path="Collections/CodexPreflight/source/example.txt",
        target_relative_path="Collections/CodexPreflight/target/example.txt",
        source_sha256=GOOD_SHA,
        expected_size_bytes=229,
        source_owner_scope="operator_visible",
    )
    return replace(base, **overrides)


class CopyRouteGuardTests(unittest.TestCase):
    def assertRejected(self, cand, reason):
        reasons = validation_reasons(cand)
        self.assertIn(reason, reasons)

    def assertRouteRedacted(self, decision):
        self.assertTrue(assert_no_private_leak(decision.response)[0], decision.response)
        self.assertTrue(assert_no_private_leak(decision.audit_event)[0], decision.audit_event)

    def test_valid_candidate_has_no_reasons(self):
        self.assertEqual(validation_reasons(candidate()), [])

    def test_preview_allows_valid_candidate(self):
        decision = preview(candidate())
        self.assertTrue(decision.allowed)
        self.assertRouteRedacted(decision)

    def test_dry_run_allows_valid_candidate_and_no_write(self):
        decision = dry_run(candidate())
        self.assertTrue(decision.allowed)
        self.assertFalse(decision.response["writes_performed"])
        self.assertIn("approval_phrase", decision.response)
        self.assertRouteRedacted(decision)

    def test_confirm_issues_candidate_bound_token(self):
        cand = candidate()
        decision = confirm(cand, approval_phrase(cand), now=1000)
        self.assertTrue(decision.allowed)
        token = decision.response["signed_approval_token"]
        self.assertTrue(token["candidate_fingerprint"])
        self.assertRouteRedacted(decision)

    def test_wrong_approval_phrase_rejected(self):
        decision = confirm(candidate(), "APPROVE WRONG")
        self.assertFalse(decision.allowed)
        self.assertIn("approval_phrase_mismatch", decision.reason_codes)

    def test_execute_blocked_by_default_even_with_token(self):
        cand = candidate()
        token = create_signed_approval_token(cand, now=1000)
        decision = execute(cand, approval_token=token, operator_approved=True, env_enabled=True, approval_file_present=True, now=1001)
        self.assertFalse(decision.allowed)
        self.assertIn("execute_feature_disabled", decision.reason_codes)
        self.assertFalse(decision.response["writes_performed"])

    def test_execute_can_authorize_only_when_every_gate_present(self):
        cand = candidate()
        flags = CopyRouteFeatureFlags(execute_enabled=True)
        token = create_signed_approval_token(cand, now=1000)
        decision = execute(cand, flags=flags, approval_token=token, operator_approved=True, env_enabled=True, approval_file_present=True, now=1001)
        self.assertTrue(decision.allowed)
        self.assertFalse(decision.response["execution_performed_by_guard"])

    def test_execute_requires_env(self):
        cand = candidate()
        flags = CopyRouteFeatureFlags(execute_enabled=True)
        token = create_signed_approval_token(cand, now=1000)
        decision = execute(cand, flags=flags, approval_token=token, operator_approved=True, env_enabled=False, approval_file_present=True, now=1001)
        self.assertFalse(decision.allowed)
        self.assertIn("execute_env_not_enabled", decision.reason_codes)

    def test_execute_requires_operator_file(self):
        cand = candidate()
        flags = CopyRouteFeatureFlags(execute_enabled=True)
        token = create_signed_approval_token(cand, now=1000)
        decision = execute(cand, flags=flags, approval_token=token, operator_approved=True, env_enabled=True, approval_file_present=False, now=1001)
        self.assertFalse(decision.allowed)
        self.assertIn("operator_approval_file_missing", decision.reason_codes)

    def test_execute_requires_operator_approved_state(self):
        cand = candidate()
        flags = CopyRouteFeatureFlags(execute_enabled=True)
        token = create_signed_approval_token(cand, now=1000)
        decision = execute(cand, flags=flags, approval_token=token, operator_approved=False, env_enabled=True, approval_file_present=True, now=1001)
        self.assertFalse(decision.allowed)
        self.assertIn("operator_approval_missing", decision.reason_codes)

    def test_execute_requires_token(self):
        flags = CopyRouteFeatureFlags(execute_enabled=True)
        decision = execute(candidate(), flags=flags, operator_approved=True, env_enabled=True, approval_file_present=True)
        self.assertFalse(decision.allowed)
        self.assertIn("approval_token_missing", decision.reason_codes)

    def test_token_expiry_rejected(self):
        cand = candidate()
        token = create_signed_approval_token(cand, now=1000, ttl_seconds=1)
        ok, reason = validate_signed_approval_token(token, cand, now=1002)
        self.assertFalse(ok)
        self.assertEqual(reason, "approval_token_expired")

    def test_token_signature_tamper_rejected(self):
        cand = candidate()
        token = create_signed_approval_token(cand, now=1000)
        token["args_hash"] = "bad"
        ok, reason = validate_signed_approval_token(token, cand, now=1001)
        self.assertFalse(ok)
        self.assertEqual(reason, "approval_token_signature_mismatch")

    def test_token_candidate_mismatch_rejected(self):
        cand = candidate()
        other = candidate(target_relative_path="Collections/CodexPreflight/target/other.txt")
        token = create_signed_approval_token(cand, now=1000)
        ok, reason = validate_signed_approval_token(token, other, now=1001)
        self.assertFalse(ok)
        self.assertIn("mismatch", reason)

    def test_token_nonce_reuse_rejected(self):
        cand = candidate()
        token = create_signed_approval_token(cand, now=1000, nonce="n1")
        seen = set()
        self.assertTrue(validate_signed_approval_token(token, cand, now=1001, seen_nonces=seen)[0])
        ok, reason = validate_signed_approval_token(token, cand, now=1001, seen_nonces=seen)
        self.assertFalse(ok)
        self.assertEqual(reason, "approval_token_nonce_reuse")

    def test_rollback_blocked_by_default(self):
        decision = rollback(candidate(), operator_approved=True)
        self.assertFalse(decision.allowed)
        self.assertIn("rollback_feature_disabled", decision.reason_codes)

    def test_delete_rejected(self):
        self.assertRejected(candidate(action_type="delete"), "action_type_not_copy")

    def test_move_rejected(self):
        self.assertRejected(candidate(action_type="move"), "action_type_not_copy")

    def test_rename_rejected(self):
        self.assertRejected(candidate(action_type="rename"), "action_type_not_copy")

    def test_chmod_rejected(self):
        self.assertRejected(candidate(action_type="chmod"), "action_type_not_copy")

    def test_absolute_source_rejected(self):
        self.assertRejected(candidate(source_relative_path="/mnt/nas/openclaw/Personal/a.txt"), "source_path_not_safe_relative")

    def test_windows_absolute_target_rejected(self):
        self.assertRejected(candidate(target_relative_path="C:\\Users\\x\\file.txt"), "target_path_not_safe_relative")

    def test_unc_path_rejected(self):
        self.assertRejected(candidate(source_relative_path="\\\\nas\\share\\file.txt"), "source_path_not_safe_relative")

    def test_traversal_source_rejected(self):
        self.assertRejected(candidate(source_relative_path="Collections/CodexPreflight/source/../secret.txt"), "source_path_not_safe_relative")

    def test_encoded_traversal_rejected(self):
        self.assertRejected(candidate(target_relative_path="Collections/CodexPreflight/target/%2e%2e/secret.txt"), "target_path_not_safe_relative")

    def test_source_prefix_rejected(self):
        self.assertRejected(candidate(source_relative_path="Documents/example.txt"), "source_prefix_not_allowlisted")

    def test_target_prefix_rejected(self):
        self.assertRejected(candidate(target_relative_path="Collections/Other/example.txt"), "target_prefix_not_allowlisted")

    def test_invalid_hash_rejected(self):
        self.assertRejected(candidate(source_sha256="bad"), "source_sha256_missing_or_invalid")

    def test_zero_size_rejected(self):
        self.assertRejected(candidate(expected_size_bytes=0), "expected_size_not_positive")

    def test_size_limit_rejected(self):
        self.assertRejected(candidate(expected_size_bytes=1048577), "expected_size_exceeds_limit")

    def test_target_exists_rejected(self):
        self.assertRejected(candidate(target_exists_now=True), "target_already_exists")

    def test_target_parent_missing_rejected(self):
        self.assertRejected(candidate(target_parent_exists=False), "target_parent_missing")

    def test_source_symlink_rejected(self):
        self.assertRejected(candidate(source_is_symlink=True), "symlink_rejected")

    def test_target_parent_symlink_rejected(self):
        self.assertRejected(candidate(target_parent_is_symlink=True), "symlink_rejected")

    def test_recursive_rejected(self):
        self.assertRejected(candidate(recursive=True), "recursive_rejected")

    def test_overwrite_rejected(self):
        self.assertRejected(candidate(overwrite=True), "overwrite_rejected")

    def test_qwen_autonomous_rejected(self):
        self.assertRejected(candidate(requested_by_qwen=True), "qwen_has_no_execution_authority")

    def test_cloud_derived_rejected(self):
        self.assertRejected(candidate(cloud_derived=True), "cloud_derived_write_rejected")

    def test_owner_scope_rejected(self):
        self.assertRejected(candidate(source_owner_scope="unknown"), "source_owner_scope_not_allowed")

    def test_same_source_target_rejected(self):
        self.assertRejected(candidate(target_relative_path="Collections/CodexPreflight/source/example.txt"), "source_target_same_path")

    def test_clone_candidate_helper(self):
        cloned = clone_candidate(candidate(), overwrite=True)
        self.assertTrue(cloned.overwrite)


if __name__ == "__main__":
    unittest.main()
