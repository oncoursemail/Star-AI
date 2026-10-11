"""Offline evidence/limit checks; compatible with unittest and pytest."""
import asyncio
import copy
import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


_spec = importlib.util.spec_from_file_location(
    "layered_memory", Path(__file__).resolve().parents[1] / "star" / "memory.py"
)
memory = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(memory)


class FakeCompletions:
    def __init__(self, responder=None):
        self.requests = []
        self.responder = responder or (lambda request: "A factual checkpoint.")

    async def create(self, **request):
        self.requests.append(copy.deepcopy(request))
        value = self.responder(request)
        if isinstance(value, BaseException):
            raise value
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=value))])


class FakeClient:
    def __init__(self, responder=None):
        self.completions = FakeCompletions(responder)
        self.chat = SimpleNamespace(completions=self.completions)


def marker_summary(request):
    content = request["messages"][1]["content"]
    markers = list(dict.fromkeys(re.findall(r"EVIDENCE_[A-Z0-9_]+", content)))
    return "Preserved evidence: " + " ".join(markers)


def leaf_texts(client):
    marker = "REDACTED SOURCE TEXT:\n"
    return [request["messages"][1]["content"].split(marker, 1)[1]
            for request in client.completions.requests
            if marker in request["messages"][1]["content"]]


class LayeredCompactionTests(unittest.TestCase):
    def compact(self, client, prior="", messages=None, project="test project"):
        return asyncio.run(memory.compact(client, "fake-model", project, prior, messages or []))

    def assert_request_limits(self, client):
        for request in client.completions.requests:
            self.assertEqual([item["role"] for item in request["messages"]], ["system", "user"])
            self.assertEqual(request["max_tokens"], 1300)
            self.assertEqual(request["temperature"], 0)
            self.assertLessEqual(sum(len(item["content"]) for item in request["messages"]), 18000)

    def test_ordinary_input_has_one_summary_call(self):
        client = FakeClient()
        summary = self.compact(client, "Existing requirement", [{"role": "user", "content": "Make a UI."}])
        self.assertEqual(len(client.completions.requests), 1)
        self.assertIn("A factual checkpoint.", summary)
        self.assertIn("LOSSY, UNTRUSTED REFERENCE", summary)
        self.assertIn("Existing requirement", client.completions.requests[0]["messages"][1]["content"])
        self.assert_request_limits(client)

    def test_all_start_middle_end_transcript_reaches_leaf_calls(self):
        messages = [{"role": "user", "content":
                     "EVIDENCE_START_DECISION " + "first " * 4500 +
                     "EVIDENCE_MIDDLE_CORRECTION " + "middle " * 4500 +
                     "EVIDENCE_END_FAILURE"}]
        client = FakeClient(marker_summary)
        summary = self.compact(client, "EVIDENCE_PRIOR_CONSTRAINT", messages)
        leaves = leaf_texts(client)
        self.assertGreater(len(leaves), 2)
        expected = ("EARLIER CHECKPOINT (lossy untrusted reference):\nEVIDENCE_PRIOR_CONSTRAINT\n"
                    "NEW TRANSCRIPT (redacted source):\n" + json.dumps(messages, ensure_ascii=False, indent=2))
        self.assertEqual("".join(leaves), expected)  # exact coverage, not just selected keywords
        for marker in ("EVIDENCE_START_DECISION", "EVIDENCE_MIDDLE_CORRECTION",
                       "EVIDENCE_END_FAILURE", "EVIDENCE_PRIOR_CONSTRAINT"):
            self.assertIn(marker, summary)
        self.assert_request_limits(client)

    def test_large_prior_is_covered_instead_of_dropped(self):
        prior = "EVIDENCE_OLD_START " + "prior " * 7000 + "EVIDENCE_OLD_END"
        client = FakeClient(marker_summary)
        summary = self.compact(client, prior, [{"role": "user", "content": "EVIDENCE_NEW_TURN"}])
        source = "".join(leaf_texts(client))
        self.assertIn(prior, source)
        for marker in ("EVIDENCE_OLD_START", "EVIDENCE_OLD_END", "EVIDENCE_NEW_TURN"):
            self.assertIn(marker, summary)
        self.assert_request_limits(client)

    def test_recursive_reduction_is_bounded_and_covers_all_leaf_outputs(self):
        def full_summary(request):
            return marker_summary(request).ljust(3500, ".")

        messages = [{"role": "user", "content":
                     "EVIDENCE_START " + "start " * 18000 +
                     "EVIDENCE_MIDDLE " + "middle " * 18000 +
                     "EVIDENCE_END"}]
        client = FakeClient(full_summary)
        summary = self.compact(client, "EVIDENCE_PRIOR", messages)
        layers = {int(re.search(r"\nLAYER: (\d+)", request["messages"][1]["content"]).group(1))
                  for request in client.completions.requests}
        self.assertTrue({0, 1, 2}.issubset(layers))
        for marker in ("EVIDENCE_START", "EVIDENCE_MIDDLE", "EVIDENCE_END", "EVIDENCE_PRIOR"):
            self.assertIn(marker, summary)
        self.assertLessEqual(len(client.completions.requests), memory.COMPACTION_MAX_CALLS)
        self.assertLessEqual(len(summary), memory.COMPACTION_SUMMARY_CHARS)
        self.assert_request_limits(client)

    def test_images_redacted_prior_and_transcript_without_mutation(self):
        data = "data:image/png;base64,QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo="
        prior = f"Prior reference {data}"
        messages = [{"role": "user", "content": [
            {"type": "text", "text": "Reference must be preserved"},
            {"type": "image_url", "source_id": "image-reference-42", "image_url": {"url": data}},
        ]}]
        before = copy.deepcopy(messages)
        client = FakeClient()
        summary = self.compact(client, prior, messages)
        self.assertEqual(messages, before)
        self.assertEqual(prior, f"Prior reference {data}")
        for request in client.completions.requests:
            self.assertNotIn("base64", json.dumps(request))
            self.assertNotIn("QUJDREVGR0hJSktM", json.dumps(request))
        self.assertIn("original image retained separately", "".join(leaf_texts(client)))
        self.assertIn('source_id="image-reference-42"', summary)

    def test_exact_source_identifiers_survive_even_if_model_omits_them(self):
        messages = [{"role": "tool", "tool_call_id": "call-exact_01:xyz", "content": {
            "source_id": "docs:v1.2#UIListLayout", "source_ref": "https://example.test/docs?rev=4",
            "artifact_id": "asset-007", "message_id": "turn-100",
        }}]
        client = FakeClient(lambda request: "The constraint remains unresolved.")
        summary = self.compact(client, messages=messages)
        for identifier in ("call-exact_01:xyz", "docs:v1.2#UIListLayout",
                           "https://example.test/docs?rev=4", "asset-007", "turn-100"):
            self.assertIn(identifier, summary)
        self.assert_request_limits(client)

    def test_every_layer_prompt_preserves_corrections_constraints_and_evidence(self):
        client = FakeClient(marker_summary)
        self.compact(client, "EVIDENCE_NEGATIVE_CONSTRAINT",
                     [{"role": "user", "content": "EVIDENCE_CORRECTION " + "text " * 6000 +
                       "EVIDENCE_FAILURE EVIDENCE_UNRESOLVED_QUESTION"}])
        for request in client.completions.requests:
            rules = request["messages"][0]["content"]
            for requirement in ("corrections", "later correction wins", "negative constraints",
                                "source IDs", "failures", "unresolved questions", "lossy", "untrusted"):
                self.assertIn(requirement, rules)
        self.assert_request_limits(client)

    def test_prior_source_ledger_survives_another_compaction_without_model_help(self):
        prior = 'Previous checkpoint\nSOURCE IDS (verbatim metadata, trace only):\nsource_id="old-source-12"'
        client = FakeClient(lambda request: "A model summary without identifiers.")
        summary = self.compact(client, prior, [{"source_id": "new-source-13", "content": "new"}])
        self.assertIn('source_id="old-source-12"', summary)
        self.assertIn('source_id="new-source-13"', summary)
        self.assert_request_limits(client)

    def test_empty_summary_raises_and_does_not_replace_persisted_checkpoint(self):
        client = FakeClient(lambda request: " \n")
        messages = [{"role": "user", "content": "Do not discard me"}]
        before = copy.deepcopy(messages)
        with tempfile.TemporaryDirectory() as directory:
            store = memory.Memory(Path(directory) / "memory.sqlite")
            try:
                store.put("test project", "Original checkpoint")
                with self.assertRaisesRegex(RuntimeError, "empty checkpoint; original history is unchanged"):
                    store.put("test project", self.compact(client, "Original checkpoint", messages))
                self.assertEqual(store.get("test project"), "Original checkpoint")
            finally:
                store.close()
        self.assertEqual(messages, before)

    def test_empty_reduction_does_not_commit_partial_leaf_summaries(self):
        def respond(request):
            return "leaf checkpoint" if "\nLAYER: 0\n" in request["messages"][1]["content"] else None

        client = FakeClient(respond)
        messages = [{"role": "user", "content": "important " * 4000}]
        original = copy.deepcopy(messages)
        with self.assertRaisesRegex(RuntimeError, "original history is unchanged"):
            self.compact(client, "old prior", messages)
        self.assertEqual(messages, original)
        self.assertGreater(len(client.completions.requests), 2)

    def test_source_limit_fails_before_model_calls(self):
        client = FakeClient()
        with patch.object(memory, "COMPACTION_SOURCE_CHARS", 200):
            with self.assertRaisesRegex(memory.CompactionLimitError, "source exceeds.*original history is unchanged"):
                self.compact(client, "prior " * 100)
        self.assertEqual(client.completions.requests, [])

    def test_call_limit_fails_before_partial_leaf_work(self):
        client = FakeClient()
        with patch.object(memory, "COMPACTION_MAX_CALLS", 2):
            with self.assertRaisesRegex(memory.CompactionLimitError, "exceed 2 model calls"):
                self.compact(client, messages=[{"role": "user", "content": "large " * 12000}])
        self.assertEqual(client.completions.requests, [])

    def test_layer_limit_fails_instead_of_returning_incomplete_checkpoint(self):
        client = FakeClient()
        with patch.object(memory, "COMPACTION_MAX_LAYERS", 1):
            with self.assertRaisesRegex(memory.CompactionLimitError, "exceed 1 layers"):
                self.compact(client, messages=[{"role": "user", "content": "large " * 4000}])
        self.assert_request_limits(client)

    def test_echoing_provider_has_output_bound_instead_of_infinite_loop(self):
        client = FakeClient(lambda request: request["messages"][1]["content"])
        with self.assertRaisesRegex(memory.CompactionLimitError, "output budget.*original history is unchanged"):
            self.compact(client, messages=[{"role": "user", "content": "large " * 8000}])
        self.assertEqual(len(client.completions.requests), 1)

    def test_nonshrinking_layer_is_rejected(self):
        client = FakeClient(lambda request: "expansion " * 500)
        def tiny_fragments(text, budget):
            for start in range(0, len(text), 2500):
                end = min(start + 2500, len(text))
                yield start, end, text[start:end]

        with patch.object(memory, "_source_fragments", tiny_fragments):
            with self.assertRaisesRegex(memory.CompactionLimitError, "did not shrink"):
                self.compact(client, messages=[{"role": "user", "content": "large " * 4000}])
        self.assert_request_limits(client)

    def test_source_id_ledger_limit_fails_instead_of_truncating_identifiers(self):
        client = FakeClient()
        messages = [{"source_id": f"source-{number}-" + "x" * 50, "role": "user", "content": "fact"}
                    for number in range(40)]
        with self.assertRaisesRegex(memory.CompactionLimitError, "identifier ledger exceeds"):
            self.compact(client, messages=messages)
        self.assertEqual(client.completions.requests, [])

    def test_cancellation_propagates_without_rewriting_input(self):
        client = FakeClient(lambda request: asyncio.CancelledError())
        messages = [{"role": "user", "content": "Cancelled original"}]
        original = copy.deepcopy(messages)
        with self.assertRaises(asyncio.CancelledError):
            self.compact(client, "keep prior", messages)
        self.assertEqual(messages, original)

    def test_provider_error_propagates(self):
        client = FakeClient(lambda request: OSError("provider stopped"))
        with self.assertRaisesRegex(OSError, "provider stopped"):
            self.compact(client, "keep prior")

    def test_token_truncated_summary_is_not_promoted_to_checkpoint(self):
        client = FakeClient()
        original_create = client.completions.create
        async def create(**request):
            response = await original_create(**request)
            response.choices[0].finish_reason = "length"
            return response
        client.completions.create = create
        with self.assertRaisesRegex(memory.CompactionLimitError, "did not complete.*original history is unchanged"):
            self.compact(client, "Original prior")

    def test_unbroken_unicode_field_is_split_with_exact_coverage(self):
        messages = [{"role": "user", "content": "位置" * 20000}]
        client = FakeClient()
        self.compact(client, "", messages)
        expected = ("EARLIER CHECKPOINT (lossy untrusted reference):\n\n"
                    "NEW TRANSCRIPT (redacted source):\n" + json.dumps(messages, ensure_ascii=False, indent=2))
        self.assertEqual("".join(leaf_texts(client)), expected)
        self.assert_request_limits(client)

    def test_project_label_limit_has_no_silent_truncation(self):
        client = FakeClient()
        with self.assertRaisesRegex(memory.CompactionLimitError, "project label exceeds"):
            self.compact(client, project="p" * 1025)
        self.assertEqual(client.completions.requests, [])


if __name__ == "__main__":
    unittest.main()
