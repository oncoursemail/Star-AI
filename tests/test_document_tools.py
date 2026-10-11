import asyncio
import copy
import json
import threading
from types import SimpleNamespace

import pytest

from star.agent import execute
from star.document_tools import DocumentTools
from star.documents import DocumentStore
from star.turn_memory import TurnMemory


class Store:
    def __init__(self, datasets=None):
        self.tables = datasets or []
        self.calls = []
        self.thread = threading.get_ident()

    def datasets(self):
        assert threading.get_ident() == self.thread
        return self.tables

    def context(self, query, budget_chars):
        assert threading.get_ident() == self.thread
        self.calls.append((query, budget_chars))
        return "[D1:2] brief.txt, line 8\nNever use neon. Existing approved reference."


def table(identifier="data-01"):
    return {"id": identifier, "name": "costs.csv / data", "source": "costs.csv, rows 2-4",
            "columns": ["Amount", "Category"], "rows": [["0.1", "A"], ["0.2", "A"], [None, "B"]],
            "warnings": ["One row has a missing Amount."]}


def reply(text="", calls=()):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text, tool_calls=list(calls)))])


def tool(name, args, identifier="call-1"):
    return SimpleNamespace(id=identifier, function=SimpleNamespace(name=name, arguments=json.dumps(args)))


class Models:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    async def create(self, **kwargs):
        self.requests.append(copy.deepcopy(kwargs))
        if not self.replies:
            raise AssertionError("Unexpected extra model request")
        return self.replies.pop(0)


def client(models):
    return SimpleNamespace(chat=SimpleNamespace(completions=models))


def returned_tool(request, identifier="call-1"):
    message = next(item for item in request["messages"] if item.get("tool_call_id") == identifier)
    result = json.loads(message["content"])
    return result, json.loads(result["output"])


def test_search_only_disclosure_and_exact_retrieved_evidence():
    store = Store()
    gateway = DocumentTools(store)
    definitions = gateway.definitions("Read my file")
    assert [definition["name"] for definition in definitions] == ["star_document_search"]
    schema = definitions[0]["inputSchema"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["query"]["maxLength"] == 800
    assert schema["properties"]["budget_chars"]["maximum"] == 8000
    result = gateway.call("star_document_search", {"query": "reference", "budget_chars": 1000},
                          enabled={"star_document_search"})
    assert result["isError"] is False
    assert result["structuredContent"]["context"] == store.context("reference", 1000)
    assert result["structuredContent"]["provenance"]["untrusted"] is True
    assert result["structuredContent"]["provenance"]["scope"] == "attached sources only"
    assert store.calls[0] == ("reference", 1000)


def test_attached_data_schema_discloses_exact_scoped_ids_and_columns():
    gateway = DocumentTools(Store([table()]))
    definitions = gateway.definitions("Add the amounts")
    assert [definition["name"] for definition in definitions] == ["star_document_search", "star_data_analyze"]
    data = definitions[1]
    for metadata in ("data-01", "Amount", "Category", "costs.csv"):
        assert metadata in data["description"]
    assert data["inputSchema"]["additionalProperties"] is False
    result = gateway.call("star_document_search", {"query": "Amount"})
    inventory = result["structuredContent"]["datasets"]
    assert inventory["tables"][0]["id"] == "data-01"
    assert inventory["tables"][0]["columns"] == ["Amount", "Category"]
    assert inventory["tables"][0]["source"] == "costs.csv, rows 2-4"
    assert "rows" not in inventory["tables"][0]


def test_selected_small_table_calculates_with_96_attached_tables(tmp_path):
    paths = []
    for number in range(3):
        path = tmp_path / f"tables{number}.json"
        path.write_text(json.dumps({f"table{index}": [{"amount": index}]
                                    for index in range(32)}), encoding="utf-8")
        paths.append(path)
    with DocumentStore(tmp_path / "home", "project", "chat") as store:
        store.ingest(paths)
        datasets = store.datasets()
        assert len(datasets) == 96
        target = next(table for table in datasets if table["name"] == "tables2.json / $.table31")
        result = DocumentTools(store).call("star_data_analyze", {
            "dataset_id": target["id"], "operation": "count"})
        assert result["isError"] is False
        calculation = result["structuredContent"]
        assert calculation["value"] == calculation["selected_rows"] == calculation["input_rows"] == 1
        assert calculation["dataset_id"] == target["id"]
        assert calculation["source"] == "tables2.json, $.table31"
        assert calculation["provenance"]["dataset_id"] == target["id"]


def test_bounded_inventory_prioritizes_requested_column_and_admits_omissions():
    wide = table()
    wide["columns"] = [f"OtherColumn{number}-" + "x" * 100 for number in range(100)] + ["Revenue"]
    wide["rows"] = []
    result = DocumentTools(Store([wide])).call("star_document_search", {"query": "Revenue"})
    inventory = result["structuredContent"]["datasets"]
    assert len(json.dumps(inventory, ensure_ascii=False)) <= 4000
    assert inventory["tables"][0]["columns"][0] == "Revenue"
    assert inventory["tables"][0]["columns_omitted"] > 0
    assert "omitted" in inventory["note"]


@pytest.mark.parametrize("args", [
    {}, {"query": " "}, {"query": "x" * 801}, {"query": 5},
    {"query": "ok", "budget_chars": True}, {"query": "ok", "budget_chars": 99},
    {"query": "ok", "budget_chars": 8001}, {"query": "ok", "path": "../../secret.env"},
])
def test_search_argument_errors_visible_without_accessing_store(args):
    store = Store()
    result = DocumentTools(store).call("star_document_search", args)
    assert result["isError"] is True
    assert result["structuredContent"]["error"]["message"]
    assert not store.calls


def test_gateway_denies_unattached_and_unknown_tools():
    store = Store([table()])
    gateway = DocumentTools(store)
    assert not gateway.owns("star_document_open_path")
    for name in ("star_document_search", "star_data_analyze", "star_document_open_path"):
        assert gateway.call(name, {"query": "x"}, enabled=set())["isError"] is True
    assert not store.calls
    assert DocumentTools(None).definitions("data") == []
    assert DocumentTools(None).call("star_document_search", {"query": "x"})["isError"] is True


def test_arithmetic_exact_decimal_provenance_and_missing_counts():
    result = DocumentTools(Store([table()])).call(
        "star_data_analyze", {"dataset_id": "data-01", "operation": "sum", "column": "Amount"},
        enabled={"star_data_analyze"})
    assert result["isError"] is False
    data = result["structuredContent"]
    assert data["value"] == "0.3"
    assert data["exact"] is True
    assert (data["input_rows"], data["used_rows"], data["missing_rows"]) == (3, 2, 1)
    assert data["provenance"]["dataset_id"] == "data-01"
    assert data["provenance"]["source"] == data["source"] == "costs.csv, rows 2-4"
    assert "without executing code" in data["provenance"]["note"]


@pytest.mark.parametrize("args", [
    {"dataset_id": "foreign", "operation": "count"},
    {"dataset_id": "data-01", "operation": "exec", "column": "Amount"},
    {"dataset_id": "data-01", "operation": "sum", "column": "amount"},
    {"dataset_id": "data-01", "operation": "count", "code": "import os"},
    {"dataset_id": "data-01", "operation": "count", "path": "/another.csv"},
])
def test_data_arguments_cannot_widen_scope_or_execute_code(args):
    result = DocumentTools(Store([table()])).call("star_data_analyze", args)
    assert result["isError"] is True
    assert "error" in result["structuredContent"]
    assert "value" not in result["structuredContent"]


def test_large_group_results_fail_visibly_instead_of_being_cut_in_transport():
    dataset = table()
    dataset["rows"] = [["1", f"group-{number}-" + "x" * 180] for number in range(100)]
    result = DocumentTools(Store([dataset])).call(
        "star_data_analyze", {"dataset_id": "data-01", "operation": "sum", "column": "Amount", "group_by": "Category"})
    assert result["isError"] is True
    assert "result budget" in result["structuredContent"]["error"]["message"]
    assert "groups" not in result["structuredContent"]


def test_execute_uses_real_attached_csv_calculation_and_returns_exact_source(tmp_path):
    csv = tmp_path / "costs.csv"
    csv.write_text("Amount,Category\n0.1,A\n0.2,A\n", encoding="utf-8")
    question = "What is the exact sum of Amount in my attached costs.csv?"
    with DocumentStore(tmp_path / "store", "project", "chat") as store:
        store.ingest([csv])
        dataset = store.datasets()[0]
        models = Models([
            reply(calls=[tool("star_document_search", {"query": "costs Amount"}, "discover")]),
            reply(calls=[tool("star_data_analyze", {"dataset_id": dataset["id"],
                                                  "operation": "sum", "column": "Amount"}, "calc")]),
            reply("The exact sum is 0.3, calculated from costs.csv."),
        ])
        events = []
        answer, _, _ = asyncio.run(execute(
            client=client(models), model="fake", prompt=question, image_paths=[], max_calls=3,
            document_tools=DocumentTools(store), on_event=events.append, tool_memory=TurnMemory(sticky=True)))
        assert answer.startswith("The exact sum is 0.3")
        assert len(models.requests) == 3
        names = [tool["function"]["name"] for tool in models.requests[0]["tools"]]
        assert names == ["star_document_search", "star_data_analyze"]
        assert dataset["id"] in models.requests[0]["tools"][1]["function"]["description"]
        assert all(request["messages"][1]["content"][0]["text"].startswith(question)
                   for request in models.requests)
        wrapped, discovery = returned_tool(models.requests[1], "discover")
        assert wrapped["isError"] is False
        assert discovery["datasets"]["tables"][0]["id"] == dataset["id"]
        wrapped, calculated = returned_tool(models.requests[2], "calc")
        assert wrapped["isError"] is False
        assert calculated["value"] == "0.3" and calculated["exact"] is True
        assert calculated["source"] == dataset["source"]
        assert calculated["provenance"]["dataset_id"] == dataset["id"]
        assert [event["tool"] for event in events if event["event"] == "tool_started"] == names


def test_cross_chat_dataset_id_is_rejected_by_actual_scoped_store(tmp_path):
    csv = tmp_path / "scope.csv"
    csv.write_text("Amount\n3\n", encoding="utf-8")
    with DocumentStore(tmp_path / "store", "same project", "chat-1") as first:
        first.ingest([csv])
        foreign = first.datasets()[0]["id"]
    with DocumentStore(tmp_path / "store", "same project", "chat-2") as second:
        second.ingest([csv])
        result = DocumentTools(second).call("star_data_analyze", {"dataset_id": foreign, "operation": "count"})
        assert result["isError"] is True
        assert "not among the attached tables" in result["structuredContent"]["error"]["message"]


def test_execute_rejects_document_tool_when_it_was_not_attached():
    class Undisclosed(DocumentTools):
        def definitions(self, prompt):
            return []
        def call(self, *args, **kwargs):
            raise AssertionError("Unattached tool must not execute")

    models = Models([reply(calls=[tool("star_data_analyze", {"dataset_id": "data-01", "operation": "count"})]),
                     reply("The capability was unavailable.")])
    events = []
    asyncio.run(execute(client=client(models), model="fake", prompt="Question", image_paths=[],
                        document_tools=Undisclosed(Store([table()])), on_event=events.append))
    wrapped = json.loads(next(item for item in models.requests[1]["messages"] if item["role"] == "tool")["content"])
    assert wrapped["isError"] is True
    assert "Tool request rejected" in wrapped["output"]
    assert any(event["event"] == "tool_rejected" for event in events)


def test_hallucinated_unregistered_document_capability_is_denied():
    store = Store([table()])
    models = Models([reply(calls=[tool("star_document_open_path", {"path": "secret.env"})]), reply("Denied.")])
    asyncio.run(execute(client=client(models), model="fake", prompt="Read attached files", image_paths=[],
                        document_tools=DocumentTools(store)))
    wrapped = json.loads(next(item for item in models.requests[1]["messages"] if item["role"] == "tool")["content"])
    assert wrapped["isError"] is True
    assert not store.calls


def test_validation_failure_reaches_model_as_error_not_an_invented_value():
    models = Models([reply(calls=[tool("star_data_analyze", {"dataset_id": "data-01", "operation": "sum",
                                                          "column": "not a column"})]), reply("Column unavailable.")])
    asyncio.run(execute(client=client(models), model="fake", prompt="Calculate my file", image_paths=[],
                        document_tools=DocumentTools(Store([table()]))))
    wrapped = json.loads(next(item for item in models.requests[1]["messages"] if item["role"] == "tool")["content"])
    assert wrapped["isError"] is True
    assert "not an exact column name" in wrapped["output"]


def test_specific_file_wins_catalog_with_shared_extensions_and_columns():
    tables = [{**table(), 'id': f'data_{index:024x}',
               'name': f'tables{index}.json / $.table31',
               'source': f'tables{index}.json, $.table31'} for index in range(96)]
    gateway = DocumentTools(Store(tables))
    result = gateway.call('star_document_search', {'query': 'tables95.json table31'})
    inventory = result['structuredContent']['datasets']
    assert inventory['tables'][0]['id'] == tables[-1]['id']
    assert inventory['tables_omitted'] > 0
    description = gateway.definitions('Count rows from tables95.json table31')[1]['description']
    assert tables[-1]['id'] in description
