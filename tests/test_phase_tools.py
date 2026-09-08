"""phase-tools.py 테스트 — 임시 git 저장소 + ORCH_STATE_DIR 격리."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "core/scripts/phase-tools.py"


def run_tool(args, cwd, env, check=False):
    r = subprocess.run(
        [sys.executable, str(TOOLS), *args],
        cwd=cwd, env=env, capture_output=True, text=True,
        timeout=60,
    )
    if check and r.returncode != 0:
        raise AssertionError(f"phase-tools {args} 실패: {r.stdout}\n{r.stderr}")
    return r


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "proj"
        self.root.mkdir()
        self.env = {
            **os.environ,
            "ORCH_STATE_DIR": str(Path(self.tmp.name) / "state"),
        }
        subprocess.run(
            ["git", "init", "-b", "develop", str(self.root)],
            check=True, capture_output=True, timeout=60,
        )
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        (self.root / "DOCs").mkdir()
        (self.root / "DOCs" / "PHASE7_seed.md").write_text(
            "---\nphase: 7\nstatus: done\n---\n"
        )
        (self.root / "a.txt").write_text("a\n")
        self.git("add", ".")
        self.git("commit", "-m", "init")

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            check=True, capture_output=True, text=True, timeout=60,
        )

    def init_registry(self):
        run_tool(
            ["init", "--default-branch", "develop", "--docs-dir", "DOCs"],
            self.root, self.env, check=True,
        )

    def registry(self):
        p = Path(self.env["ORCH_STATE_DIR"]) / "registry" / "proj.json"
        return json.loads(p.read_text())


class TestInit(Base):
    # Phase 8 RED (오케스트레이터 작성·동결 — 위임 수정 금지)
    def test_init_default_docs_dir_is_docs_phases(self):
        phases = self.root / "docs" / "phases"
        phases.mkdir(parents=True)
        (phases / "PHASE3_seed.md").write_text("---\nphase: 3\nstatus: done\n---\n")
        run_tool(["init", "--default-branch", "develop"], self.root, self.env, check=True)
        reg = self.registry()
        self.assertEqual(reg["docs_dir"], "docs/phases")
        self.assertEqual(reg["next_phase"], 4)  # docs/phases의 PHASE3 스캔 → 4 (DOCs의 7은 무시)

    def test_init_default_falls_back_to_DOCs_when_no_docs_phases(self):
        # 미마이그레이션 프로젝트(DOCs만 존재)에서 --docs-dir 생략 시
        # 존재하지 않는 docs/phases로 phase 카운터가 리셋되면 안 된다
        run_tool(["init", "--default-branch", "develop"], self.root, self.env, check=True)
        reg = self.registry()
        self.assertEqual(reg["docs_dir"], "DOCs")
        self.assertEqual(reg["next_phase"], 8)

    def test_init_default_ignores_empty_docs_phases(self):
        # docs/phases가 존재하지만 비어있으면 실문서가 있는 DOCs를 쓴다
        (self.root / "docs" / "phases").mkdir(parents=True)
        run_tool(["init", "--default-branch", "develop"], self.root, self.env, check=True)
        reg = self.registry()
        self.assertEqual(reg["docs_dir"], "DOCs")
        self.assertEqual(reg["next_phase"], 8)

    def test_init_default_ignores_scaffolding_only_docs_phases(self):
        # docs/phases에 PHASE 문서가 아닌 스텁(.md)만 있으면 DOCs를 쓴다
        scaffold = self.root / "docs" / "phases"
        (scaffold / "TEMPLATES").mkdir(parents=True)
        (scaffold / "TEMPLATES" / "CURRENT_TASK_template.md").write_text("stub")
        (scaffold / "specs").mkdir()
        (scaffold / "specs" / "design.md").write_text("stub")
        run_tool(["init", "--default-branch", "develop"], self.root, self.env, check=True)
        reg = self.registry()
        self.assertEqual(reg["docs_dir"], "DOCs")
        self.assertEqual(reg["next_phase"], 8)

    def test_init_picks_docs_phases_when_only_reviews_docs(self):
        # 실문서가 docs/phases/reviews/ 하위에만 있어도 docs-index와 동일하게
        # docs/phases를 선택해야 한다 (스크립트 간 판정 불일치 금지)
        reviews = self.root / "docs" / "phases" / "reviews"
        reviews.mkdir(parents=True)
        (reviews / "PHASE12_REVIEW.md").write_text("---\nphase: 12\nstatus: done\n---\n")
        self.git("add", ".")
        self.git("commit", "-m", "reviews")
        run_tool(["init", "--default-branch", "develop"], self.root, self.env, check=True)
        reg = self.registry()
        self.assertEqual(reg["docs_dir"], "docs/phases")
        self.assertEqual(reg["next_phase"], 13)

    def test_reseed_without_docs_dir_preserves_registry_value(self):
        # 운영 중 레지스트리의 docs_dir를 --reseed가 기본값으로 덮어쓰면 안 된다
        self.init_registry()  # docs_dir=DOCs 명시
        (self.root / "docs" / "phases").mkdir(parents=True)
        (self.root / "docs" / "phases" / "PHASE2_other.md").write_text(
            "---\nphase: 2\nstatus: done\n---\n"
        )
        run_tool(
            ["init", "--default-branch", "develop", "--reseed"],
            self.root, self.env, check=True,
        )
        reg = self.registry()
        self.assertEqual(reg["docs_dir"], "DOCs")
        self.assertEqual(reg["next_phase"], 8)

    def test_init_seeds_next_phase_from_docs(self):
        self.init_registry()
        reg = self.registry()
        self.assertEqual(reg["next_phase"], 8)  # DOCs에 PHASE7 → 다음 8
        self.assertEqual(reg["default_branch"], "develop")
        self.assertEqual(reg["docs_dir"], "DOCs")
        self.assertEqual(reg["active"], [])

    def test_init_scans_worktree_docs_too(self):
        # 다른 세션 워크트리에만 존재하는 지시서(브랜치 미병합)도 시드에 반영돼야 한다
        self.init_registry()
        run_tool(["claim", "other"], self.root, self.env, check=True)
        wt = self.root / ".claude/worktrees/phase8-other"
        # 워크트리 안에서 번호가 리네임된 상황 재현 (166→167 실측 사례)
        (wt / "DOCs" / "PHASE12_renamed.md").write_text("---\nstatus: in-progress\n---\n")
        run_tool(
            ["init", "--default-branch", "develop", "--docs-dir", "DOCs", "--reseed"],
            self.root, self.env, check=True,
        )
        self.assertEqual(self.registry()["next_phase"], 13)

    def test_init_is_idempotent_without_reseed(self):
        self.init_registry()
        (self.root / "DOCs" / "PHASE20_x.md").write_text("---\nstatus: done\n---\n")
        self.init_registry()  # reseed 없으면 기존 값 유지
        self.assertEqual(self.registry()["next_phase"], 8)


class TestClaim(Base):
    def test_claim_allocates_number_worktree_branch(self):
        self.init_registry()
        r = run_tool(["claim", "my-feature"], self.root, self.env, check=True)
        self.assertIn("PHASE=8", r.stdout)
        self.assertIn("BRANCH=feature/phase8-my-feature", r.stdout)
        wt = self.root / ".claude/worktrees/phase8-my-feature"
        self.assertTrue(wt.is_dir())
        head = subprocess.run(
            ["git", "-C", str(wt), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True, timeout=60,
        ).stdout.strip()
        self.assertEqual(head, "feature/phase8-my-feature")
        reg = self.registry()
        self.assertEqual(reg["next_phase"], 9)
        self.assertEqual(reg["active"][0]["phase"], 8)

    def test_claim_from_inside_worktree_uses_main_root(self):
        self.init_registry()
        run_tool(["claim", "first"], self.root, self.env, check=True)
        wt = self.root / ".claude/worktrees/phase8-first"
        r = run_tool(["claim", "second"], wt, self.env, check=True)
        self.assertIn("PHASE=9", r.stdout)
        self.assertTrue((self.root / ".claude/worktrees/phase9-second").is_dir())

    def test_parallel_claims_get_distinct_numbers(self):
        self.init_registry()
        procs = [
            subprocess.Popen(
                [sys.executable, str(TOOLS), "claim", f"par-{i}"],
                cwd=self.root, env=self.env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            for i in range(2)
        ]
        outs = [p.communicate(timeout=60)[0] for p in procs]
        self.assertTrue(all(p.returncode == 0 for p in procs))
        nums = sorted(
            int(line.split("=")[1])
            for out in outs for line in out.splitlines()
            if line.startswith("PHASE=")
        )
        self.assertEqual(nums, [8, 9])


class TestClose(Base):
    def _claim_and_finish(self, slug="feat-x", merge=True):
        """claim → 워크트리에서 커밋 + 지시서 status: done → (선택) develop에 병합."""
        self.init_registry()
        run_tool(["claim", slug], self.root, self.env, check=True)
        wt = self.root / f".claude/worktrees/phase8-{slug}"
        (wt / "DOCs" / f"PHASE8_{slug}.md").write_text(
            "---\nphase: 8\nstatus: done\n---\n"
        )
        (wt / "b.txt").write_text("b\n")
        subprocess.run(["git", "-C", str(wt), "add", "."],
                       check=True, capture_output=True, timeout=60)
        subprocess.run(["git", "-C", str(wt), "commit", "-m", "work"],
                       check=True, capture_output=True, timeout=60)
        if merge:
            self.git("merge", "--no-ff", f"feature/phase8-{slug}", "-m", "merge")
        return wt

    def test_close_removes_worktree_branch_and_entry(self):
        wt = self._claim_and_finish()
        r = run_tool(["close", "8"], self.root, self.env, check=True)
        self.assertFalse(wt.exists())
        branches = self.git("branch").stdout
        self.assertNotIn("feature/phase8-feat-x", branches)
        self.assertEqual(self.registry()["active"], [])
        self.assertIn("phase 8 마감", r.stdout)

    def test_close_refuses_when_doc_not_done(self):
        wt = self._claim_and_finish(merge=False)
        doc = wt / "DOCs" / "PHASE8_feat-x.md"
        doc.write_text("---\nphase: 8\nstatus: in-progress\n---\n")
        subprocess.run(["git", "-C", str(wt), "commit", "-am", "wip"],
                       check=True, capture_output=True, timeout=60)
        r = run_tool(["close", "8"], self.root, self.env)
        self.assertEqual(r.returncode, 2)
        self.assertTrue(wt.exists())  # 아무것도 지우지 않음

    def test_close_refuses_in_progress_when_reviews_only_content(self):
        # docs_dir 판정이 reviews/ 하위 실문서를 인지해 docs/phases로 결정되고,
        # 그 안의 in-progress 지시서가 --force 없는 close를 막아야 한다
        reviews = self.root / "docs" / "phases" / "reviews"
        reviews.mkdir(parents=True)
        (reviews / "PHASE12_REVIEW.md").write_text("---\nphase: 12\nstatus: done\n---\n")
        self.git("add", ".")
        self.git("commit", "-m", "reviews")
        run_tool(["init", "--default-branch", "develop"], self.root, self.env, check=True)
        run_tool(["claim", "gap"], self.root, self.env, check=True)
        entry = self.registry()["active"][0]
        self.assertEqual(entry["phase"], 13)  # reviews/의 PHASE12 인지 → 13 발급
        wt = self.root / entry["worktree"]
        doc = wt / "docs" / "phases" / "PHASE13_gap.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("---\nphase: 13\nstatus: in-progress\n---\n")
        subprocess.run(["git", "-C", str(wt), "add", "."],
                       check=True, capture_output=True, timeout=60)
        subprocess.run(["git", "-C", str(wt), "commit", "-m", "wip"],
                       check=True, capture_output=True, timeout=60)
        r = run_tool(["close", "13"], self.root, self.env)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertTrue(wt.exists())  # 아무것도 지우지 않음

    def test_close_keeps_dirty_worktree_but_clears_entry_with_force(self):
        wt = self._claim_and_finish()
        (wt / "dirty.txt").write_text("uncommitted\n")
        r = run_tool(["close", "8", "--force"], self.root, self.env, check=True)
        self.assertTrue(wt.exists())  # dirty 워크트리는 보존
        self.assertIn("dirty", r.stdout)
        self.assertEqual(self.registry()["active"], [])

    def test_close_archives_orchestrate_logs(self):
        self._claim_and_finish()
        orch = self.root / ".orchestrate"
        orch.mkdir()
        (orch / "p8-task1.log").write_text("log\n")
        run_tool(["close", "8"], self.root, self.env, check=True)
        self.assertFalse((orch / "p8-task1.log").exists())
        self.assertTrue((orch / "archive/phase8/p8-task1.log").exists())

    def _merge_into_integration(self, slug="integration"):
        wt = self._claim_and_finish(slug, merge=False)
        self.git("checkout", "-b", "feat/integration")
        self.git("merge", "--no-ff", f"feature/phase8-{slug}", "-m", "merge")
        return wt

    def test_close_removes_worktree_merged_into_current_integration_branch(self):
        wt = self._merge_into_integration()
        run_tool(["close", "8"], self.root, self.env, check=True)
        self.assertFalse(wt.exists())
        self.assertEqual(self.registry()["active"], [])

    def test_close_target_uses_only_specified_ref(self):
        wt = self._merge_into_integration("target-only")
        run_tool(["close", "8", "--target", "develop"],
                 self.root, self.env, check=True)
        self.assertTrue(wt.exists())
        self.assertEqual(self.registry()["active"], [])

    def test_close_keeps_unmerged_worktree_when_main_uses_same_branch(self):
        wt = self._claim_and_finish("self-reference", merge=False)
        self.git("checkout", "--ignore-other-worktrees",
                 "feature/phase8-self-reference")
        r = run_tool(["close", "8"], self.root, self.env, check=True)
        self.assertTrue(wt.exists())
        self.assertIn("워크트리 미병합 — 보존", r.stdout)

    def test_close_rejects_missing_target_without_removing_worktree(self):
        wt = self._claim_and_finish("invalid-target", merge=False)
        r = run_tool(["close", "8", "--target", "missing-target"],
                     self.root, self.env)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--target ref 를 찾을 수 없음: missing-target", r.stderr)
        self.assertTrue(wt.exists())


class TestJanitor(Base):
    def test_janitor_removes_merged_clean_worktree_and_branch(self):
        self.init_registry()
        run_tool(["claim", "done-work"], self.root, self.env, check=True)
        wt = self.root / ".claude/worktrees/phase8-done-work"
        (wt / "b.txt").write_text("b\n")
        subprocess.run(["git", "-C", str(wt), "add", "."],
                       check=True, capture_output=True, timeout=60)
        subprocess.run(["git", "-C", str(wt), "commit", "-m", "work"],
                       check=True, capture_output=True, timeout=60)
        self.git("merge", "--no-ff", "feature/phase8-done-work", "-m", "merge")
        r = run_tool(["janitor"], self.root, self.env, check=True)
        self.assertFalse(wt.exists())
        self.assertNotIn("feature/phase8-done-work", self.git("branch").stdout)
        self.assertEqual(self.registry()["active"], [])
        self.assertIn("자동정리", r.stdout)

    def test_janitor_reports_dirty_worktree_without_touching(self):
        self.init_registry()
        run_tool(["claim", "wip"], self.root, self.env, check=True)
        wt = self.root / ".claude/worktrees/phase8-wip"
        (wt / "dirty.txt").write_text("x\n")
        r = run_tool(["janitor"], self.root, self.env, check=True)
        self.assertTrue(wt.exists())
        self.assertIn("확인필요", r.stdout)
        self.assertIn("phase8-wip", r.stdout)

    def test_janitor_reports_main_checkout_drift(self):
        self.init_registry()
        self.git("checkout", "-b", "integration/other")
        r = run_tool(["janitor"], self.root, self.env, check=True)
        self.assertIn("integration/other", r.stdout)

    def test_janitor_drops_ghost_entry_and_always_exit_zero(self):
        self.init_registry()
        run_tool(["claim", "ghost"], self.root, self.env, check=True)
        self.git("worktree", "remove", "--force",
                 ".claude/worktrees/phase8-ghost")
        r = run_tool(["janitor"], self.root, self.env)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.registry()["active"], [])

    def test_janitor_never_deletes_longlived_branches(self):
        # main/master/develop 같은 장수 브랜치는 병합돼 있어도 삭제 금지
        self.init_registry()
        self.git("branch", "main")      # develop과 동일 커밋 = merged 판정됨
        self.git("branch", "release")   # 임의 feature성 브랜치는 삭제 대상
        run_tool(["janitor"], self.root, self.env, check=True)
        branches = self.git("branch").stdout
        self.assertIn("main", branches)
        self.assertNotIn("release", branches)

    def test_janitor_archives_old_orchestrate_files(self):
        self.init_registry()
        orch = self.root / ".orchestrate"
        orch.mkdir()
        old = orch / "p3-task1.log"
        old.write_text("old\n")
        eight_days = 8 * 86400
        os.utime(old, (old.stat().st_atime - eight_days,
                       old.stat().st_mtime - eight_days))
        (orch / "fresh.log").write_text("new\n")
        run_tool(["janitor"], self.root, self.env, check=True)
        self.assertFalse(old.exists())
        self.assertTrue((orch / "archive/old/p3-task1.log").exists())
        self.assertTrue((orch / "fresh.log").exists())


class TasksTest(Base):
    """Phase 11 RED — task 상태 기계판독화 (`tasks` 서브커맨드)."""

    def seed_tasks(self):
        self.init_registry()
        tasks_dir = self.root / "DOCs" / "PHASE7_seed.tasks"
        tasks_dir.mkdir()
        (tasks_dir / "task1.md").write_text(
            "---\ntask: 1\nstatus: done\n---\n\n# Task 1: 첫 작업\n"
        )
        (tasks_dir / "task2.md").write_text(
            "---\ntask: 2\nstatus: pending\n---\n\n# Task 2: 둘째 작업\n"
        )
        (tasks_dir / "task3.md").write_text("# Task 3: frontmatter 없음\n")
        return tasks_dir

    def test_tasks_lists_status_as_json(self):
        self.seed_tasks()
        r = run_tool(["tasks", "7"], self.root, self.env, check=True)
        data = json.loads(r.stdout)
        self.assertEqual(data["phase"], 7)
        by_n = {t["task"]: t for t in data["tasks"]}
        self.assertEqual(by_n[1]["status"], "done")
        self.assertEqual(by_n[2]["status"], "pending")
        self.assertEqual(by_n[2]["title"], "Task 2: 둘째 작업")
        # frontmatter 없는 기존 파일은 무경고 디폴트 대입 없이 unknown으로 노출
        self.assertEqual(by_n[3]["status"], "unknown")
        self.assertFalse(data["complete"])

    def test_tasks_set_updates_frontmatter(self):
        tasks_dir = self.seed_tasks()
        run_tool(["tasks", "7", "--set", "2=in-progress"], self.root, self.env, check=True)
        self.assertIn("status: in-progress", (tasks_dir / "task2.md").read_text())
        # frontmatter 없던 파일에 --set 하면 frontmatter를 삽입한다
        run_tool(["tasks", "7", "--set", "3=pending"], self.root, self.env, check=True)
        text = (tasks_dir / "task3.md").read_text()
        self.assertTrue(text.startswith("---\n"))
        self.assertIn("task: 3", text)
        self.assertIn("status: pending", text)
        self.assertIn("# Task 3: frontmatter 없음", text)

    def test_tasks_set_rejects_unknown_status(self):
        self.seed_tasks()
        r = run_tool(["tasks", "7", "--set", "2=finished"], self.root, self.env)
        self.assertNotEqual(r.returncode, 0)

    def test_tasks_next_prefers_in_progress_then_lowest_pending(self):
        self.seed_tasks()
        r = run_tool(["tasks", "7", "--next"], self.root, self.env, check=True)
        self.assertEqual(r.stdout.strip(), "2")
        run_tool(["tasks", "7", "--set", "2=in-progress"], self.root, self.env, check=True)
        r = run_tool(["tasks", "7", "--next"], self.root, self.env, check=True)
        self.assertEqual(r.stdout.strip(), "2")

    def test_tasks_next_exits_1_when_no_runnable(self):
        # done·blocked·unknown만 남으면 실행 가능 task 없음 — 드라이버 루프 종료 조건
        self.seed_tasks()
        run_tool(["tasks", "7", "--set", "2=blocked"], self.root, self.env, check=True)
        r = run_tool(["tasks", "7", "--next"], self.root, self.env)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout.strip(), "")

    def test_tasks_complete_true_when_all_done_or_superseded(self):
        tasks_dir = self.seed_tasks()
        (tasks_dir / "task3.md").unlink()
        run_tool(["tasks", "7", "--set", "2=superseded"], self.root, self.env, check=True)
        data = json.loads(run_tool(["tasks", "7"], self.root, self.env, check=True).stdout)
        self.assertTrue(data["complete"])


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

    # Phase 16 RED 2차 (리뷰 반려 대응 — 폴백 무신호 🔴 2건 + 진단 정보 손실 🟠 1건)
    def test_fallback_to_main_is_announced_on_stderr(self):
        # 폴백은 정상 동작이지만 조용해선 안 된다 — stdout(기계 판독)은 그대로,
        # 어느 체크아웃에서 문서를 찾았는지는 stderr 로 알린다.
        self.init_registry()
        tasks_dir = self.root / "DOCs" / "PHASE7_seed.tasks"
        tasks_dir.mkdir(exist_ok=True)
        (tasks_dir / "task1.md").write_text("---\ntask: 1\nstatus: pending\n---\n\n# Task 1: 메인\n")
        wt = self.root / ".claude" / "worktrees" / "phase9-y"
        self.git("worktree", "add", "-b", "feature/phase9-y", str(wt), "develop")
        r = run_tool(["tasks", "7", "--next"], wt, self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "1")  # 기계 판독 계약 불변
        self.assertIn(str(self.root.resolve()), r.stderr)

    def test_set_reports_written_file_path(self):
        # --set 은 어느 파일을 고쳤는지 밝혀야 한다 (폴백 시 다른 체크아웃을 고칠 수 있으므로)
        tdir = self.seed_worktree_tasks()
        r = run_tool(["tasks", "8", "--set", "2=in-progress"], self.wt, self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(str((tdir / "task2.md").resolve()), r.stdout)

    def test_set_on_fallback_announces_and_reports_main_path(self):
        # 폴백 + --set 조합 (리뷰 지적 커버리지 갭): 워크트리 cwd 에서 --set 을 부르면
        # 메인 체크아웃 파일을 고치게 된다 — 통지(stderr)와 실제 쓴 경로(stdout)가 둘 다 나와야 한다.
        self.init_registry()
        tasks_dir = self.root / "DOCs" / "PHASE7_seed.tasks"
        tasks_dir.mkdir(exist_ok=True)
        (tasks_dir / "task1.md").write_text("---\ntask: 1\nstatus: pending\n---\n\n# Task 1: 메인\n")
        wt = self.root / ".claude" / "worktrees" / "phase9-w"
        self.git("worktree", "add", "-b", "feature/phase9-w", str(wt), "develop")
        r = run_tool(["tasks", "7", "--set", "1=in-progress"], wt, self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(str(self.root.resolve()), r.stderr)
        self.assertIn(str((tasks_dir / "task1.md").resolve()), r.stdout)
        self.assertIn("status: in-progress", (tasks_dir / "task1.md").read_text())

    def test_missing_tasks_message_names_the_worktree_root_it_searched(self):
        # 폴백 후 docs_root 를 root 로 덮어써 "탐색: X, X" 가 되면 어느 워크트리를
        # 뒤졌는지 사라진다 — 실제로 탐색한 워크트리 루트가 메시지에 남아야 한다.
        self.init_registry()
        wt = self.root / ".claude" / "worktrees" / "phase9-z"
        self.git("worktree", "add", "-b", "feature/phase9-z", str(wt), "develop")
        r = run_tool(["tasks", "9"], wt, self.env)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout.strip(), "")
        self.assertIn(str(wt.resolve()), r.stderr)


class RetryGuardTest(Base):
    """Phase 17 RED (task 3a) — `retry-guard` 무변경 재시도 차단 (A2).

    오케스트레이터 작성·동결 — 위임 수정 금지.
    감독 상태 파일은 격리 XDG 레이아웃(`<XDG_STATE_HOME>/orchestrate/supervisor/<project>.json`)에
    두고, 홈(`~/.claude`·`~/.local/state`)은 읽지도 쓰지도 않는다.
    """

    PROJECT = "proj"

    def setUp(self):
        super().setUp()
        self.home = Path(self.tmp.name) / "home"
        self.xdg_state = Path(self.tmp.name) / "xdg-state"
        self.state_file = (
            self.xdg_state / "orchestrate" / "supervisor" / f"{self.PROJECT}.json"
        )
        self.state_file.parent.mkdir(parents=True)
        self.home.mkdir()
        self.env = {
            **self.env,
            "HOME": str(self.home),
            "XDG_STATE_HOME": str(self.xdg_state),
        }

    def write_state(self, state):
        self.state_file.write_text(json.dumps(state, ensure_ascii=False))

    def read_state(self):
        return json.loads(self.state_file.read_text())

    def guard(self, *flags, phase="17", part="3"):
        return run_tool(
            ["retry-guard", phase, part, *flags, "--state", str(self.state_file)],
            self.root, self.env,
        )

    def record(self):
        r = self.guard("--record")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def test_check_blocks_when_worktree_is_unchanged_since_last_failure(self):
        # 1) 직전 실패 시점과 스냅샷이 같으면 재spawn 금지 신호를 내야 한다.
        self.write_state({"status": "running", "owner": {"pid": "1", "start_id": "x"}})
        self.record()
        state = self.read_state()
        # 기록은 상태 파일을 통째로 갈아엎지 않는다 (supervisor-state.sh 경유 = 기존 키 보존).
        self.assertEqual(state["status"], "running")
        self.assertEqual(state["owner"], {"pid": "1", "start_id": "x"})
        recorded = state["last_failure"]["worktree_hash"]
        self.assertRegex(recorded, r"^[0-9a-f]{64}$")
        self.assertFalse(self.state_file.is_symlink())

        r = self.guard("--check")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("retry_exhausted", r.stdout)

    def test_check_passes_when_tracked_file_changed(self):
        # 2) 추적 파일이 바뀌었으면 통과한다.
        self.write_state({"status": "running"})
        self.record()
        (self.root / "a.txt").write_text("a changed\n")
        r = self.guard("--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_check_passes_when_only_untracked_content_changed(self):
        # 3) untracked 파일만 바뀌어도 통과한다. 파일 목록(`git status -z -uall`)과
        #    추적 diff 가 동일한 채 **내용만** 바뀌는 경우까지 잡으려면 스냅샷이
        #    untracked 파일 내용의 sha256 을 포함해야 한다.
        self.write_state({"status": "running"})
        untracked = self.root / "u.txt"
        untracked.write_text("one\n")
        self.record()
        untracked.write_text("two\n")  # 이름·목록·추적 diff 는 그대로, 내용만 다르다
        r = self.guard("--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

        # 새 untracked 파일이 생긴 경우도 "변경 있음" 이다.
        self.record()
        (self.root / "v.txt").write_text("new\n")
        r = self.guard("--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_check_passes_when_no_failure_recorded(self):
        # 4) 첫 시도(직전 실패 기록 없음)는 통과한다. `--check` 는 기본 동작이다.
        self.write_state({"status": "idle"})
        r = self.guard("--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.guard()  # 플래그 생략 시 기본이 --check
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class RetryGuardHardeningTest(Base):
    """Phase 17 RED 2차 (task 3b 리뷰 1라운드 반영) — 오케스트레이터 작성·동결.

    1라운드에서 리뷰어 3인이 낸 🔴·🠠 중 테스트로 고정 가능한 것만 못박는다.
    """

    PROJECT = "proj"

    def setUp(self):
        super().setUp()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self.xdg_state = Path(self.tmp.name) / "xdg-state"
        self.state_file = (
            self.xdg_state / "orchestrate" / "supervisor" / f"{self.PROJECT}.json"
        )
        self.state_file.parent.mkdir(parents=True)
        self.state_file.write_text('{"status": "running"}')
        self.env = {
            **self.env,
            "HOME": str(self.home),
            "XDG_STATE_HOME": str(self.xdg_state),
        }
        self.sub = self.root / "sub"
        self.sub.mkdir()
        (self.sub / "s.txt").write_text("s\n")
        self.git("add", ".")
        self.git("commit", "-m", "sub")

    def read_state(self):
        return json.loads(self.state_file.read_text())

    def guard(self, *flags, cwd=None, phase="17", part="3", tool=None, timeout=60):
        return subprocess.run(
            [sys.executable, str(tool or TOOLS), "retry-guard", phase, part,
             *flags, "--state", str(self.state_file)],
            cwd=cwd or self.root, env=self.env, capture_output=True, text=True,
            timeout=timeout,
        )

    def record(self, **kwargs):
        r = self.guard("--record", **kwargs)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def test_record_works_through_symlinked_entrypoint(self):
        # 🔴 문서화된 진입점은 심링크 `scripts/phase-tools.py` 다. 동반 스크립트를
        # `__file__` 의 형제로 찾으면 `scripts/supervisor-state.sh` (없는 경로)를 가리켜
        # --record 가 매번 크래시하고, 기록이 없으니 --check 는 늘 통과한다(fail-open).
        link_dir = Path(self.tmp.name) / "scripts-link"
        link_dir.mkdir()
        entry = link_dir / "phase-tools.py"
        entry.symlink_to(TOOLS)
        r = self.guard("--record", tool=entry)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertRegex(self.read_state()["last_failure"]["worktree_hash"],
                         r"^[0-9a-f]{64}$")
        r = self.guard("--check", tool=entry)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)

    def test_snapshot_is_independent_of_invocation_cwd(self):
        # 🔴 스냅샷이 호출 cwd 에 의존하면(`git ls-files --others` 는 cwd 하위만
        # cwd 상대 경로로 나열한다) 같은 워크트리인데도 해시가 달라져 무변경 재시도가 통과한다.
        # 미추적 파일이 저장소 루트에 있어야 이 차이가 드러난다.
        untracked = self.root / "top-untracked.txt"
        untracked.write_text("top\n")
        self.record(cwd=self.root)
        r = self.guard("--check", cwd=self.sub)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)

        # 서브디렉터리에서 실행해도 저장소 어디의 변경이든 보여야 한다.
        untracked.write_text("top changed\n")
        r = self.guard("--check", cwd=self.sub)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_check_of_another_part_is_not_blocked(self):
        # 🟡 `<part>` 가 출력 문구에만 쓰이면 다른 파트의 첫 시도가 남의 실패 기록으로 막힌다.
        self.record(part="3")
        r = self.guard("--check", part="3")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        r = self.guard("--check", part="4")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.guard("--check", phase="18", part="3")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_untracked_symlink_target_change_is_detected(self):
        # 🠠 미추적 심링크를 경로만으로 해시하면 타깃 변경이 안 보여 정당한 재시도가 막힌다.
        link = self.root / "dangling-link"
        link.symlink_to("target-one")  # 깨진 링크 — readlink 만 스냅샷에 반영된다
        self.record()
        link.unlink()
        link.symlink_to("target-two")
        r = self.guard("--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    # --- 리뷰 2라운드 반영 (🔴 1건 + 🟠 1건) ---

    def test_legacy_last_failure_without_scope_is_still_enforced(self):
        # 🔴 `phase`·`part` 키가 없는 기록(이전 버전·수기 편집)을 "스코프 불일치" 로 보고
        # 조용히 통과시키면, 정말 무변경인 재시도가 아무 흔적 없이 허용된다(fail-open).
        # 스코프 필드가 없는 기록은 하위호환으로 해시 비교를 계속 수행해야 한다.
        self.record()
        state = self.read_state()
        state["last_failure"] = {"worktree_hash": state["last_failure"]["worktree_hash"]}
        self.state_file.write_text(json.dumps(state, ensure_ascii=False))
        r = self.guard("--check")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertTrue(r.stderr.strip(), "스코프 없는 기록을 쓸 때는 통지해야 한다")

    def test_scope_mismatch_is_announced_on_stderr(self):
        # 🔴 스코프 불일치로 통과시키는 것은 정상 동작이지만 조용해선 안 된다 —
        # 호출부가 표기를 어긋나게 넘겨 가드가 매번 우회되는 상황을 로그로 구분할 수 있어야 한다.
        self.record(part="3")
        r = self.guard("--check", part="4")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stderr.strip(), "스코프 불일치 통과는 stderr 로 알려야 한다")

    def test_invalid_phase_argument_does_not_use_the_missing_state_code(self):
        # 🟠 argparse 자체 오류는 exit 2 다 — 확정된 "상태 파일 없음 = 2" 와 겹치면
        # 호출부가 CLI 사용 버그를 "기록 없음, 재시도해도 됨" 으로 오분류한다.
        r = self.guard("--check", phase="17a")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertTrue(r.stderr.strip())

    def test_missing_state_file_exits_2(self):
        # 파트 17-2 가 확정한 종료코드 표와 맞춘다: 상태 파일 없음 = 2
        # (1=기타 오류·3=retry_exhausted 와 섞이면 호출부가 구분할 수 없다).
        self.state_file.unlink()
        r = self.guard("--check")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        r = self.guard("--record")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
