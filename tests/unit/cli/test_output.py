"""Tests for CLI output formatting (archai.cli.output)."""

import json


from archai.cli.output import (
    _ensure_dict,
    format_blast_radius,
    format_context_packet,
    format_process_result,
    format_validation,
)


class TestEnsureDict:
    """Tests for the _ensure_dict helper."""

    def test_with_plain_dict(self):
        d = {"foo": 1, "bar": 2}
        result = _ensure_dict(d)
        assert result is d
        assert result == {"foo": 1, "bar": 2}

    def test_with_model_dump_object(self):
        class FakeModel:
            def model_dump(self):
                return {"foo": 1, "bar": 2}

        result = _ensure_dict(FakeModel())
        assert result == {"foo": 1, "bar": 2}

    def test_with_dict_method_object(self):
        class FakeModel:
            def dict(self):
                return {"foo": 1, "bar": 2}

        result = _ensure_dict(FakeModel())
        assert result == {"foo": 1, "bar": 2}

    def test_model_dump_preferred_over_dict(self):
        class FakeModel:
            def model_dump(self):
                return {"from": "model_dump"}

            def dict(self):
                return {"from": "dict"}

        result = _ensure_dict(FakeModel())
        assert result == {"from": "model_dump"}

    def test_with_dict_like_iterable(self):
        result = _ensure_dict([("a", 1), ("b", 2)])
        assert result == {"a": 1, "b": 2}


SAMPLE_CONTEXT_PACKET = {
    "focus": "API Layer",
    "focus_reasoning": "The query relates to HTTP endpoints",
    "constraints": {
        "async_only": True,
        "no_blocking_io": False,
        "forbidden_dependencies": ["requests"],
        "allowed_dependencies": [],
    },
    "relevant_files": [
        {"path": "src/api/routes.py", "reason": "part of focus subsystem", "importance": 1.0},
        {"path": "src/api/handlers.py", "reason": "part of focus subsystem", "importance": 0.8},
        {"path": "tests/api/test_routes.py", "reason": "related test file", "importance": 0.8},
    ],
}

SAMPLE_CONTEXT_PACKET_EMPTY = {
    "focus": "unknown",
    "focus_reasoning": "Could not determine focus",
    "constraints": {},
    "relevant_files": [],
}


class TestFormatContextPacket:
    """Tests for format_context_packet."""

    def test_json_mode_returns_valid_json(self):
        output = format_context_packet(SAMPLE_CONTEXT_PACKET, json_mode=True)
        parsed = json.loads(output)
        assert parsed["focus"] == "API Layer"
        assert len(parsed["relevant_files"]) == 3

    def test_json_mode_with_empty_data(self):
        output = format_context_packet(SAMPLE_CONTEXT_PACKET_EMPTY, json_mode=True)
        parsed = json.loads(output)
        assert parsed["focus"] == "unknown"
        assert parsed["relevant_files"] == []

    def test_human_readable_returns_string(self):
        output = format_context_packet(SAMPLE_CONTEXT_PACKET, json_mode=False)
        assert isinstance(output, str)
        assert len(output) > 0
        assert "API Layer" in output

    def test_human_readable_empty_data(self):
        output = format_context_packet(SAMPLE_CONTEXT_PACKET_EMPTY, json_mode=False)
        assert isinstance(output, str)
        assert "unknown" in output

    def test_with_pydantic_model(self):
        output = format_context_packet(SAMPLE_CONTEXT_PACKET, json_mode=True)
        parsed = json.loads(output)
        assert "constraints" in parsed
        assert "async_only" in parsed["constraints"]

    def test_importance_bar_generated(self):
        high = {"path": "a.py", "reason": "core", "importance": 1.0}
        low = {"path": "b.py", "reason": "peripheral", "importance": 0.1}
        data = {
            "focus": "Test",
            "focus_reasoning": "Testing",
            "constraints": {},
            "relevant_files": [high, low],
        }
        output = format_context_packet(data, json_mode=False)
        assert "a.py" in output
        assert "b.py" in output


SAMPLE_BLAST_RADIUS = {
    "focus_file": "src/core/engine.py",
    "direct_dependents": ["src/api/routes.py", "src/api/handlers.py"],
    "direct_dependencies": ["src/core/models.py", "src/core/utils.py"],
    "transitive_dependents": ["src/app/main.py"],
    "subsystems_affected": {"api": 2, "app": 1},
}

SAMPLE_BLAST_RADIUS_EMPTY = {
    "focus_file": "src/standalone/config.py",
    "direct_dependents": [],
    "direct_dependencies": [],
    "transitive_dependents": [],
    "subsystems_affected": {},
}


class TestFormatBlastRadius:
    """Tests for format_blast_radius."""

    def test_json_mode_returns_valid_json(self):
        output = format_blast_radius(SAMPLE_BLAST_RADIUS, json_mode=True)
        parsed = json.loads(output)
        assert parsed["focus_file"] == "src/core/engine.py"
        assert len(parsed["direct_dependents"]) == 2

    def test_json_mode_empty_data(self):
        output = format_blast_radius(SAMPLE_BLAST_RADIUS_EMPTY, json_mode=True)
        parsed = json.loads(output)
        assert parsed["direct_dependents"] == []
        assert parsed["subsystems_affected"] == {}

    def test_human_readable_returns_string(self):
        output = format_blast_radius(SAMPLE_BLAST_RADIUS, json_mode=False)
        assert isinstance(output, str)
        assert len(output) > 0
        assert "src/core/engine.py" in output

    def test_human_readable_shows_none_for_empty(self):
        output = format_blast_radius(SAMPLE_BLAST_RADIUS_EMPTY, json_mode=False)
        assert isinstance(output, str)
        assert "(none)" in output or "none" in output.lower()

    def test_subsystems_table_included(self):
        output = format_blast_radius(SAMPLE_BLAST_RADIUS, json_mode=False)
        assert "api" in output

    def test_subsystems_table_omitted_when_empty(self):
        # Should not error out
        format_blast_radius(SAMPLE_BLAST_RADIUS_EMPTY, json_mode=False)


SAMPLE_VALIDATION_VALID = {"valid": True, "violations": []}

SAMPLE_VALIDATION_INVALID = {
    "valid": False,
    "violations": [
        {
            "file": "src/api/routes.py",
            "rule": "no_blocking_io",
            "message": "time.sleep not allowed",
        },
        {
            "file": "src/core/engine.py",
            "rule": "forbidden_dependency",
            "message": "import os not allowed",
        },
    ],
}


class TestFormatValidation:
    """Tests for format_validation."""

    def test_json_mode_valid(self):
        output = format_validation(SAMPLE_VALIDATION_VALID, json_mode=True)
        parsed = json.loads(output)
        assert parsed["valid"] is True
        assert parsed["violations"] == []

    def test_json_mode_invalid(self):
        output = format_validation(SAMPLE_VALIDATION_INVALID, json_mode=True)
        parsed = json.loads(output)
        assert parsed["valid"] is False
        assert len(parsed["violations"]) == 2

    def test_human_readable_valid(self):
        output = format_validation(SAMPLE_VALIDATION_VALID, json_mode=False)
        assert isinstance(output, str)
        assert "VALID" in output

    def test_human_readable_invalid(self):
        output = format_validation(SAMPLE_VALIDATION_INVALID, json_mode=False)
        assert isinstance(output, str)
        assert "INVALID" in output
        assert "time.sleep" in output

    def test_violations_table_omitted_when_empty(self):
        output = format_validation(SAMPLE_VALIDATION_VALID, json_mode=False)
        assert "Violations" not in output or "VALID" in output


SAMPLE_PROCESS_RESULT = {
    "repo_path": "/tmp/test-repo",
    "file_count": 10,
    "edge_count": 25,
    "cluster_count": 3,
    "clusters": {
        "cluster_1": ["src/api/routes.py", "src/api/handlers.py"],
        "cluster_2": ["src/core/engine.py"],
        "cluster_3": ["src/app/main.py"],
    },
    "cluster_names": {
        "cluster_1": "API Layer",
        "cluster_2": "Core Engine",
        "cluster_3": "App Entry",
    },
}

SAMPLE_PROCESS_RESULT_NO_CLUSTERS = {
    "repo_path": "/tmp/empty",
    "file_count": 0,
    "edge_count": 0,
    "cluster_count": 0,
    "clusters": {},
}


class TestFormatProcessResult:
    """Tests for format_process_result."""

    def test_json_mode_returns_valid_json(self):
        output = format_process_result(SAMPLE_PROCESS_RESULT, json_mode=True)
        parsed = json.loads(output)
        assert parsed["repo_path"] == "/tmp/test-repo"
        assert parsed["file_count"] == 10

    def test_json_mode_empty(self):
        output = format_process_result(SAMPLE_PROCESS_RESULT_NO_CLUSTERS, json_mode=True)
        parsed = json.loads(output)
        assert parsed["clusters"] == {}

    def test_human_readable(self):
        output = format_process_result(SAMPLE_PROCESS_RESULT, json_mode=False)
        assert isinstance(output, str)
        assert "/tmp/test-repo" in output
        assert "10" in output

    def test_human_readable_no_clusters(self):
        output = format_process_result(SAMPLE_PROCESS_RESULT_NO_CLUSTERS, json_mode=False)
        assert isinstance(output, str)
        assert "/tmp/empty" in output

    def test_json_with_pydantic_model(self):
        class FakeResult:
            def model_dump(self):
                return dict(SAMPLE_PROCESS_RESULT)

        output = format_process_result(FakeResult(), json_mode=True)
        parsed = json.loads(output)
        assert parsed["repo_path"] == "/tmp/test-repo"
