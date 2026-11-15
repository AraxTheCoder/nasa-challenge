"""T145: the commit is read from .git without a git binary."""
from pathlib import Path

from server import version

SHA_A = "a" * 40
SHA_B = "b" * 40


def _repo(tmp_path: Path) -> Path:
    (tmp_path / ".git" / "refs" / "heads").mkdir(parents=True)
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    return tmp_path


def test_loose_ref(tmp_path):
    repo = _repo(tmp_path)
    (repo / ".git" / "refs" / "heads" / "main").write_text(SHA_A + "\n")
    assert version.commit(repo) == SHA_A


def test_packed_ref(tmp_path):
    repo = _repo(tmp_path)
    (repo / ".git" / "packed-refs").write_text(f"# pack-refs with: peeled\n{SHA_B} refs/heads/main\n")
    assert version.commit(repo) == SHA_B


def test_detached_head(tmp_path):
    repo = _repo(tmp_path)
    (repo / ".git" / "HEAD").write_text(SHA_A + "\n")
    assert version.commit(repo) == SHA_A


def test_worktree(tmp_path):
    main = _repo(tmp_path / "main")
    (main / ".git" / "refs" / "heads" / "topic").write_text(SHA_B + "\n")
    wt_git = main / ".git" / "worktrees" / "wt"
    wt_git.mkdir(parents=True)
    (wt_git / "HEAD").write_text("ref: refs/heads/topic\n")
    (wt_git / "commondir").write_text("../..\n")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {wt_git}\n")
    assert version.commit(wt) == SHA_B


def test_no_repo(tmp_path):
    assert version.commit(tmp_path) is None


def test_health_reports_the_commit(tmp_path):
    from fastapi.testclient import TestClient
    from server.app import create_app
    body = TestClient(create_app(tmp_path / "targets", fixture=True)).get("/api/health").json()
    assert body["ok"] is True
    assert body["commit"] == version.commit()
    assert body["api_commit"] == version.STARTED
