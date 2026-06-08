"""Tests for the MCP tool layer (the public surface in knowledge/tools.py).

These call tools through the real FastMCP instance so wrapper bugs (argument
passing, file-write branches, the git-backed diff) are caught.
"""

from __future__ import annotations

import asyncio
import subprocess

import pytest

from excalidraw_mcp import server


def call(name: str, args: dict) -> str:
    """Invoke a registered MCP tool and return its text result."""

    async def _run():
        res = await server.mcp.call_tool(name, args)
        content = getattr(res, "content", None)
        if isinstance(content, list) and content:
            return getattr(content[0], "text", str(content[0]))
        return str(getattr(res, "data", res))

    return asyncio.run(_run())


@pytest.fixture
def graph_path(tmp_path):
    p = str(tmp_path / "arch.md")
    call("kg_init", {"graph_path": p, "title": "T", "direction": "TD"})
    call("kg_add_service", {"id": "a", "label": "A", "graph_path": p})
    call("kg_add_service", {"id": "b", "label": "B", "domain": "core", "graph_path": p})
    call("kg_link", {"from_id": "a", "to_id": "b", "label": "calls", "graph_path": p})
    return p


def test_build_and_query_flow(graph_path):
    assert "Impact analysis for 'b'" in call(
        "whats_connected_to", {"service_id": "b", "graph_path": graph_path}
    )
    assert call("kg_path", {"from_id": "a", "to_id": "b", "graph_path": graph_path}) == "a -> b"
    assert "no issues" in call("kg_lint", {"graph_path": graph_path}).lower()


def test_link_to_missing_service_reports_error(graph_path):
    msg = call("kg_link", {"from_id": "a", "to_id": "ghost", "graph_path": graph_path})
    assert "Error" in msg


def test_render_tools(graph_path, tmp_path):
    out = str(tmp_path / "o.excalidraw")
    assert "2 node" in call("kg_render", {"output_path": out, "graph_path": graph_path})
    assert "1 node" in call(
        "kg_render_view", {"node_ids": ["a"], "output_path": out, "graph_path": graph_path}
    )
    assert "node" in call(
        "kg_render_domain", {"domain": "core", "output_path": out, "graph_path": graph_path}
    )


def test_export_to_stdout_and_file(graph_path, tmp_path):
    assert call("kg_export", {"format": "mermaid", "graph_path": graph_path}).startswith(
        "flowchart"
    )
    f = str(tmp_path / "g.dot")
    assert "Exported dot" in call(
        "kg_export", {"format": "dot", "output_path": f, "graph_path": graph_path}
    )
    assert "digraph" in open(f).read()


def test_export_bad_format(graph_path):
    assert "unsupported" in call("kg_export", {"format": "svg", "graph_path": graph_path})


def test_onboarding_doc(graph_path):
    assert "Onboarding Guide" in call("kg_onboarding_doc", {"graph_path": graph_path})


def test_remove_service(graph_path):
    msg = call("kg_remove_service", {"id": "b", "graph_path": graph_path})
    assert "Removed" in msg
    assert "not found" in call(
        "kg_path", {"from_id": "a", "to_id": "b", "graph_path": graph_path}
    ).lower() or "No dependency" in call(
        "kg_path", {"from_id": "a", "to_id": "b", "graph_path": graph_path}
    )


def test_kg_diff_against_git(tmp_path):
    """kg_diff compares the working copy to a committed git version."""
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }

    def git(*args):
        subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
            env={**__import__("os").environ, **env},
        )

    git("init")
    p = str(repo / "arch.md")
    call("kg_init", {"graph_path": p, "title": "Sys"})
    call("kg_add_service", {"id": "a", "label": "A", "graph_path": p})
    git("add", ".")
    git("commit", "-m", "v1")

    # change after the commit
    call("kg_add_service", {"id": "b", "label": "B", "graph_path": p})
    call("kg_link", {"from_id": "a", "to_id": "b", "graph_path": p})

    out = call("kg_diff", {"ref": "HEAD", "graph_path": p})
    assert "+ service b" in out
    assert "+ dependency a -> b" in out


def test_kg_diff_outside_git_reports_error(tmp_path):
    p = str(tmp_path / "arch.md")
    call("kg_init", {"graph_path": p})
    out = call("kg_diff", {"ref": "HEAD", "graph_path": p})
    assert "Error" in out or "No architectural changes" in out
