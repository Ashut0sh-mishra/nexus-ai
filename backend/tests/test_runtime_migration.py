"""Phase 6A — migration integrity test for runtime tables.

Conftest-free, AST-based. Verifies that the Alembic migration for the dynamic
agent runtime exists, declares the right revision chain, and creates the three
expected tables (`agent_runs`, `agent_steps`, `artifacts`) with their key
indexes — all without importing alembic or executing any SQL.

Run::

    python -m pytest --noconftest -p no:cacheprovider \
        backend/tests/test_runtime_migration.py -v
"""
from __future__ import annotations

import ast
from pathlib import Path


_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "database"
    / "migrations"
    / "versions"
    / "0002_agent_runtime.py"
)


def _load_module() -> ast.Module:
    return ast.parse(_MIGRATION.read_text(encoding="utf-8"), filename=str(_MIGRATION))


def _module_assigns(tree: ast.Module) -> dict[str, ast.AST]:
    out: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            target = node.targets[0] if isinstance(node, ast.Assign) else node.target
            if isinstance(target, ast.Name) and node.value is not None:
                out[target.id] = node.value
    return out


def _calls_in_function(tree: ast.Module, name: str) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    calls.append(sub)
    return calls


def _string_arg(call: ast.Call, idx: int) -> str | None:
    if idx >= len(call.args):
        return None
    arg = call.args[idx]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    return None


def _is_op_call(call: ast.Call, fn: str) -> bool:
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == fn
        and isinstance(func.value, ast.Name)
        and func.value.id == "op"
    )


def test_migration_file_exists() -> None:
    assert _MIGRATION.exists(), f"missing migration: {_MIGRATION}"


def test_migration_revision_chain() -> None:
    tree = _load_module()
    assigns = _module_assigns(tree)
    rev = assigns.get("revision")
    down = assigns.get("down_revision")
    assert isinstance(rev, ast.Constant) and rev.value == "0002_agent_runtime"
    assert isinstance(down, ast.Constant) and down.value == "0001_initial"


def test_upgrade_creates_runtime_tables() -> None:
    tree = _load_module()
    upgrade_calls = _calls_in_function(tree, "upgrade")
    created = {
        _string_arg(c, 0)
        for c in upgrade_calls
        if _is_op_call(c, "create_table")
    }
    for expected in ("agent_runs", "agent_steps", "artifacts"):
        assert expected in created, f"upgrade() must create_table({expected!r})"


def test_upgrade_creates_required_indexes() -> None:
    tree = _load_module()
    upgrade_calls = _calls_in_function(tree, "upgrade")
    indexes: set[tuple[str, str]] = set()
    for c in upgrade_calls:
        if _is_op_call(c, "create_index"):
            ix = _string_arg(c, 0)
            tbl = _string_arg(c, 1)
            if ix and tbl:
                indexes.add((tbl, ix))
    expected = {
        ("agent_runs", "ix_agent_runs_task_id"),
        ("agent_runs", "ix_agent_runs_user_id"),
        ("agent_runs", "ix_agent_runs_status"),
        ("agent_steps", "ix_agent_steps_run_id"),
        ("artifacts", "ix_artifacts_run_id"),
        ("artifacts", "ix_artifacts_task_id"),
        ("artifacts", "ix_artifacts_artifact_type"),
    }
    missing = expected - indexes
    assert not missing, f"missing indexes in upgrade(): {sorted(missing)}"


def test_downgrade_drops_runtime_tables() -> None:
    tree = _load_module()
    downgrade_calls = _calls_in_function(tree, "downgrade")
    dropped = {
        _string_arg(c, 0)
        for c in downgrade_calls
        if _is_op_call(c, "drop_table")
    }
    for expected in ("agent_runs", "agent_steps", "artifacts"):
        assert expected in dropped, f"downgrade() must drop_table({expected!r})"
