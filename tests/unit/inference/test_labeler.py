"""Tests for semantic labeling of clusters."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from archai.inference.labeler import ClusterLabel, LabeledCluster, label_clusters
from archai.inference.llm.base import LLMError


class TestClusterLabel:
    """ClusterLabel Pydantic model validation."""

    def test_construct_with_valid_fields(self):
        label = ClusterLabel(
            name="Auth Module",
            description="Handles user authentication and authorization",
            reasoning="Files are auth-related and share common dependencies",
        )
        assert label.name == "Auth Module"
        assert label.description == "Handles user authentication and authorization"
        assert label.reasoning == "Files are auth-related and share common dependencies"

    def test_missing_fields_raises_validation_error(self):
        with pytest.raises(ValueError):
            ClusterLabel()  # type: ignore[call-arg]


class TestLabeledCluster:
    """LabeledCluster Pydantic model validation."""

    def test_construct_with_valid_fields(self):
        lc = LabeledCluster(
            cluster_id="cluster_1",
            files=["src/auth/login.py", "src/auth/register.py"],
            name="Auth Module",
            description="Handles authentication",
            reasoning="All files relate to authentication",
        )
        assert lc.cluster_id == "cluster_1"
        assert lc.files == ["src/auth/login.py", "src/auth/register.py"]
        assert lc.name == "Auth Module"
        assert lc.description == "Handles authentication"


class TestLabelClusters:
    """label_clusters function."""

    async def test_returns_labeled_clusters_for_valid_input(self):
        clusters = {"cluster_1": ["src/auth/login.py", "src/auth/register.py"]}
        provider = AsyncMock()
        provider.generate_structured.return_value = ClusterLabel(
            name="Auth Module",
            description="Handles authentication",
            reasoning="Files share auth domain",
        )

        result = await label_clusters(clusters, provider)

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], LabeledCluster)
        assert result[0].cluster_id == "cluster_1"
        assert result[0].files == ["src/auth/login.py", "src/auth/register.py"]
        assert result[0].name == "Auth Module"
        assert result[0].description == "Handles authentication"

    async def test_empty_clusters_returns_empty_list(self):
        result = await label_clusters({}, AsyncMock())
        assert result == []

    async def test_provider_called_with_files_in_prompt(self):
        clusters = {"cluster_1": ["src/auth/login.py", "src/auth/register.py"]}
        provider = AsyncMock()
        provider.generate_structured.return_value = ClusterLabel(
            name="Auth",
            description="Auth subsystem",
            reasoning="R",
        )

        await label_clusters(clusters, provider)

        provider.generate_structured.assert_awaited_once()
        _args, kwargs = provider.generate_structured.await_args
        prompt = kwargs.get("prompt", "")
        assert "src/auth/login.py" in prompt
        assert "src/auth/register.py" in prompt

    async def test_provider_called_with_system_prompt(self):
        clusters = {"cluster_1": ["src/auth/login.py"]}
        provider = AsyncMock()
        provider.generate_structured.return_value = ClusterLabel(
            name="X",
            description="Y",
            reasoning="Z",
        )

        await label_clusters(clusters, provider)

        provider.generate_structured.assert_awaited_once()
        _args, kwargs = provider.generate_structured.await_args
        system_prompt = kwargs.get("system_prompt", "")
        assert "software architect" in system_prompt.lower()

    async def test_provider_error_propagates(self):
        clusters = {"cluster_1": ["src/auth/login.py"]}
        provider = AsyncMock()
        provider.generate_structured.side_effect = LLMError("LLM call failed")

        with pytest.raises(LLMError, match="LLM call failed"):
            await label_clusters(clusters, provider)

    async def test_malformed_response_raises_llm_error(self):
        clusters = {"cluster_1": ["src/auth/login.py"]}
        provider = AsyncMock()
        provider.generate_structured.side_effect = LLMError(
            "Failed to parse LLM response as ClusterLabel",
        )

        with pytest.raises(LLMError, match="ClusterLabel"):
            await label_clusters(clusters, provider)

    async def test_multiple_clusters_all_labeled(self):
        clusters = {
            "cluster_1": ["src/auth/login.py"],
            "cluster_2": ["src/db/models.py"],
            "cluster_3": ["src/api/routes.py"],
        }
        provider = AsyncMock()
        provider.generate_structured.side_effect = [
            ClusterLabel(name="Auth", description="Auth subsystem", reasoning="R1"),
            ClusterLabel(name="Database", description="Data models", reasoning="R2"),
            ClusterLabel(name="API", description="API routes", reasoning="R3"),
        ]

        result = await label_clusters(clusters, provider)

        assert len(result) == 3
        assert [lc.name for lc in result] == ["Auth", "Database", "API"]
        assert provider.generate_structured.await_count == 3


class TestClusterLabelConstraints:
    """ClusterLabel constraint fields."""

    def test_construct_with_constraints(self):
        """Should accept constraint fields."""
        label = ClusterLabel(
            name="Auth Module",
            description="Handles user authentication",
            reasoning="Files are auth-related",
            async_only=True,
            no_blocking_io=True,
            forbidden_dependencies=["src/legacy/", "src/old/"],
            allowed_dependencies=["src/common/", "src/models/"],
        )
        assert label.async_only is True
        assert label.no_blocking_io is True
        assert label.forbidden_dependencies == ["src/legacy/", "src/old/"]
        assert label.allowed_dependencies == ["src/common/", "src/models/"]

    def test_constraints_default_to_false(self):
        """Constraint fields should default to safe values."""
        label = ClusterLabel(
            name="Auth",
            description="Auth subsystem",
            reasoning="R",
        )
        assert label.async_only is False
        assert label.no_blocking_io is False
        assert label.forbidden_dependencies == []
        assert label.allowed_dependencies == []


class TestLabeledClusterConstraints:
    """LabeledCluster should carry constraint data."""

    def test_labeled_cluster_carries_constraints(self):
        """Should store constraint fields from LLM response."""
        lc = LabeledCluster(
            cluster_id="cluster_1",
            files=["src/auth/login.py"],
            name="Auth Module",
            description="Handles authentication",
            reasoning="All auth-related files",
            async_only=True,
            forbidden_dependencies=["src/legacy/"],
        )
        assert lc.async_only is True
        assert lc.no_blocking_io is False
        assert lc.forbidden_dependencies == ["src/legacy/"]
        assert lc.allowed_dependencies == []


class TestLabelClustersConstraints:
    """label_clusters constraint propagation."""

    async def test_constraints_from_llm_are_passed_to_labeled_cluster(self):
        """Constraints from LLM response should flow into LabeledCluster."""
        clusters = {"cluster_1": ["src/auth/login.py"]}
        provider = AsyncMock()
        provider.generate_structured.return_value = ClusterLabel(
            name="Auth",
            description="Auth subsystem",
            reasoning="R",
            async_only=True,
            forbidden_dependencies=["src/legacy/"],
        )

        result = await label_clusters(clusters, provider)

        assert len(result) == 1
        assert result[0].async_only is True
        assert result[0].forbidden_dependencies == ["src/legacy/"]
        assert result[0].no_blocking_io is False
        assert result[0].allowed_dependencies == []

    async def test_system_prompt_mentions_constraints(self):
        """System prompt should ask LLM to infer constraints."""
        clusters = {"cluster_1": ["src/auth/login.py"]}
        provider = AsyncMock()
        provider.generate_structured.return_value = ClusterLabel(
            name="X",
            description="Y",
            reasoning="Z",
        )

        await label_clusters(clusters, provider)

        _args, kwargs = provider.generate_structured.await_args
        system_prompt = kwargs.get("system_prompt", "")
        assert "constraint" in system_prompt.lower() or "async" in system_prompt.lower()
