"""Semantic Labeling - Generate human-readable names for file clusters.

Uses an LLM provider to analyze file clusters and produce concise,
meaningful names and descriptions for each logical subsystem.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

import asyncio

from archai.inference.llm.base import LLMProvider

CLUSTER_SYSTEM_PROMPT = (
    "You are a software architect analyzing a codebase. "
    "Given a set of files that form a logical subsystem, "
    "name it and describe its purpose concisely. "
    "Also infer architectural constraints for this subsystem:\n"
    "- async_only: Whether this subsystem REQUIRES async/await patterns\n"
    "- no_blocking_io: Whether this subsystem must avoid blocking I/O calls\n"
    "- forbidden_dependencies: List of modules/packages this subsystem must NOT import\n"
    "- allowed_dependencies: List of modules/packages this subsystem is ALLOWED to import\n"
    "Set boolean fields to true only if there's clear evidence in the files."
)

CLUSTER_USER_PROMPT = (
    'Cluster "{cluster_id}" contains the following files:\n'
    "{files_list}\n\n"
    "Analyze these files and determine what logical subsystem they form. "
    "Provide a concise name for this subsystem and a brief description "
    "of its purpose, along with your reasoning."
)


class ClusterLabel(BaseModel):
    """Structured response expected from the LLM for a single cluster."""

    name: str
    description: str
    reasoning: str
    async_only: bool = False
    no_blocking_io: bool = False
    forbidden_dependencies: list[str] = Field(default_factory=list)
    allowed_dependencies: list[str] = Field(default_factory=list)


class LabeledCluster(BaseModel):
    """A cluster enriched with an LLM-generated name and description."""

    cluster_id: str
    files: list[str]
    name: str
    description: str
    reasoning: str
    async_only: bool = False
    no_blocking_io: bool = False
    forbidden_dependencies: list[str] = Field(default_factory=list)
    allowed_dependencies: list[str] = Field(default_factory=list)


def _build_cluster_prompt(cluster_id: str, files: list[str]) -> str:
    """Build the user prompt for a single cluster."""
    files_list = "\n".join(f"- {f}" for f in files)
    return CLUSTER_USER_PROMPT.format(cluster_id=cluster_id, files_list=files_list)


async def label_clusters(
    clusters: dict[str, list[str]],
    provider: LLMProvider,
) -> list[LabeledCluster]:
    """Label each cluster using the LLM provider.

    Args:
        clusters: dict mapping cluster_id -> list of file paths
        provider: LLM provider instance

    Returns:
        list of LabeledCluster with LLM-generated names/descriptions

    Raises:
        LLMError: If the LLM call fails or returns invalid data
    """
    if not clusters:
        return []

    sem = asyncio.Semaphore(5)

    async def _label_one(cluster_id: str, files: list[str]) -> LabeledCluster:
        async with sem:
            prompt = _build_cluster_prompt(cluster_id, files)
            label = await provider.generate_structured(
                prompt=prompt,
                response_model=ClusterLabel,
                system_prompt=CLUSTER_SYSTEM_PROMPT,
            )
            return LabeledCluster(
                cluster_id=cluster_id,
                files=files,
                name=label.name,
                description=label.description,
                reasoning=label.reasoning,
                async_only=label.async_only,
                no_blocking_io=label.no_blocking_io,
                forbidden_dependencies=label.forbidden_dependencies,
                allowed_dependencies=label.allowed_dependencies,
            )

    tasks = [_label_one(cid, fls) for cid, fls in clusters.items()]
    labeled = await asyncio.gather(*tasks)
    return labeled
