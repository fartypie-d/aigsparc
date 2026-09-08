---
task: 2a
status: done
---

## Task 2a: RED — `session-cost.py` 옵션·워크트리 슬러그 계약 동결 (3건)
- **에이전트**: 오케스트레이터 직접 (PITFALLS 14)
- **대상 파일**: `tests/test_session_cost.py` (신규)
- **선행**: 없음
- **목표**: 아래 3개 테스트가 현재 구현에서 전부 FAIL임을 확인하고 커밋(동결)한다.
- **재사용**: 없음 — `grep -rn "session-cost" tests/`로 조사(0건, 이 스크립트의 첫 테스트). 격리 방식은 `test_phase_tools.py:Base`와 같이 `tempfile`+`git init`.
- **실패 테스트**: 아래 파일 전체
- **필수 규칙**: `HOME`을 임시 디렉터리로 주입해 실제 `~/.claude/projects`를 읽지 않는다. 커밋은 이 파일만, 메시지
  `test(scripts): session-cost --project/--session/--json 과 워크트리 슬러그 계약을 동결 — RED 3 (오케스트레이터)`.
- **완료 조건**: `python3 -m unittest tests.test_session_cost -v; echo "exit=$?"` → `Ran 3 tests`, 전부 FAIL/ERROR, exit=1.

> **실측 (파트 세션 2026-09-02)**: `Ran 3 tests` · **FAIL 2 + OK 1** · exit=1 (커밋 `f11e996`).
> 지시서 예상("전부 FAIL")과 1건 다르다. `test_missing_session_is_explicit_error`가 지금도 통과하는 것은
> 현행 구현이 `--project`를 **세션 이름**(`sys.argv[1]`)으로 오인해 `세션 파일 없음: …/--project.jsonl`로
> 죽기 때문이다 — 우연한 통과이지 계약 충족이 아니다. 테스트는 1a의 4번과 같은 **폴백 가드**로 그대로 두고
> (약화 금지), 2b 이후에는 `--project`가 정상 파싱된 뒤 `zzz` 부재로 같은 명시 오류가 나야 통과한다.
> RED 근거: 나머지 2건 — `1 != 0 : 세션 파일 없음: …/--project.jsonl`,
> `1 != 0 : 세션 디렉터리 없음: …-proj-.claude-worktrees-phase9-x`(워크트리 슬러그 미해석).

```python
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


if __name__ == "__main__":
    unittest.main()
```
