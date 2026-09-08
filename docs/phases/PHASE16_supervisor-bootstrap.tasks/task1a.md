---
task: 1a
status: done
---

## Task 1a: RED — `tasks`가 워크트리 cwd의 페이즈 문서를 우선 해석하는 계약 동결 (5건)
- **에이전트**: 오케스트레이터 직접 (PITFALLS 14 — 회귀 테스트는 오케스트레이터가 작성·동결)
- **대상 파일**: `tests/test_phase_tools.py` (기존 `Base`·`run_tool` 재사용, 파일 끝 `if __name__` 앞에 클래스 추가)
- **선행**: 없음
- **목표**: 아래 5개 테스트가 현재 구현에서 **1·2·3·5번 FAIL, 4번 PASS**로 실패를 확인하고 커밋(동결)된다.
- **재사용**: 그대로 재사용 `tests/test_phase_tools.py:Base`(격리 저장소·레지스트리·`git()`), `run_tool`. 새 헬퍼 금지.
- **실패 테스트**: 아래 클래스 전체
- **필수 규칙**: 커밋은 이 파일만(`git add tests/test_phase_tools.py`), 메시지 `test(scripts): tasks 워크트리 문서 우선 해석 계약을 동결 — RED 4 + 폴백 가드 1 (오케스트레이터)`. 커밋 메시지에 heredoc·명령치환 금지.
- **완료 조건**: `python3 -m unittest tests.test_phase_tools.WorktreeTasksTest -v; echo "exit=$?"` → `Ran 5 tests`, FAIL 4·OK 1, exit=1. 기존 `TasksTest` 6건은 여전히 OK.

```python
class WorktreeTasksTest(Base):
    """Phase 16 RED — KF-13: tasks 가 워크트리 cwd 의 페이즈 문서를 우선 해석한다."""

    def seed_worktree_tasks(self):
        self.init_registry()
        self.wt = self.root / ".claude" / "worktrees" / "phase8-x"
        self.git("worktree", "add", "-b", "feature/phase8-x", str(self.wt), "develop")
        docs = self.wt / "DOCs"
        (docs / "PHASE8_x.md").write_text("---\nphase: 8\nstatus: in-progress\n---\n")
        tdir = docs / "PHASE8_x.tasks"
        tdir.mkdir()
        (tdir / "task1.md").write_text("---\ntask: 1\nstatus: done\n---\n\n# Task 1: 첫\n")
        (tdir / "task2.md").write_text("---\ntask: 2\nstatus: pending\n---\n\n# Task 2: 둘\n")
        return tdir

    def test_tasks_next_from_worktree_cwd_finds_worktree_tasks(self):
        self.seed_worktree_tasks()
        r = run_tool(["tasks", "8", "--next"], self.wt, self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "2")

    def test_tasks_json_from_worktree_reports_docs_root_and_relative_path(self):
        self.seed_worktree_tasks()
        r = run_tool(["tasks", "8"], self.wt, self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(Path(data["docs_root"]).resolve(), self.wt.resolve())
        by_n = {t["task"]: t for t in data["tasks"]}
        self.assertEqual(by_n[2]["path"], "DOCs/PHASE8_x.tasks/task2.md")

    def test_tasks_set_from_worktree_writes_worktree_file(self):
        tdir = self.seed_worktree_tasks()
        r = run_tool(["tasks", "8", "--set", "2=in-progress"], self.wt, self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("status: in-progress", (tdir / "task2.md").read_text())
        # 메인 체크아웃에는 같은 경로가 생기지 않는다
        self.assertFalse((self.root / "DOCs" / "PHASE8_x.tasks").exists())

    def test_tasks_from_main_cwd_without_docs_is_explicit_error(self):
        self.seed_worktree_tasks()
        r = run_tool(["tasks", "8"], self.root, self.env)
        self.assertEqual(r.returncode, 2)
        self.assertIn("PHASE8_*.tasks", r.stderr)
        self.assertEqual(r.stdout.strip(), "")

    def test_tasks_from_worktree_falls_back_to_main_when_absent(self):
        # 병합 후: 문서는 메인에만 있고 워크트리 브랜치에는 없다 — 메인 루트로 폴백해야 한다
        self.init_registry()
        tasks_dir = self.root / "DOCs" / "PHASE7_seed.tasks"
        tasks_dir.mkdir(exist_ok=True)
        (tasks_dir / "task1.md").write_text("---\ntask: 1\nstatus: pending\n---\n\n# Task 1: 메인\n")
        wt = self.root / ".claude" / "worktrees" / "phase9-y"
        self.git("worktree", "add", "-b", "feature/phase9-y", str(wt), "develop")
        r = run_tool(["tasks", "7", "--next"], wt, self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "1")
        data = json.loads(run_tool(["tasks", "7"], wt, self.env).stdout)
        self.assertEqual(Path(data["docs_root"]).resolve(), self.root.resolve())
```

> `json`·`Path`는 파일 상단에 이미 import돼 있다. `seed_tasks`는 `TasksTest` 소속이라 여기서 쓰지 않는다.
