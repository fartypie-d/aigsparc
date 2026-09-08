"""`core/scripts/supervisor-state.sh` 동결 테스트 — Phase 17 task 2a RED.

동결 규약 (PITFALLS 14): 이 파일은 오케스트레이터가 작성·동결했다. 위임 구현자는 수정하지 않는다.

격리 규약: 모든 실행에 `HOME` 과 `XDG_STATE_HOME` 을 임시 디렉터리로 주입한다.
실제 `~/.claude` · `~/.local/state` 는 읽지도 쓰지도 않는다.

## 동결하는 계약

상태 파일 경로는 `lib/stamp.sh` 와 같다:
`${XDG_STATE_HOME:-$HOME/.local/state}/orchestrate/supervisor/<project>.json`

1. `get <project>` — 상태 파일 바이트를 **그대로** stdout 으로 낸다.
   파일이 없으면 stderr 에 사유를 내고 **exit 2**. 빈 JSON(`{}`)·`null`·빈 출력 폴백 금지.
2. `set <project> <json-file|-> --baseline <sha256>` — baseline 이 현재 파일 해시와 다르면
   **거부**하고 non-zero 로 끝나며(exit 3) 파일을 바꾸지 않는다. `--baseline` 을 아예 주지 않은
   `set` 도 조용히 덮어쓰지 않는다(non-zero). 조용한 덮어쓰기는 이 페이즈의 반려 사유다.
3. baseline 이 맞으면 tmp+`mv` 로 원자 교체하고, 중간 산출물(`*.tmp`·`*.kit-partial.*` 등)을
   상태 디렉터리에 남기지 않는다.
4. `patch <project> <key=value ...>` — 지정 키만 바꾸고 나머지 필드를 보존한다.
5. `owner-check <project>` — owner 의 `pid` 가 살아 있고 `start_id` 가 현재 프로세스의 것과
   일치하면 stdout 첫 낱말이 `alive`, 종료코드 0. mtime 은 **보조 지표**라 오래된 mtime 이어도
   리스가 유효하면 `alive` 다.
6. `owner-check` 회수: 같은 PID 라도 `start_id` 가 다르면(PID 재사용) stdout 첫 낱말이
   `reclaimable`, 종료코드 non-zero. PID 자체가 없어도 `reclaimable`.
   `start_id` 를 어느 소스에서도 얻을 수 없으면 mtime 폴백임을 **출력에 명시**한다(`mtime` 문자열).
   `owner-take` 는 회수 가능할 때만 성공한다.

start_id 1차 소스는 하네스가 쓰는 `$HOME/.claude/sessions/<pid>.json` 의 `procStart` 필드다
(2026-09-02 홈 실측). 이 파일은 **읽기 전용**이다 — 테스트는 격리 HOME 안에 픽스처로만 만든다.
`/proc/<pid>/stat` 22필드는 Linux 한정 폴백이라 해당 케이스는 `sys.platform` 으로 skip 한다.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
SCRIPT = KIT / "core" / "scripts" / "supervisor-state.sh"
RUN_TIMEOUT = 60

PROJECT = "demoproj"

BASE_STATE = {
    "project": PROJECT,
    "root": "/somewhere/demoproj",
    "phase": 17,
    "slug": "supervisor-hardening",
    "worktree": None,
    "branch": "feature/phase17",
    "part": "17-2",
    "status": "idle",
    "child": None,
    "cost": {"phase_usd": 1.5, "parts": {"17-1": 1.5}},
    "phases_since_review": 2,
    "last_review": "2026-09-02",
    "owner": None,
}


def proc_start_id(pid):
    """Linux `/proc/<pid>/stat` 22번째 필드. 없으면 None."""
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return None
    # comm 필드에 공백·괄호가 들어갈 수 있으므로 마지막 ')' 뒤부터 자른다.
    fields = raw.rsplit(")", 1)[1].split()
    # rsplit 뒤 fields[0] 은 3번째 필드(state)다 → 22번째 필드는 인덱스 19.
    return fields[19]


def dead_pid():
    """이미 종료된 자식의 PID — 회수 가능 판정용."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait()
    pid = proc.pid
    try:
        os.kill(pid, 0)
    except OSError:
        return pid
    return None


class _SupervisorStateBase(unittest.TestCase):
    """픽스처·헬퍼만 담는다. 테스트 메서드는 아래 두 클래스에 있다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.supervisor = self.home / ".local" / "state" / "orchestrate" / "supervisor"
        self.supervisor.mkdir(parents=True)
        self.sessions = self.home / ".claude" / "sessions"
        self.sessions.mkdir(parents=True)
        self.state_path = self.supervisor / f"{PROJECT}.json"

    # --- 헬퍼 -----------------------------------------------------------
    def env(self):
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        env["XDG_STATE_HOME"] = str(self.home / ".local" / "state")
        return env

    def run_script(self, *args, stdin=None):
        return subprocess.run(
            ["bash", str(SCRIPT), *args], input=stdin,
            capture_output=True, text=True, env=self.env(), timeout=RUN_TIMEOUT,
        )

    def write_state(self, data):
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        self.state_path.write_text(text, encoding="utf-8")
        return text

    def current_hash(self):
        return hashlib.sha256(self.state_path.read_bytes()).hexdigest()

    def leftovers(self):
        """상태 디렉터리에 남은 중간 산출물 — 상태 파일 자신만 있어야 한다."""
        return sorted(p.name for p in self.supervisor.iterdir()
                      if p.name != f"{PROJECT}.json")

    def write_session_fixture(self, pid, start_id):
        """하네스가 쓰는 `~/.claude/sessions/<pid>.json` 픽스처 (읽기 전용 소스의 모사)."""
        (self.sessions / f"{pid}.json").write_text(json.dumps({
            "pid": pid,
            "sessionId": "ses_fixture",
            "procStart": str(start_id),
            "cwd": str(self.home),
            "kind": "interactive",
            "name": f"supervise-{PROJECT}",
            "status": "busy",
            "updatedAt": "2026-09-02T00:00:00Z",
        }), encoding="utf-8")

    def state_with_owner(self, pid, start_id):
        data = dict(BASE_STATE)
        owner = {"session_id": "ses_fixture", "host": "testhost", "pid": pid}
        if start_id is not None:
            owner["start_id"] = str(start_id)
        else:
            owner["start_id"] = None
        data["owner"] = owner
        data["status"] = "running"
        return self.write_state(data)


class SupervisorStateTest(_SupervisorStateBase):
    """task 2a 에서 동결한 6개 계약 + `/proc` 폴백 1건."""

    # --- 1. get ---------------------------------------------------------
    def test_get_outputs_state_verbatim_and_errors_when_missing(self):
        missing = self.run_script("get", PROJECT)
        self.assertNotEqual(missing.returncode, 0,
                            f"없는 상태 파일에 get 이 성공했다:\n{missing.stdout}{missing.stderr}")
        self.assertEqual(missing.returncode, 2,
                         f"없는 상태 파일의 종료코드는 2 여야 한다:\n{missing.stdout}{missing.stderr}")
        self.assertEqual(missing.stdout.strip(), "",
                         "없는 상태 파일에 빈 JSON·폴백 값을 내보냈다 (조용한 폴백 금지)")
        self.assertNotEqual(missing.stderr.strip(), "",
                            "없는 상태 파일인데 stderr 에 사유가 없다")

        text = self.write_state(BASE_STATE)
        got = self.run_script("get", PROJECT)
        self.assertEqual(got.returncode, 0, f"{got.stdout}{got.stderr}")
        self.assertEqual(json.loads(got.stdout), BASE_STATE,
                         "get 이 상태 JSON 을 그대로 내보내지 않았다")
        self.assertEqual(got.stdout, text,
                         "get 출력이 파일 바이트와 다르다 (재직렬화·주석 삽입 금지)")

    # --- 2. baseline 불일치 거부 ---------------------------------------
    def test_set_rejects_when_baseline_changed(self):
        self.write_state(BASE_STATE)
        stale = self.current_hash()

        # 다른 세션이 먼저 바꿨다 — baseline 이 낡았다.
        changed = dict(BASE_STATE, status="running", part="17-9")
        changed_text = self.write_state(changed)

        payload = json.dumps(dict(BASE_STATE, status="done"), ensure_ascii=False)
        rejected = self.run_script("set", PROJECT, "-", "--baseline", stale, stdin=payload)
        self.assertNotEqual(
            rejected.returncode, 0,
            f"낡은 baseline 으로 set 이 성공했다 (조용한 덮어쓰기):\n{rejected.stdout}{rejected.stderr}")
        self.assertEqual(rejected.returncode, 3,
                         f"baseline 불일치의 종료코드는 3 이어야 한다:\n{rejected.stdout}{rejected.stderr}")
        self.assertEqual(self.state_path.read_text(encoding="utf-8"), changed_text,
                         "baseline 불일치인데 상태 파일이 바뀌었다")
        report = rejected.stdout + rejected.stderr
        self.assertIn(self.current_hash(), report,
                      "거부하면서 현재 파일 해시를 보고하지 않았다")

        # baseline 없이 부르는 것도 조용한 덮어쓰기가 되면 안 된다.
        no_baseline = self.run_script("set", PROJECT, "-", stdin=payload)
        if no_baseline.returncode == 0:
            self.fail("--baseline 없이 부른 set 이 성공했다 (충돌 감지 우회 경로):\n"
                      f"{no_baseline.stdout}{no_baseline.stderr}")
        self.assertEqual(self.state_path.read_text(encoding="utf-8"), changed_text,
                         "--baseline 없는 set 이 파일을 덮었다")

    # --- 3. 원자 교체 ---------------------------------------------------
    def test_set_replaces_atomically_without_leftovers(self):
        self.write_state(BASE_STATE)
        baseline = self.current_hash()
        self.assertEqual(self.leftovers(), [], "사전 조건: 상태 디렉터리가 깨끗해야 한다")

        new_state = dict(BASE_STATE, status="running", part="17-2")
        payload = json.dumps(new_state, ensure_ascii=False)
        result = self.run_script("set", PROJECT, "-", "--baseline", baseline, stdin=payload)
        self.assertEqual(result.returncode, 0,
                         f"올바른 baseline 으로 set 이 실패했다:\n{result.stdout}{result.stderr}")

        self.assertEqual(json.loads(self.state_path.read_text(encoding="utf-8")), new_state,
                         "set 이 새 내용을 반영하지 않았다")
        self.assertEqual(self.leftovers(), [],
                         "원자 교체 후 중간 산출물이 상태 디렉터리에 남았다")
        self.assertFalse(self.state_path.is_symlink(),
                         "상태 파일이 심링크로 바뀌었다")

    # --- 4. patch 보존 --------------------------------------------------
    def test_patch_changes_only_given_keys(self):
        self.write_state(BASE_STATE)

        result = self.run_script("patch", PROJECT, "status=running", "part=17-2")
        self.assertEqual(result.returncode, 0, f"{result.stdout}{result.stderr}")

        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "running", "patch 가 지정 키를 바꾸지 않았다")
        self.assertEqual(data["part"], "17-2", "patch 가 지정 키를 바꾸지 않았다")

        preserved = {k: v for k, v in BASE_STATE.items() if k not in ("status", "part")}
        for key, value in preserved.items():
            self.assertIn(key, data, f"patch 가 필드를 지웠다: {key}")
            self.assertEqual(data[key], value, f"patch 가 지정하지 않은 필드를 바꿨다: {key}")
        self.assertEqual(self.leftovers(), [], "patch 후 중간 산출물이 남았다")

    # --- 5. 살아 있는 리스 ----------------------------------------------
    def test_live_owner_with_matching_start_id_is_alive(self):
        pid = os.getpid()
        start_id = "424242424"
        self.write_session_fixture(pid, start_id)
        self.state_with_owner(pid, start_id)
        # mtime 은 보조 지표다 — 아주 오래된 mtime 이어도 리스가 유효하면 alive 여야 한다.
        os.utime(self.state_path, (1, 1))

        result = self.run_script("owner-check", PROJECT)
        first = result.stdout.split()[0] if result.stdout.split() else ""
        self.assertEqual(first, "alive",
                         f"살아 있는 리스를 alive 로 판정하지 않았다:\n{result.stdout}{result.stderr}")
        self.assertEqual(result.returncode, 0,
                         f"alive 의 종료코드는 0 이어야 한다:\n{result.stdout}{result.stderr}")

        # 살아 있는 리스는 빼앗을 수 없다.
        take = self.run_script("owner-take", PROJECT, "--pid", str(pid), "--start-id", "999")
        self.assertNotEqual(take.returncode, 0,
                            f"살아 있는 리스를 owner-take 가 빼앗았다:\n{take.stdout}{take.stderr}")
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(data["owner"]["start_id"], start_id,
                         "살아 있는 리스의 owner 가 덮어써졌다")

    @unittest.skipUnless(sys.platform.startswith("linux"), "/proc 폴백은 Linux 한정")
    def test_live_owner_falls_back_to_proc_stat(self):
        pid = os.getpid()
        real = proc_start_id(pid)
        self.assertIsNotNone(real, "사전 조건: /proc 에서 start_id 를 읽을 수 있어야 한다")
        # sessions 픽스처를 만들지 않는다 → /proc 폴백 경로만 남는다.
        self.state_with_owner(pid, real)

        result = self.run_script("owner-check", PROJECT)
        first = result.stdout.split()[0] if result.stdout.split() else ""
        self.assertEqual(first, "alive",
                         f"/proc 폴백으로 alive 를 판정하지 못했다:\n{result.stdout}{result.stderr}")
        self.assertEqual(result.returncode, 0, f"{result.stdout}{result.stderr}")

    # --- 6. 회수 판정 ---------------------------------------------------
    def test_stale_owner_with_reused_pid_is_reclaimed(self):
        pid = os.getpid()
        actual = proc_start_id(pid) or "424242424"
        self.write_session_fixture(pid, actual)

        with self.subTest("같은 PID · 다른 start_id (PID 재사용)"):
            self.state_with_owner(pid, "111111111")
            self.assertNotEqual(str(actual), "111111111", "사전 조건: start_id 가 달라야 한다")
            result = self.run_script("owner-check", PROJECT)
            first = result.stdout.split()[0] if result.stdout.split() else ""
            self.assertEqual(first, "reclaimable",
                             "PID 재사용(같은 PID·다른 start_id)을 살아 있다고 오판했다:\n"
                             f"{result.stdout}{result.stderr}")
            self.assertNotEqual(result.returncode, 0,
                                "reclaimable 의 종료코드가 0 이다 (alive 와 구분되지 않는다)")

            # 회수 가능하면 owner-take 가 성공하고 새 리스가 기록된다.
            take = self.run_script("owner-take", PROJECT, "--pid", str(pid),
                                   "--start-id", str(actual))
            self.assertEqual(take.returncode, 0,
                             f"회수 가능한데 owner-take 가 실패했다:\n{take.stdout}{take.stderr}")
            owner = json.loads(self.state_path.read_text(encoding="utf-8"))["owner"]
            self.assertEqual(str(owner["pid"]), str(pid), "owner-take 가 pid 를 기록하지 않았다")
            self.assertEqual(str(owner["start_id"]), str(actual),
                             "owner-take 가 start_id 를 기록하지 않았다")
            self.assertEqual(self.leftovers(), [], "owner-take 후 중간 산출물이 남았다")

        with self.subTest("PID 부재"):
            gone = dead_pid()
            self.assertIsNotNone(gone, "사전 조건: 종료된 PID 를 확보해야 한다")
            self.state_with_owner(gone, "111111111")
            result = self.run_script("owner-check", PROJECT)
            first = result.stdout.split()[0] if result.stdout.split() else ""
            self.assertEqual(first, "reclaimable",
                             f"없는 PID 의 리스를 회수 불가로 판정했다:\n{result.stdout}{result.stderr}")
            self.assertNotEqual(result.returncode, 0, "PID 부재인데 종료코드가 0 이다")

        with self.subTest("start_id 를 얻을 수 없음 → mtime 폴백 명시"):
            self.state_with_owner(pid, None)
            (self.sessions / f"{pid}.json").unlink()
            result = self.run_script("owner-check", PROJECT)
            report = result.stdout + result.stderr
            self.assertIn("mtime", report,
                          "start_id 없이 mtime 으로 판정하면서 그 사실을 출력하지 않았다 "
                          f"(조용한 폴백 금지):\n{report}")


class SupervisorStateReviewTest(_SupervisorStateBase):
    """리뷰 1라운드 🔴·🟡 반영분 — Phase 17 task 2b 재위임 RED (2026-09-02).

    1라운드에서 `silent-failure-hunter` 가 🔴 2건, `security-reviewer` 가 🟡 3건을 냈다.
    아래는 그중 **테스트로 고정할 수 있는 것**만 계약으로 못박은 것이다.
    (TOCTOU 재검사 순서와 `make_temp` 실패 메시지는 결정적으로 재현할 수 없어 코드 리뷰로 확인한다.)
    """

    # 🔴 1 — mtime 폴백 alive 가 검증된 alive 와 종료코드로 구분되지 않는다
    def test_mtime_fallback_is_distinguishable_from_verified_alive(self):
        pid = os.getpid()

        # (가) 검증된 alive — start_id 가 실제로 일치한다.
        self.write_session_fixture(pid, "424242424")
        self.state_with_owner(pid, "424242424")
        verified = self.run_script("owner-check", PROJECT)
        self.assertEqual(verified.stdout.split()[0], "alive")
        self.assertEqual(verified.returncode, 0)

        # (나) start_id 를 어느 소스에서도 얻을 수 없다 → mtime 추측이다.
        (self.sessions / f"{pid}.json").unlink()
        self.state_with_owner(pid, None)
        guessed = self.run_script("owner-check", PROJECT)
        report = guessed.stdout + guessed.stderr
        self.assertIn("mtime", report, "mtime 폴백임을 출력에 명시하지 않았다")

        self.assertNotEqual(
            guessed.stdout.split()[0] if guessed.stdout.split() else "", "alive",
            "mtime 추측을 검증된 alive 와 같은 판정어로 보고했다:\n" + report)
        self.assertNotEqual(
            guessed.returncode, verified.returncode,
            "mtime 추측과 검증된 alive 의 종료코드가 같다 — 종료코드로만 분기하는 호출자가 "
            f"둘을 구분할 수 없다:\n{report}")
        self.assertEqual(
            guessed.returncode, 4,
            f"검증 불가(mtime 폴백)의 종료코드는 4 여야 한다:\n{report}")
        self.assertEqual(guessed.stdout.split()[0], "unverified",
                         f"검증 불가의 판정어는 unverified 여야 한다:\n{report}")

        # 검증되지 않은 판정으로 리스를 빼앗지 않되, 그 사실을 조용히 넘기지 않는다.
        take = self.run_script("owner-take", PROJECT, "--pid", str(pid), "--start-id", "1")
        self.assertNotEqual(take.returncode, 0,
                            "검증 불가 상태에서 owner-take 가 리스를 빼앗았다")
        self.assertIn("mtime", take.stdout + take.stderr,
                      "owner-take 가 검증 불가 판정을 근거로 거부하면서 그 사실을 알리지 않았다 "
                      f"(조용한 폴백):\n{take.stdout}{take.stderr}")

    # 🟡 — 신뢰할 수 없는 owner.pid 가 kill -0 에 그대로 들어간다
    def test_non_positive_owner_pid_is_not_alive(self):
        for bogus in ("0", "-1", "notapid"):
            with self.subTest(pid=bogus):
                self.state_with_owner(bogus, "111111111")
                result = self.run_script("owner-check", PROJECT)
                first = result.stdout.split()[0] if result.stdout.split() else ""
                self.assertEqual(
                    first, "reclaimable",
                    f"owner.pid={bogus} 를 살아 있는 리스로 판정했다 "
                    f"(`kill -0 0`·`kill -0 -1` 은 프로세스 그룹 대상이라 성공한다):\n"
                    f"{result.stdout}{result.stderr}")
                self.assertNotEqual(result.returncode, 0,
                                    f"owner.pid={bogus} 인데 종료코드가 0 이다")

    # 🟡 — 상태 디렉터리가 봉쇄 밖을 가리키는 심링크면 따라가지 않는다
    def test_refuses_when_state_directory_escapes_containment(self):
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        planted = outside / f"{PROJECT}.json"
        planted.write_text(json.dumps(dict(BASE_STATE, project="PLANTED")), encoding="utf-8")

        # supervisor 디렉터리를 봉쇄 밖으로 돌린다.
        for leftover in self.supervisor.iterdir():
            leftover.unlink()
        self.supervisor.rmdir()
        self.supervisor.symlink_to(outside)

        got = self.run_script("get", PROJECT)
        self.assertNotEqual(got.returncode, 0,
                            "봉쇄 밖 심링크 디렉터리의 상태 파일을 그대로 읽었다:\n"
                            f"{got.stdout}{got.stderr}")
        self.assertNotIn("PLANTED", got.stdout,
                         "봉쇄 밖에 심어 둔 상태 파일 내용이 유출됐다")

        payload = json.dumps(dict(BASE_STATE, status="done"), ensure_ascii=False)
        baseline = hashlib.sha256(planted.read_bytes()).hexdigest()
        wrote = self.run_script("set", PROJECT, "-", "--baseline", baseline, stdin=payload)
        self.assertNotEqual(wrote.returncode, 0,
                            "봉쇄 밖 심링크 디렉터리에 상태를 썼다:\n"
                            f"{wrote.stdout}{wrote.stderr}")
        self.assertEqual(json.loads(planted.read_text(encoding="utf-8"))["project"], "PLANTED",
                         "봉쇄 밖 파일이 덮어써졌다")


if __name__ == "__main__":
    unittest.main()
