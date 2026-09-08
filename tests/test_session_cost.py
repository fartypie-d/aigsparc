"""session-cost.py — --project/--session/--json 과 워크트리 슬러그 해석 (Phase 16 RED, KF-11)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "core/scripts/session-cost.py"


def usage_line(model, msg_id, i, o):
    return json.dumps({"type": "assistant", "message": {
        "id": msg_id, "model": model,
        "usage": {"input_tokens": i, "output_tokens": o,
                  "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}}})


class SessionCost(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.proj = Path(self.tmp.name) / "proj"
        self.proj.mkdir()
        subprocess.run(["git", "init", "-b", "main", str(self.proj)], check=True,
                       capture_output=True, timeout=60)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(self.proj),
                        "commit", "--allow-empty", "-m", "init"],
                       check=True, capture_output=True, timeout=60)
        self.wt = self.proj / ".claude" / "worktrees" / "phase9-x"
        subprocess.run(["git", "-C", str(self.proj), "worktree", "add", "-b", "f9", str(self.wt), "main"],
                       check=True, capture_output=True, timeout=60)
        slug = str(self.proj.resolve()).replace("/", "-")
        self.sdir = self.home / ".claude" / "projects" / slug
        self.sdir.mkdir(parents=True)
        (self.sdir / "aaa.jsonl").write_text(usage_line("claude-opus-5", "m1", 1_000_000, 0) + "\n")
        (self.sdir / "bbb.jsonl").write_text(usage_line("claude-opus-5", "m2", 0, 1_000_000) + "\n")
        self.env = {**os.environ, "HOME": str(self.home)}

    def run_script(self, args, cwd):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd, env=self.env,
                              capture_output=True, text=True, timeout=60)

    def test_session_option_sums_only_that_file(self):
        r = self.run_script(["--project", str(self.proj), "--session", "aaa", "--json"], self.proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["files"], 1)
        self.assertAlmostEqual(data["usd"], 5.0)   # claude-opus-5 input $5/M

    def test_worktree_cwd_resolves_main_checkout_slug(self):
        r = self.run_script(["--session", "bbb", "--json"], self.wt)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertAlmostEqual(json.loads(r.stdout)["usd"], 25.0)  # output $25/M

    def test_missing_session_is_explicit_error(self):
        r = self.run_script(["--project", str(self.proj), "--session", "zzz"], self.proj)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("세션 파일 없음", r.stderr)
        self.assertEqual(r.stdout.strip(), "")

    # Phase 16 RED 2차 (리뷰 반려 대응 — provenance 부재 🔴, 침묵 $0.00 🟠,
    # usd 과소보고 🟠, git 부재 크래시 🟠, --session 경로 탈출 🟠)
    def test_json_reports_which_directory_was_aggregated(self):
        # 어느 프로젝트를 집계했는지 출력에 없으면 틀린 숫자를 검증할 방법이 없다.
        r = self.run_script(["--project", str(self.proj), "--session", "aaa", "--json"], self.proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(Path(json.loads(r.stdout)["project_dir"]).resolve(), self.sdir.resolve())

    def test_table_mode_reports_directory_on_stderr_only(self):
        # 표 출력(stdout) 형식은 동결이므로 provenance 는 stderr 로 나가야 한다.
        r = self.run_script(["--project", str(self.proj), "--session", "aaa"], self.proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("model"), r.stdout[:80])
        self.assertIn(str(self.sdir.resolve()), r.stderr)

    def test_file_without_usage_records_is_explicit_error(self):
        # "집계할 데이터가 없었다" 와 "비용이 $0" 을 구분하지 못하면 침묵 실패다.
        (self.sdir / "empty.jsonl").write_text('{"type":"user","message":{}}\n')
        r = self.run_script(["--project", str(self.proj), "--session", "empty"], self.proj)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "")

    def test_json_flags_incomplete_total_for_unpriced_model(self):
        # usd 만 읽는 소비자가 과소보고를 참값으로 믿지 않도록 완전성 플래그가 필요하다.
        (self.sdir / "ccc.jsonl").write_text(usage_line("nonesuch-model-9", "m3", 1_000, 0) + "\n")
        r = self.run_script(["--project", str(self.proj), "--session", "ccc", "--json"], self.proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertFalse(data["usd_complete"])
        self.assertEqual(data["unknown_models"], ["nonesuch-model-9"])
        ok = json.loads(self.run_script(
            ["--project", str(self.proj), "--session", "aaa", "--json"], self.proj).stdout)
        self.assertTrue(ok["usd_complete"])

    def test_session_id_may_not_escape_the_project_dir(self):
        # pdir / f"{s}.jsonl" 은 s 가 절대경로면 pdir 를 통째로 버린다 (pathlib 동작).
        outside = Path(self.tmp.name) / "outside.jsonl"
        outside.write_text(usage_line("claude-opus-5", "m9", 9_000_000, 0) + "\n")
        for bad in (str(outside)[: -len(".jsonl")], "../../outside"):
            with self.subTest(session=bad):
                r = self.run_script(["--project", str(self.proj), "--session", bad], self.proj)
                self.assertNotEqual(r.returncode, 0, r.stdout)
                self.assertEqual(r.stdout.strip(), "")

    def test_missing_git_binary_falls_back_to_cwd(self):
        # git 이 없으면 "git 밖" 과 같이 조용히 cwd 로 폴백해야 한다 (트레이스백 금지).
        env = {**self.env, "PATH": ""}
        r = subprocess.run([sys.executable, str(SCRIPT), "--session", "aaa", "--json"],
                           cwd=self.proj, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertAlmostEqual(json.loads(r.stdout)["usd"], 5.0)


if __name__ == "__main__":
    unittest.main()
