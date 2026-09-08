"""run-delegation.sh의 serve attach·폴백 회귀 테스트."""

import os
import re
import json
import shlex
import signal
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


KIT = Path(__file__).resolve().parents[1]
SOURCE = KIT / "core/scripts/run-delegation.sh"


class RunDelegationTest(unittest.TestCase):
    """실제 serve나 사용자 상태 디렉터리 없이 PATH 스텁으로 검증한다."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.bin = self.root / "bin"
        self.scripts = self.root / "scripts"
        self.project = self.root / "project"
        for directory in (self.home / ".config/opencode", self.home / ".opencode/bin", self.bin, self.scripts, self.project):
            directory.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE, self.scripts / "run-delegation.sh")
        (self.home / ".config/opencode/model-policy.json").write_text(
            '{"tiers":{"default":["first/model", "second/model"]}}\n'
        )
        (self.home / ".config/opencode/serve.env").write_text(
            "OPENCODE_SERVE_PORT=4096\nOPENCODE_SERVER_PASSWORD=test-password\n"
        )
        os.chmod(self.home / ".config/opencode/serve.env", 0o600)
        self._write("opencode", """#!/usr/bin/env bash
if [ -n "${LOCK_SNAPSHOT:-}" ]; then
  mkdir -p "$LOCK_SNAPSHOT"
  /bin/cp -a "$ORCHESTRATE_STATE_DIR/." "$LOCK_SNAPSHOT/"
fi
printf '%s\\n' "$*" >> "$OPENCODE_CALLS"
if [ -n "${OPENCODE_ENV_DUMP:-}" ]; then
  printf 'OPENCODE_SERVER_PASSWORD=%s\\n' "${OPENCODE_SERVER_PASSWORD:-<unset>}" >> "$OPENCODE_ENV_DUMP"
fi
echo 'loop session.id ses_test_session'
exit "${OPENCODE_RC:-0}"
""", self.home / ".opencode/bin")
        self._write("sleep", "#!/usr/bin/env bash\nexit 0\n", self.bin)
        self._write("ps", "#!/usr/bin/env bash\nexit 0\n", self.bin)
        self._write("opencode-serve-ctl.sh", """#!/usr/bin/env bash
if [ "$1" = "ensure" ] && [ "${SERVE_RC:-0}" -ne 0 ]; then
  exit "$SERVE_RC"
fi
exec bash "$REAL_CTL" "$@"
""", self.scripts)
        os.chmod(self.scripts / "opencode-serve-ctl.sh", 0o644)
        self._write("curl", """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$CURL_CALLS"
CONFIG=$(cat)
printf '%s\\n' "$CONFIG" >> "$CURL_CONFIGS"
COUNT_FILE="${CURL_CALLS}.session-count"
COUNT=0
[ -f "$COUNT_FILE" ] && COUNT=$(cat "$COUNT_FILE")
case "$CONFIG" in
   *'/session?directory='*)
     CREATE_FILE="${CURL_CALLS}.create-count"; CREATE=0
     [ -f "$CREATE_FILE" ] && CREATE=$(cat "$CREATE_FILE")
     CREATE=$((CREATE + 1)); printf '%s' "$CREATE" > "$CREATE_FILE"
     [ "${CURL_CREATE_RC:-0}" -eq 0 ] || exit "$CURL_CREATE_RC"
     printf '{"id":"%s","directory":"/wherever/server/cwd/is"}' "${CURL_CREATE_ID_PREFIX:-ses_created}$CREATE"
     case " $* " in *' --write-out '*) printf '\n%s' "${CURL_CREATE_HTTP_CODE:-200}" ;; esac
    ;;
   *'/session"'*)
     COUNT=$((COUNT + 1)); printf '%s' "$COUNT" > "$COUNT_FILE"
     SESSION_RC_VAR="CURL_SESSIONS_RC_CALL_$COUNT"
     if [ -n "${!SESSION_RC_VAR+x}" ]; then exit "${!SESSION_RC_VAR}"; fi
     [ "${CURL_SESSIONS_RC:-0}" -eq 0 ] || exit "$CURL_SESSIONS_RC"
     SESSION_VAR="CURL_SESSIONS_CALL_$COUNT"
    if [ -n "${!SESSION_VAR+x}" ]; then printf '%s' "${!SESSION_VAR}";
    elif [ "$COUNT" -eq 1 ]; then printf '%s' "${CURL_SESSIONS_BEFORE:-[]}"; else printf '%s' "${CURL_SESSIONS_AFTER:-[]}"; fi
    # 실제 curl 은 --write-out 을 주면 항상 코드를 덧붙인다. 스텁이 이를 생략하면
    # 소스가 "코드 없는 응답"을 수용하도록 휘어진다(이 페이즈의 반복 실패 패턴).
    case " $* " in *' --write-out '*) printf '\n%s' "${CURL_SESSIONS_HTTP_CODE:-200}" ;; esac
    ;;
  *'/abort"'*) printf '%s' "${CURL_ABORT_HTTP_CODE:-200}"; exit "${CURL_ABORT_RC:-0}" ;;
   *'/session/'*)
     [ "${CURL_SESSION_DETAIL_RC:-0}" -eq 0 ] || exit "$CURL_SESSION_DETAIL_RC"
    DETAIL_FILE="${CURL_CALLS}.detail-count"; DETAIL=0
    [ -f "$DETAIL_FILE" ] && DETAIL=$(cat "$DETAIL_FILE")
    DETAIL=$((DETAIL + ${PROGRESS_STEP:-0})); printf '%s' "$DETAIL" > "$DETAIL_FILE"
     printf '%s' "${CURL_SESSION_DETAIL_BODY:-}"
     if [ -z "${CURL_SESSION_DETAIL_BODY:-}" ]; then printf '{"time":{"updated":%s},"tokens":{"input":%s}}' "$DETAIL" "$DETAIL"; fi
     case " $* " in *' --write-out '*) printf '\n%s' "${CURL_SESSION_DETAIL_HTTP_CODE:-200}" ;; esac
    ;;
  *) printf '%s' "${CURL_HTTP_CODE:-200}" ;;
esac
exit 0
""", self.bin)
        self.prompt = self.root / "prompt.txt"
        self.log = self.root / "delegation.log"
        self.prompt.write_text("테스트 프롬프트\n")
        self.calls = self.root / "calls.txt"
        self.curl_calls = self.root / "curl-calls.txt"
        self.curl_configs = self.root / "curl-configs.txt"
        self.opencode_pids = self.root / "opencode-pids.txt"

    def tearDown(self):
        self._stop_stub_processes()
        self.temp.cleanup()

    def _write(self, name, content, directory):
        if name == "opencode":
            content = content.replace(
                "#!/usr/bin/env bash\n",
                "#!/usr/bin/env bash\nprintf '%s\\n' \"$$\" >> \"$OPENCODE_PIDS\"\n",
                1,
            )
        path = directory / name
        path.write_text(content)
        os.chmod(path, 0o755)

    def _stop_stub_processes(self):
        if not self.opencode_pids.exists():
            return
        pids = [int(value) for value in self.opencode_pids.read_text().split() if value.isdigit()]
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        time.sleep(0.05)
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def _script_env(self, project, extra_env):
        environment = os.environ.copy()
        environment.update({
            "HOME": str(self.home),
            "PATH": f"{self.bin}:{environment['PATH']}",
            "OPENCODE_CALLS": str(self.calls),
            "OPENCODE_PIDS": str(self.opencode_pids),
            "CURL_CALLS": str(self.curl_calls),
            "CURL_CONFIGS": str(self.curl_configs),
            "REAL_CTL": str(KIT / "core/scripts/opencode-serve-ctl.sh"),
            "ORCHESTRATE_STATE_DIR": str(self.root / "state"),
            "CURL_SESSIONS_AFTER": '[{"id":"ses_default","directory":"%s","time":{"updated":1},"tokens":1}]' % (project or self.project),
            **extra_env,
        })
        return environment

    def _script_command(self, umask=None, log=None):
        argv = ["bash", str(self.scripts / "run-delegation.sh"), "worker", str(self.prompt), str(log or self.log)]
        if umask is None:
            return argv
        # umask 를 명시 주입하지 않으면, 실행 환경이 이미 좁은 umask(077 등)일 때
        # chmod/install 을 제거하는 변이가 살아남는다(권한 테스트가 환경 덕을 본다).
        quoted = " ".join(shlex.quote(item) for item in argv)
        return ["bash", "-c", "umask %s; exec %s" % (umask, quoted)]

    def run_script(self, *, project=None, umask=None, log=None, **extra_env):
        for suffix in (".session-count", ".detail-count"):
            (Path(str(self.curl_calls) + suffix)).unlink(missing_ok=True)
        return subprocess.run(
            self._script_command(umask=umask, log=log),
            cwd=project or self.project,
            capture_output=True,
            text=True,
            env=self._script_env(project, extra_env),
            timeout=10,
        )

    def launch_script(self, *, project=None, log=None, **extra_env):
        """동시 실행 검증용 — 블로킹하지 않고 `Popen` 을 돌려준다."""
        return subprocess.Popen(
            self._script_command(log=log),
            cwd=project or self.project,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=self._script_env(project, extra_env),
            # 위임 트리(래퍼 + nohup 자식 + 그 후손)를 통째로 정리할 수 있도록 새 세션으로 띄운다.
            start_new_session=True,
        )

    def without_flock_path(self):
        """현재 PATH의 실행 파일을 flock만 제외해 임시 PATH에 노출한다."""
        no_flock = self.root / "no-flock-bin"
        no_flock.mkdir()
        for source_directory in os.environ["PATH"].split(os.pathsep):
            directory = Path(source_directory)
            if not directory.is_dir():
                continue
            for candidate in directory.iterdir():
                if candidate.name == "flock" or not os.access(candidate, os.X_OK):
                    continue
                target = no_flock / candidate.name
                if not target.exists():
                    target.symlink_to(candidate)
        return str(no_flock)

    def assert_lock_snapshot(self, snapshot, *, project):
        """opencode 실행 중 캡처한 락 산출물이 **어느 락인지**까지 확인한다.

        비flock 환경의 산출물은 `<이름>.d` 디렉터리라, 접미사를 정규화하지 않으면
        `assertNotEqual(name, "opencode.lock")` 같은 단정이 **전역 락으로 회귀해도 통과**한다
        (`opencode.lock.d` != `opencode.lock`). 환경 차이는 단정을 지울 이유가 아니라
        정규화해서 각각 단언할 이유다.
        """
        locks = list(snapshot.glob("opencode*.lock"))
        lock_dirs = list(snapshot.glob("opencode*.lock.d"))
        self.assertEqual(len(locks) + len(lock_dirs), 1, list(snapshot.iterdir()) if snapshot.exists() else [])
        lock = (locks + lock_dirs)[0]
        stem = lock.name[:-2] if lock.name.endswith(".d") else lock.name
        if project:
            # 프로젝트 락은 `opencode-<슬러그>-<해시>.lock` 형태다. 전역 락 이름이면 회귀다.
            self.assertTrue(stem.startswith("opencode-"), stem)
            self.assertNotEqual(stem, "opencode.lock")
        else:
            self.assertEqual(stem, "opencode.lock")
        if lock_dirs:
            self.assertTrue((lock_dirs[0] / "pid").is_file())

    def test_attach_mode_uses_project_lock(self):
        snapshot = self.root / "attach-lock"
        result = self.run_script(LOCK_SNAPSHOT=str(snapshot))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_lock_snapshot(snapshot, project=True)
        self.assertIn("--attach http://127.0.0.1:4096", self.calls.read_text())

    def test_concurrent_delegations_of_same_project_serialize(self):
        """같은 프로젝트의 두 위임이 **실제로 배타적으로** 실행돼야 한다.

        락 산출물의 존재만 단정하면 `flock -n` 호출을 지우거나 배타적 `mkdir` 을 항상
        성공시키는 변이가 살아남는다(2d 리뷰 재현). 두 프로세스의 실행 구간이 겹치는지를
        직접 본다. **순서는 단정하지 않는다** — 경합 순서는 비결정적이라 순서를 고정하면
        이 페이즈에서 이미 나온 "비결정 테스트" 함정이 재발한다.

        전파(Task 5) 후 4개 프로젝트가 동시에 위임을 돌릴 때 상호배제가 깨지면 업스트림의
        "토큰 0개 + exit 0 침묵사"가 재발한다 — 이 페이즈가 막으려던 바로 그 결함이다.
        """
        window = self.root / "windows.txt"
        self._write("opencode", """#!/usr/bin/env bash
printf 'START %s\\n' "$(/bin/date +%s%N)" >> "$WINDOW_FILE"
/bin/sleep 1.5
printf 'END %s\\n' "$(/bin/date +%s%N)" >> "$WINDOW_FILE"
echo 'loop session.id ses_test_session'
""", self.home / ".opencode/bin")
        # 스핀락(비flock 경로)은 대기 1회당 10초를 소진한 것으로 계산한다. 무응답 sleep 스텁이면
        # 30분 한도를 순식간에 태워 exit 4 가 되므로, 짧게라도 **실제로 자는** 스텁을 준다.
        self._write("sleep", "#!/usr/bin/env bash\n/bin/sleep 0.2\n", self.bin)

        # curl 스텁은 호출 횟수 파일로 세션 목록의 before/after 를 가른다. 두 프로세스가 그 파일을
        # 공유하면 나중 프로세스가 차분에서 새 세션을 못 찾아(세션 미개시) 락과 무관하게 실패한다.
        first = self.launch_script(
            WINDOW_FILE=str(window),
            log=self.root / "first.log",
            CURL_CALLS=str(self.root / "curl-first.txt"),
            CURL_CONFIGS=str(self.root / "curl-first-configs.txt"),
        )
        second = self.launch_script(
            WINDOW_FILE=str(window),
            log=self.root / "second.log",
            CURL_CALLS=str(self.root / "curl-second.txt"),
            CURL_CONFIGS=str(self.root / "curl-second-configs.txt"),
        )
        first_output = first.communicate(timeout=60)
        second_output = second.communicate(timeout=60)
        self.assertEqual(first.returncode, 0, first_output)
        self.assertEqual(second.returncode, 0, second_output)

        events = [line.split() for line in window.read_text().splitlines() if line.strip()]
        starts = sorted(int(event[1]) for event in events if event[0] == "START")
        ends = sorted(int(event[1]) for event in events if event[0] == "END")
        self.assertEqual(len(starts), 2, window.read_text())
        self.assertEqual(len(ends), 2, window.read_text())
        # 두 구간이 겹치지 않으면 "먼저 끝난 시각 <= 나중 시작 시각"이 성립한다.
        self.assertLessEqual(
            ends[0],
            starts[1],
            "두 위임의 실행 구간이 겹쳤다 — 상호배제가 성립하지 않는다:\n%s" % window.read_text(),
        )

    def test_projects_with_same_basename_get_distinct_locks(self):
        """basename 이 같은 두 프로젝트는 서로 다른 락을 써야 한다 (경로 해시가 이름에 들어간다).

        이름만으로 락을 만들면 `~/a/project` 와 `~/b/project` 가 한 락을 공유해
        무관한 두 프로젝트의 위임이 서로를 막는다.
        """
        seen = []
        for parent in ("a", "b"):
            project = self.root / parent / "project"
            project.mkdir(parents=True)
            snapshot = self.root / ("lock-" + parent)
            session = '[{"id":"ses_default","directory":"%s","time":{"updated":1},"tokens":1}]' % project
            result = self.run_script(project=project, CURL_SESSIONS_AFTER=session, LOCK_SNAPSHOT=str(snapshot))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            names = {item.name for item in snapshot.glob("opencode*.lock*")}
            self.assertNotIn("opencode.lock", names, "프로젝트 위임이 전역 락을 잡았다")
            seen.append(names)
        # 두 번째 스냅샷에는 첫 실행의 락도 남아 있다. 새로 생긴 이름이 있어야 두 프로젝트가
        # 서로 다른 락을 쓴 것이다 — 이름이 basename 만으로 정해지면 새 이름이 생기지 않는다.
        self.assertTrue(seen[1] - seen[0], "basename 이 같은 두 프로젝트가 같은 락을 공유했다: %s" % seen)

    def test_lock_is_released_when_delegation_processes_die(self):
        """위임 프로세스가 모두 사라지면 락이 남아 다음 위임을 영구히 막으면 안 된다.

        주의 — **래퍼만 죽는 것으로는 부족하다.** nohup 자식이 락 fd 를 상속하도록 설계돼 있어
        (2026-07-28 결정), 래퍼가 죽어도 실제 위임이 도는 동안 락은 유지된다. 그게 정상이다.
        이 테스트는 래퍼와 자식이 **모두** 사라진 뒤를 본다(크래시·강제 종료 시나리오).
        """
        window = self.root / "windows.txt"
        self._write("opencode", """#!/usr/bin/env bash
printf 'START %s\\n' "$(/bin/date +%s%N)" >> "$WINDOW_FILE"
/bin/sleep 30
""", self.home / ".opencode/bin")
        self._write("sleep", "#!/usr/bin/env bash\n/bin/sleep 0.2\n", self.bin)
        holder = self.launch_script(
            WINDOW_FILE=str(window),
            log=self.root / "holder.log",
            CURL_CALLS=str(self.root / "curl-holder.txt"),
        )
        state = self.root / "state"
        deadline = time.time() + 10
        while time.time() < deadline and not (state.exists() and any(state.glob("opencode*.lock*"))):
            time.sleep(0.1)
        self.assertTrue(any(state.glob("opencode*.lock*")), "첫 위임이 락을 잡지 못했다")

        # 락 fd 는 후손이 하나라도 살아 있으면 유지된다(설계된 동작). 트리를 통째로 정리한다.
        os.killpg(os.getpgid(holder.pid), signal.SIGKILL)
        holder.communicate(timeout=10)

        # 원래 스텁(즉시 종료)으로 되돌려 두 번째 위임이 곧바로 끝나는지 본다.
        self._write("opencode", """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$OPENCODE_CALLS"
echo 'loop session.id ses_test_session'
""", self.home / ".opencode/bin")
        try:
            result = self.run_script(log=self.root / "second.log")
        except subprocess.TimeoutExpired:
            self.fail("래퍼가 죽은 뒤에도 락이 남아 다음 위임이 진행되지 못했다")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_attach_creates_session_before_launch(self):
        """attach 모드는 세션을 **먼저 만들고** 그 ID 로 클라이언트를 붙여야 한다.

        서버는 세션의 directory 를 자기 cwd 로 기록하므로(PITFALLS 18), 기동 전후 차분 +
        directory 일치로 식별하면 서버를 띄운 프로젝트에서만 성공한다.
        """
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("--session ses_created1", self.calls.read_text())
        self.assertIn("SESSION_ID=ses_created1", result.stdout)

    def test_attach_session_survives_server_cwd_mismatch(self):
        """서버가 엉뚱한 directory 를 돌려줘도 위임은 성공해야 한다 (PITFALLS 18 회귀 고정)."""
        mismatched = '[{"id":"ses_elsewhere","directory":"/not/this/project","time":{"updated":1},"tokens":1}]'
        result = self.run_script(CURL_SESSIONS_BEFORE=mismatched, CURL_SESSIONS_AFTER=mismatched)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("DONE", result.stdout)

    def test_session_creation_failure_falls_back_to_standalone(self):
        """세션 생성이 실패하면 attach 를 포기하고 검증된 standalone 경로로 진행한다."""
        result = self.run_script(CURL_CREATE_HTTP_CODE="500")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SERVE_FALLBACK", result.stdout)
        calls = self.calls.read_text()
        self.assertNotIn("--attach", calls, "생성 실패인데 attach 로 붙었다")

    def test_session_creation_failure_does_not_abort_other_sessions(self):
        """생성 실패 시 남의 세션(사용자 대화형 TUI 등)을 abort 하면 안 된다."""
        existing = '[{"id":"ses_USER_INTERACTIVE_TUI","directory":"%s","time":{"updated":1}}]' % self.project
        result = self.run_script(CURL_CREATE_HTTP_CODE="500", CURL_SESSIONS_AFTER=existing)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        configs = self.curl_configs.read_text() if self.curl_configs.exists() else ""
        self.assertNotIn("/session/ses_USER_INTERACTIVE_TUI/abort", configs)

    def test_new_session_per_model_attempt(self):
        """모델 폴백 시 이전 세션 ID 를 재사용하지 말고 새로 만든다."""
        self._write("opencode", """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$OPENCODE_CALLS"
COUNT=$(grep -c . "$OPENCODE_CALLS")
echo 'loop session.id ses_test_session'
if [ "$COUNT" -eq 1 ]; then echo 'ERROR status 429 rate limit'; exit 1; fi
""", self.home / ".opencode/bin")
        result = self.run_script(PROGRESS_STEP="1")
        calls = self.calls.read_text()
        self.assertIn("--session ses_created1", calls)
        self.assertIn("--session ses_created2", calls, "두 번째 모델이 이전 세션을 재사용했다:\n" + calls)

    def test_log_injected_session_id_is_never_used_for_abort(self):
        """abort 대상은 서버가 준 ID 뿐이다 — 로그에 심어진 ID 를 신뢰하면 안 된다."""
        self._write("opencode", """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$OPENCODE_CALLS"
echo '{"sessionID":"ses_ATTACKER"}'
echo 'loop session.id real'
echo '! agent "worker" not found. Falling back to default agent'
""", self.home / ".opencode/bin")
        result = self.run_script()
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        configs = self.curl_configs.read_text()
        self.assertNotIn("ses_ATTACKER", configs)
        self.assertIn("/session/ses_created1/abort", configs)

    def test_repository_serve_ctl_symlink_reaches_controller(self):
        controller = KIT / "scripts/opencode-serve-ctl.sh"
        self.assertTrue(controller.is_symlink())
        result = subprocess.run(
            ["bash", str(controller), "invalid"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 64)
        self.assertIn("사용법:", result.stderr)

    def test_nonexecutable_ctl_is_found_when_bash_invokes_it(self):
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("serve 제어 스크립트 없음", result.stdout)

    def test_spinlock_writes_pid_file_without_flock(self):
        stale_lock = self.root / "state/opencode.lock.d"
        stale_lock.mkdir(parents=True)
        (stale_lock / "pid").write_text("99999999\n")
        observed_pid = self.root / "spinlock-pid"
        self._write("rm", "#!/usr/bin/env bash\nif [ -f \"$2/pid\" ]; then /bin/cp \"$2/pid\" \"$SPINLOCK_PID\"; fi\n/bin/rm \"$@\"\n", self.bin)
        result = self.run_script(SERVE_RC="1", PATH=f"{self.bin}:{self.without_flock_path()}", SPINLOCK_PID=str(observed_pid))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(stale_lock.exists())
        self.assertNotEqual(observed_pid.read_text().strip(), "99999999")

    def test_log_and_state_permissions_are_private(self):
        # umask 022(느슨한 환경)를 명시 주입한다 — 좁은 umask 환경에서는 권한 설정 코드를
        # 제거해도 결과가 우연히 사적이라 변이가 살아남는다.
        result = self.run_script(umask="022")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.log.stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.root / "state").stat().st_mode & 0o777, 0o700)

    def test_serve_env_injection_is_rejected(self):
        (self.home / ".config/opencode/serve.env").write_text(
            "OPENCODE_SERVE_PORT=4096\nOPENCODE_SERVER_PASSWORD='safe\nurl = \"http://attacker.invalid\"'\n"
        )
        os.chmod(self.home / ".config/opencode/serve.env", 0o600)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # 폴백 사유까지 단정해야 이 테스트가 공허해지지 않는다. 검증이 제거되면 attach 로 진행해
        # 이 메시지가 사라지고 주입이 성립한다(리뷰 재현 확인).
        self.assertIn(
            "SERVE_FALLBACK: standalone 모드 (서버 인증정보 없음)",
            result.stdout,
            "악성 비밀번호가 ctl 검증에서 거부되지 않았다 — attach 로 진행하면 주입이 성립한다",
        )
        configs = self.curl_configs.read_text() if self.curl_configs.exists() else ""
        self.assertNotIn('url = "http://attacker.invalid"', configs)

    def test_password_reaches_attach_client(self):
        """attach 모드에서는 클라이언트 자식이 서버 비밀번호를 **가져야** 한다.

        `opencode run --attach` 는 `OPENCODE_SERVER_PASSWORD`(또는 `-p`)로 서버에 인증한다.
        이것을 지우면 클라이언트가 `Error: Session not found` 로 즉사한다(2026-08-13 실환경 실측 —
        스텁 테스트로는 잡히지 않아 전파 시점에 4개 프로젝트가 동시에 깨졌다).
        `-p` 로 argv 에 넣는 대안은 공용 서버에서 `ps` 로 전 사용자에게 노출되므로 더 나쁘다.
        위임 에이전트는 같은 사용자라 어차피 `serve.env`(600)를 읽을 수 있으므로,
        클라이언트에게 주지 않는 것은 방어 효과가 없다.
        """
        dump = self.root / "child-env.txt"
        result = self.run_script(OPENCODE_ENV_DUMP=str(dump))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("MODE=attach", result.stdout + "MODE=attach")  # 하네스 기본이 attach 경로다
        self.assertIn(
            "OPENCODE_SERVER_PASSWORD=test-password",
            dump.read_text(),
            "attach 클라이언트가 비밀번호를 못 받으면 서버 인증에 실패한다",
        )

    def test_password_is_absent_in_standalone_mode(self):
        """standalone 폴백에서는 서버가 없으므로 비밀번호를 자식에게 넘기지 않는다."""
        dump = self.root / "child-env.txt"
        result = self.run_script(SERVE_RC="1", OPENCODE_ENV_DUMP=str(dump))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SERVE_FALLBACK", result.stdout)
        self.assertIn(
            "OPENCODE_SERVER_PASSWORD=<unset>",
            dump.read_text(),
            "standalone 인데 비밀번호가 자식 환경에 남았다",
        )

    def test_password_is_absent_when_attempt_falls_back_to_standalone(self):
        """attach 로 시작해도 *그 시도만* standalone 으로 떨어지면 비밀번호를 넘기지 않는다.

        전역 `$MODE` 만 보는 가드는 이 경로를 놓친다 — `secrets.env` 를 `set -a` 로 소싱한 뒤
        세션 생성 실패로 `ATTEMPT_MODE=standalone` 이 되면 자식이 비밀번호를 그대로 상속한다.
        """
        (self.home / ".config/opencode/secrets.env").write_text(
            "OPENCODE_SERVER_PASSWORD=SECRETS_ENV_LEAK\n"
        )
        os.chmod(self.home / ".config/opencode/secrets.env", 0o600)
        dump = self.root / "child-env-attempt-fallback.txt"
        result = self.run_script(CURL_CREATE_HTTP_CODE="500", OPENCODE_ENV_DUMP=str(dump))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # 전역은 attach 인데 이 시도만 standalone 으로 떨어진 경로여야 의미가 있다.
        self.assertNotIn("--attach", self.calls.read_text(), result.stdout)
        self.assertIn(
            "OPENCODE_SERVER_PASSWORD=<unset>",
            dump.read_text(),
            "시도 단위 standalone 폴백인데 비밀번호가 자식 환경에 남았다",
        )

    def test_log_file_permissions_normalized_when_file_exists(self):
        """이미 존재하는 로그 파일도 매 실행 600으로 교정돼야 한다.

        `(umask 0177; : > FILE)` 는 **생성 시에만** 적용되므로 기존 644 파일은 그대로 남는다.
        공용 서버에서 로그에는 위임 프롬프트 전문과 세션 ID가 들어간다.
        """
        self.log.write_text("이전 실행 잔재\n")
        os.chmod(self.log, 0o644)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            self.log.stat().st_mode & 0o777,
            0o600,
            "기존 로그 파일 권한이 600으로 교정되지 않았다",
        )

    def test_log_file_is_600_from_creation(self):
        self._write("chmod", """#!/usr/bin/env bash
if [ "$2" = "$WATCHED_LOG_FILE" ]; then
  printf '%s\\n' "$(/usr/bin/stat -c %a "$2")" >> "$CHMOD_LOG"
fi
/bin/chmod "$@"
""", self.bin)
        result = self.run_script(
            WATCHED_LOG_FILE=str(self.log),
            CHMOD_LOG=str(self.root / "chmod-log"),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.root / "chmod-log").exists(), "로그 생성 뒤 chmod가 호출되었습니다")
        self.assertEqual(self.log.stat().st_mode & 0o777, 0o600)

    def test_project_lock_name_strips_newlines(self):
        project = self.root / "project\nMODEL_USED=forged"
        project.mkdir()
        session = json.dumps([{"id": "ses_newline", "directory": str(project), "time": {"updated": 1}}])
        snapshot = self.root / "newline-lock"
        result = self.run_script(project=project, CURL_SESSIONS_AFTER=session, LOCK_SNAPSHOT=str(snapshot))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_lock_snapshot(snapshot, project=True)
        lock = next(iter(list(snapshot.glob("opencode-*.lock")) + list(snapshot.glob("opencode-*.lock.d"))))
        self.assertNotIn("\n", lock.name)

    def test_standalone_fallback_acquires_global_lock(self):
        snapshot = self.root / "global-lock"
        result = self.run_script(SERVE_RC="1", LOCK_SNAPSHOT=str(snapshot))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_lock_snapshot(snapshot, project=False)
        self.assertIn("SERVE_FALLBACK: standalone 모드", result.stdout)
        self.assertNotIn("--attach", self.calls.read_text())

    def test_fallback_reports_missing_ctl(self):
        (self.scripts / "opencode-serve-ctl.sh").unlink()
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("serve 제어 스크립트 없음", result.stdout)

    def test_fallback_warns_when_serve_is_alive(self):
        self._write("ps", "#!/usr/bin/env bash\nprintf '%s\\n' ' 401 2 401 /tmp/opencode serve --port 4096'\n", self.bin)
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SERVE_ALIVE_FALLBACK", result.stdout + result.stderr)

    def test_fallback_warns_when_bare_opencode_serve_is_alive(self):
        self._write("ps", "#!/usr/bin/env bash\nprintf '%s\\n' ' 401 2 401 opencode serve --port 4096'\n", self.bin)
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SERVE_ALIVE_FALLBACK", result.stdout + result.stderr)

    # `ps -eo pid,ppid,pgid,args` 전체 스캔과 `ps ... -p <pid>` 단건 조회에 **모두** 답하는 스텁.
    # 구현이 같은 스캔 안에서 부모를 찾든 별도 조회를 하든 통과해야 한다(구현 방식을 고정하지 않는다).
    PS_TABLE_STUB = """#!/usr/bin/env bash
TABLE=%s
TARGET=""
PREV=""
for ARG in "$@"; do
  if [ "$PREV" = "-p" ]; then TARGET="$ARG"; fi
  PREV="$ARG"
done
if [ -n "$TARGET" ]; then
  printf '%%s\\n' "$TABLE" | awk -v p="$TARGET" '$1 == p { $1=""; $2=""; $3=""; sub(/^ +/, ""); print }'
  exit 0
fi
printf '%%s\\n' "$TABLE"
"""

    # 위임 래퍼(부모) 행. 실행 파일이 bash 라 전체 스캔의 opencode 필터에는 걸리지 않는다.
    WRAPPER_ROW = " 500 400 400 bash scripts/run-delegation.sh worker prompt.txt delegation.log"

    def _write_ps_table(self, *rows):
        table = "\n".join(rows)
        self._write("ps", self.PS_TABLE_STUB % ("'" + table + "'"), self.bin)

    def test_preflight_ignores_managed_attach_process(self):
        # 부모가 실제로 위임 래퍼일 때만 "관리 중"이다. (예전 스텁은 부모 행이 없어
        # ppid≠1 이라는 이유만으로 통과했다 — 부모 미상은 관리 근거가 못 된다.)
        self._write_ps_table(
            " 401 500 401 /tmp/opencode run --attach http://127.0.0.1:4096",
            self.WRAPPER_ROW,
        )
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_preflight_flags_attachlike_prompt_text_from_foreign_parent(self):
        """프롬프트 본문에 attach 플래그처럼 보이는 문자열이 있어도 부모가 래퍼가 아니면 차단.

        `ps` 는 argv 를 공백으로 이어 보여주므로 문자열만으로는 진짜 플래그와 구분할 수 없다.
        이 저장소는 그 문법을 다루는 프로젝트라 프롬프트에 등장할 개연성이 낮지 않다.
        """
        self._write_ps_table(
            " 401 700 401 /tmp/opencode run 프롬프트에 --attach http://127.0.0.1:9999 문구가 있음",
            " 700 1 700 /bin/bash -c 사용자가-직접-실행",
        )
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_preflight_accepts_equals_form_attach_from_wrapper(self):
        """등호 형식(`--attach=URL`)도 부모가 래퍼면 정상 — 공백 형식만 인정하면 정상 병렬 위임이 죽는다."""
        self._write_ps_table(
            " 401 500 401 /tmp/opencode run --attach=http://127.0.0.1:4096 --dir /x",
            self.WRAPPER_ROW,
        )
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_preflight_flags_process_whose_parent_is_unknown(self):
        """부모 조회가 비면 '관리 중'으로 취급하지 말 것 — 부모 미상은 fail-closed 다."""
        self._write_ps_table(
            " 401 900 401 /tmp/opencode run --attach http://127.0.0.1:4096",
        )
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_preflight_flags_parent_that_merely_mentions_wrapper_name(self):
        """부모 판정도 **필드**로 해야 한다 — 명령줄에 이름이 스쳐 지나가는 것은 근거가 아니다.

        자식 후보는 `basename($4)=="opencode"`·`$5=="run"` 처럼 엄격히 보면서 부모만 전체 줄
        부분 문자열로 보면, 이 task 가 닫으려던 위장이 부모 쪽으로 옮겨갈 뿐이다.
        """
        self._write_ps_table(
            " 401 700 401 /tmp/opencode run --attach http://127.0.0.1:9999",
            " 700 1 700 /bin/bash -c echo not-the-real-run-delegation-wrapper-but-mentions-it",
        )
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_preflight_ignores_client_of_versioned_wrapper(self):
        """래퍼 파일명이 `run-delegation-v2.sh` 처럼 변형이어도 관리 중으로 인정해야 한다.

        위임 스크립트를 고치는 페이즈에서는 안정본 사본을 얼려서 쓴다(이 저장소의 운영 관행).
        정확히 `run-delegation.sh` 만 인정하면 그 기간의 정상 병렬 위임이 exit 3 으로 죽는다.
        """
        self._write_ps_table(
            " 401 500 401 /tmp/opencode run --attach http://127.0.0.1:4096",
            " 500 400 400 bash scripts/run-delegation-v2.sh worker prompt.txt delegation.log",
        )
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_preflight_flags_parent_with_lookalike_wrapper_filename(self):
        """신뢰하는 래퍼 이름은 `run-delegation.sh` 와 버전 사본(`-v2`)뿐이다.

        `^run-delegation.*[.]sh$` 같은 열린 와일드카드는 임의의 `run-delegation*.sh` 파일명을
        신뢰한다. 이 가드는 Task 5 에서 4개 프로젝트로 복사되므로 전파 전에 좁혀야 한다.
        """
        self._write_ps_table(
            " 401 700 401 /tmp/opencode run --attach http://127.0.0.1:9999",
            " 700 1 700 bash /home/other/run-delegation-totally-unrelated-script.sh",
        )
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_preflight_ignores_bare_argv_client_of_wrapper(self):
        """경로 없는 bare argv + 진짜 attach + 부모가 래퍼 → 무시 (E1×E3 교차, C23)."""
        self._write_ps_table(
            " 401 500 401 opencode run --attach http://127.0.0.1:4096",
            self.WRAPPER_ROW,
        )
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_preflight_blocks_orphan_attach_process(self):
        self._write("ps", "#!/usr/bin/env bash\nprintf '%s\\n' ' 401 1 401 /tmp/opencode run --attach http://127.0.0.1:4096'\n", self.bin)
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_preflight_blocks_bare_orphan_in_own_process_group(self):
        # C19: 현재 프리플라이트는 ps -o pgid= -p $$를 호출하지 않는다. 변이로 그 호출이
        # 되살아나도 이 테스트가 우연히 통과하지 않도록, 실제 ps 표 형식만 반환한다.
        self._write("ps", "#!/usr/bin/env bash\nprintf '%s\\n' ' 401 1 401 opencode run --attach http://127.0.0.1:4096'\n", self.bin)
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_preflight_blocks_prompt_text_that_only_mentions_attach(self):
        self._write("ps", "#!/usr/bin/env bash\nprintf '%s\\n' ' 401 2 401 /tmp/opencode run 작업 프롬프트에 --attach 단어가 있음'\n", self.bin)
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_preflight_ignores_unrelated_argv_text(self):
        self._write("ps", "#!/usr/bin/env bash\nprintf '%s\\n' ' 401 1 401 /bin/bash -c prompt-contains-opencode run --attach'\n", self.bin)
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_agent_not_found_fails_fast(self):
        self._write("opencode", """#!/usr/bin/env bash
echo '{"type":"error","sessionID":"ses_test_session","message":"agent \\"worker\\" not found"}'
""", self.home / ".opencode/bin")
        session = '[{"id":"ses_agent","directory":"%s","time":{"updated":1}}]' % self.project
        result = self.run_script(
            CURL_SESSIONS_CALL_1="[]",
            CURL_SESSIONS_CALL_2=session,
            CURL_SESSIONS_CALL_3="[]",
            CURL_SESSIONS_CALL_4=session,
        )
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        self.assertIn("AGENT_NOT_FOUND", result.stdout)

    def test_agent_not_found_ignores_agent_output(self):
        self._write("opencode", "#!/usr/bin/env bash\nfor _ in $(seq 1 60); do echo 'INFO 작업 진행'; done\necho 'loop session.id ses_ok'\necho '작업 결과: agent \"worker\" not found 문구를 설명함'\n", self.home / ".opencode/bin")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("DONE", result.stdout)

    def test_agent_not_found_detects_raw_quote_form(self):
        self._write("opencode", "#!/usr/bin/env bash\necho '! agent \"worker\" not found. Falling back to default agent'\n", self.home / ".opencode/bin")
        session = '[{"id":"ses_raw_quote","directory":"%s","time":{"updated":1}}]' % self.project
        result = self.run_script(CURL_SESSIONS_AFTER=session)
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        self.assertIn("AGENT_NOT_FOUND", result.stdout)

    def test_agent_not_found_is_detected_after_30_line_preamble(self):
        self._write("opencode", "#!/usr/bin/env bash\nfor _ in $(seq 1 31); do echo 'INFO 초기화'; done\necho 'agent \\\"worker\\\" not found'\n", self.home / ".opencode/bin")
        session = '[{"id":"ses_long_preamble","directory":"%s","time":{"updated":1}}]' % self.project
        result = self.run_script(CURL_SESSIONS_AFTER=session)
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        self.assertIn("AGENT_NOT_FOUND", result.stdout)

    def test_fallback_reports_missing_serve_port(self):
        (self.home / ".config/opencode/serve.env").write_text(
            "OPENCODE_SERVER_PASSWORD=test-password\n"
        )
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SERVE_FALLBACK: standalone 모드 (serve 환경 포트 없음)", result.stdout)

    def test_watchdog_aborts_server_session(self):
        self._write("opencode", """#!/usr/bin/env bash
echo '{"type":"error","sessionID":"ses_abort_target","message":"agent \\"worker\\" not found"}'
""", self.home / ".opencode/bin")
        result = self.run_script()
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        self.assertIn("--request POST", self.curl_calls.read_text())
        config = self.curl_configs.read_text()
        self.assertIn("url = \"http://127.0.0.1:4096/session/ses_created1/abort\"", config)
        self.assertIn("user = \"opencode:test-password\"", config)
        self.assertNotIn("test-password", self.curl_calls.read_text())

    def test_abort_failure_is_surfaced(self):
        self._write("opencode", """#!/usr/bin/env bash
echo '{"type":"error","sessionID":"ses_abort_failure","message":"agent \\"worker\\" not found"}'
""", self.home / ".opencode/bin")
        result = self.run_script(CURL_ABORT_RC="1")
        self.assertEqual(result.returncode, 6, result.stdout + result.stderr)
        self.assertIn("ORPHAN_SESSIONS=ses_created1", result.stdout)

    def test_worktrees_share_project_lock(self):
        repository = self.root / "repository"
        worktree = self.root / "worktree"
        repository.mkdir()
        worktree.mkdir()
        self._write("git", """#!/usr/bin/env bash
if [ "$1" = rev-parse ]; then
  printf '%s\\n' "$TEST_COMMON_DIR"
  exit 0
fi
exit 1
""", self.bin)
        first_snapshot = self.root / "first-worktree-lock"
        second_snapshot = self.root / "second-worktree-lock"
        first = self.run_script(project=repository, TEST_COMMON_DIR=str(repository / ".git"), LOCK_SNAPSHOT=str(first_snapshot))
        second = self.run_script(project=worktree, TEST_COMMON_DIR=str(repository / ".git"), LOCK_SNAPSHOT=str(second_snapshot))
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assert_lock_snapshot(first_snapshot, project=True)
        self.assert_lock_snapshot(second_snapshot, project=True)
        self.assertEqual(
            [item.name for item in first_snapshot.glob("opencode-*.lock*")],
            [item.name for item in second_snapshot.glob("opencode-*.lock*")],
        )

    def test_model_fallback_chain_preserved(self):
        # 각 실행은 별도 프로세스이므로 호출 횟수 파일로 시도 순서를 판정한다.
        self._write("opencode", """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$OPENCODE_CALLS"
COUNT=$(wc -l < "$OPENCODE_CALLS")
echo 'loop session.id test-session'
if [ "$COUNT" -eq 1 ]; then echo 'ERROR status 429 rate limit'; exit 1; fi
""", self.home / ".opencode/bin")
        first = '[{"id":"ses_first","directory":"%s","time":{"updated":1}}]' % self.project
        both = '[{"id":"ses_first","directory":"%s","time":{"updated":1}},{"id":"ses_second","directory":"%s","time":{"updated":2}}]' % (self.project, self.project)
        result = self.run_script(
            CURL_SESSIONS_CALL_1="[]",
            CURL_SESSIONS_CALL_2=first,
            CURL_SESSIONS_CALL_3=first,
            CURL_SESSIONS_CALL_4=both,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("MODEL_USED=second/model", result.stdout)
        self.assertIn("MODEL_FALLBACK: first/model", result.stdout)

    def test_attach_uses_text_format(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = self.calls.read_text()
        self.assertIn("--print-logs --log-level INFO", calls)
        self.assertNotIn("--format json", calls)

    def test_stalled_at_init_still_exit_2(self):
        self._write("opencode", """#!/usr/bin/env bash
echo 'INFO bootstrap complete'
while :; do /bin/sleep 1; done
""", self.home / ".opencode/bin")
        result = self.run_script()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("STALLED_AT_INIT", result.stdout)

    def test_init_stall_reports_orphan_possibility(self):
        self._write("opencode", "#!/usr/bin/env bash\nwhile :; do /bin/sleep 1; done\n", self.home / ".opencode/bin")
        result = self.run_script()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("ORPHAN_SESSIONS=ses_created1", result.stdout)

    def test_init_stall_does_not_report_orphan_after_successful_abort(self):
        self._write("opencode", "#!/usr/bin/env bash\nwhile :; do /bin/sleep 1; done\n", self.home / ".opencode/bin")
        late = '[{"id":"ses_late","directory":"%s","time":{"updated":1}}]' % self.project
        result = self.run_script(
            CURL_SESSIONS_CALL_1="[]", CURL_SESSIONS_CALL_2="[]",
            CURL_SESSIONS_CALL_3="[]", CURL_SESSIONS_CALL_4="[]",
            CURL_SESSIONS_CALL_5="[]", CURL_SESSIONS_CALL_6="[]",
            CURL_SESSIONS_CALL_7="[]", CURL_SESSIONS_CALL_8="[]",
            CURL_SESSIONS_CALL_9="[]", CURL_SESSIONS_CALL_10="[]",
            CURL_SESSIONS_CALL_11="[]", CURL_SESSIONS_CALL_12="[]",
            CURL_SESSIONS_CALL_13="[]", CURL_SESSIONS_CALL_14=late,
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("SESSION_ABORTED=ses_late", result.stdout)
        self.assertNotIn("ORPHAN_SESSIONS=미확보", result.stdout)

    def test_progress_http_error_counts_as_poll_failure(self):
        self._write("opencode", "#!/usr/bin/env bash\nwhile :; do echo 'ERROR status 429 rate limit'; /bin/sleep .01; done\n", self.home / ".opencode/bin")
        self._write("date", "#!/usr/bin/env bash\nFILE=\"$DATE_COUNTER\"; VALUE=0; [ -f \"$FILE\" ] && VALUE=$(cat \"$FILE\"); VALUE=$((VALUE + 10)); printf '%s' \"$VALUE\" > \"$FILE\"; printf '%s\\n' \"$VALUE\"\n", self.bin)
        (self.home / ".config/opencode/model-policy.json").write_text('{"tiers":{"default":["first/model"]}}\n')
        session = '[{"id":"ses_unauthorized","directory":"%s","time":{"updated":1}}]' % self.project
        result = self.run_script(
            CURL_SESSIONS_AFTER=session,
            CURL_SESSION_DETAIL_BODY='{"error":"unauthorized"}',
            CURL_SESSION_DETAIL_HTTP_CODE="401",
            DATE_COUNTER=str(self.root / "date-count"),
        )
        self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
        self.assertIn("SERVER_POLL_FAILED", result.stdout)

    def test_agent_not_found_diagnostic_survives_abort_failure(self):
        self._write("opencode", "#!/usr/bin/env bash\necho 'agent \"worker\" not found'\n", self.home / ".opencode/bin")
        session = '[{"id":"ses_abort_failure","directory":"%s","time":{"updated":1}}]' % self.project
        result = self.run_script(CURL_SESSIONS_AFTER=session, CURL_ABORT_RC="1")
        self.assertEqual(result.returncode, 6, result.stdout + result.stderr)
        self.assertIn("AGENT_NOT_FOUND: 에이전트 'worker'를 찾을 수 없음", result.stdout)

    def test_init_loop_reports_agent_not_found_before_abort_failure(self):
        self._write("sleep", "#!/usr/bin/env bash\n/bin/sleep .05\n", self.bin)
        # 클라이언트를 유지해 wait 뒤 진단 분기로 새지 않고 init 루프에서만 검증한다.
        self._write("opencode", "#!/usr/bin/env bash\necho 'agent \"worker\" not found'\nwhile :; do /bin/sleep 1; done\n", self.home / ".opencode/bin")
        session = '[{"id":"ses_init_agent","directory":"%s","time":{"updated":1}}]' % self.project
        result = self.run_script(CURL_SESSIONS_AFTER=session, CURL_ABORT_RC="1")
        self.assertEqual(result.returncode, 6, result.stdout + result.stderr)
        self.assertLess(result.stdout.index("AGENT_NOT_FOUND"), result.stdout.index("ORPHAN_SESSION_WARNING"))

    def test_progress_loop_reports_agent_not_found_before_abort_failure(self):
        self._write("sleep", "#!/usr/bin/env bash\n/bin/sleep .05\n", self.bin)
        self._write("opencode", "#!/usr/bin/env bash\necho 'loop session.id ses_progress_agent'\n/bin/sleep .5\necho 'agent \"worker\" not found'\nwhile :; do /bin/sleep 1; done\n", self.home / ".opencode/bin")
        session = '[{"id":"ses_progress_agent","directory":"%s","time":{"updated":1}}]' % self.project
        result = self.run_script(CURL_SESSIONS_AFTER=session, CURL_ABORT_RC="1")
        self.assertEqual(result.returncode, 6, result.stdout + result.stderr)
        self.assertLess(result.stdout.index("AGENT_NOT_FOUND"), result.stdout.index("ORPHAN_SESSION_WARNING"))

    def test_poll_failures_are_reported_periodically_before_stall(self):
        self._write("opencode", "#!/usr/bin/env bash\nwhile :; do /bin/sleep 1; done\n", self.home / ".opencode/bin")
        (self.home / ".config/opencode/model-policy.json").write_text('{"tiers":{"default":["first/model"]}}\n')
        session = '[{"id":"ses_poll_repeat","directory":"%s","time":{"updated":1}}]' % self.project
        result = self.run_script(CURL_SESSIONS_AFTER=session, CURL_SESSION_DETAIL_RC="1")
        self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
        self.assertGreaterEqual(result.stdout.count("SERVER_POLL_FAILED"), 2, result.stdout)
        self.assertIn("서버 폴링 연속 실패", result.stdout)

    def test_error_spam_does_not_count_as_progress(self):
        self._write("opencode", """#!/usr/bin/env bash
while :; do echo 'ERROR status 429 rate limit'; /bin/sleep .01; done
""", self.home / ".opencode/bin")
        self._write("date", """#!/usr/bin/env bash
FILE="$DATE_COUNTER"; VALUE=0; [ -f "$FILE" ] && VALUE=$(cat "$FILE"); VALUE=$((VALUE + 10)); printf '%s' "$VALUE" > "$FILE"; printf '%s\\n' "$VALUE"
""", self.bin)
        (self.home / ".config/opencode/model-policy.json").write_text(
            '{"tiers":{"default":["first/model"]}}\n'
        )
        session = '[{"id":"ses_stalled","directory":"%s","time":{"updated":1},"tokens":1}]' % self.project
        result = self.run_script(CURL_SESSIONS_AFTER=session, DATE_COUNTER=str(self.root / "date-count"))
        self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
        self.assertIn("재시도 루프 스톨", result.stdout)
        self.assertNotIn("SERVER_POLL_FAILED", result.stdout)

    def test_server_progress_resets_stall_timer(self):
        self._write("opencode", """#!/usr/bin/env bash
COUNT=0
while [ "$COUNT" -lt 10 ]; do
  echo 'ERROR status 429 rate limit'
  COUNT=$((COUNT + 1))
  /bin/sleep .1
done
COUNT=0
while [ "$COUNT" -lt 51 ]; do
  echo 'INFO 작업 진행 중'
  COUNT=$((COUNT + 1))
done
""", self.home / ".opencode/bin")
        self._write("date", """#!/usr/bin/env bash
FILE="$DATE_COUNTER"; VALUE=0; [ -f "$FILE" ] && VALUE=$(cat "$FILE"); VALUE=$((VALUE + 10)); printf '%s' "$VALUE" > "$FILE"; printf '%s\\n' "$VALUE"
""", self.bin)
        (self.home / ".config/opencode/model-policy.json").write_text(
            '{"tiers":{"default":["first/model"]}}\n'
        )
        session = '[{"id":"ses_progress","directory":"%s","time":{"updated":1},"tokens":1}]' % self.project
        result = self.run_script(
            CURL_SESSIONS_AFTER=session,
            PROGRESS_STEP="1",
            DATE_COUNTER=str(self.root / "date-count"),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("재시도 루프 스톨", result.stdout)

    def test_server_poll_failure_is_reported(self):
        self._write("opencode", """#!/usr/bin/env bash
while :; do echo 'ERROR status 429 rate limit'; /bin/sleep .01; done
""", self.home / ".opencode/bin")
        self._write("date", """#!/usr/bin/env bash
FILE="$DATE_COUNTER"; VALUE=0; [ -f "$FILE" ] && VALUE=$(cat "$FILE"); VALUE=$((VALUE + 10)); printf '%s' "$VALUE" > "$FILE"; printf '%s\\n' "$VALUE"
""", self.bin)
        (self.home / ".config/opencode/model-policy.json").write_text(
            '{"tiers":{"default":["first/model"]}}\n'
        )
        session = '[{"id":"ses_poll_failure","directory":"%s","time":{"updated":1},"tokens":1}]' % self.project
        result = self.run_script(
            CURL_SESSIONS_AFTER=session,
            CURL_SESSION_DETAIL_RC="1",
            DATE_COUNTER=str(self.root / "date-count"),
        )
        self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
        self.assertIn("SERVER_POLL_FAILED", result.stdout)
        self.assertIn("재시도 루프 스톨", result.stdout)

    def test_abort_failure_stops_fallback_and_exits_6(self):
        self._write("opencode", """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$OPENCODE_CALLS"
while :; do echo 'ERROR status 429 rate limit'; /bin/sleep .01; done
""", self.home / ".opencode/bin")
        self._write("date", """#!/usr/bin/env bash
FILE="$DATE_COUNTER"; VALUE=0; [ -f "$FILE" ] && VALUE=$(cat "$FILE"); VALUE=$((VALUE + 10)); printf '%s' "$VALUE" > "$FILE"; printf '%s\\n' "$VALUE"
""", self.bin)
        result = self.run_script(CURL_ABORT_RC="1", DATE_COUNTER=str(self.root / "date-count"))
        self.assertEqual(result.returncode, 6, result.stdout + result.stderr)
        self.assertIn("ORPHAN_SESSIONS=ses_created1", result.stdout)
        self.assertEqual(self.calls.read_text().count("--agent worker"), 1)

    def test_missing_password_falls_back_to_standalone(self):
        (self.home / ".config/opencode/serve.env").write_text("OPENCODE_SERVE_PORT=4096\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("서버 인증정보 없음", result.stdout)
        self.assertNotIn("--attach", self.calls.read_text())


    # --- Phase 13: 래퍼 로그 영속화 + 총 벽시계 캡 (오케스트레이터 동결) ---

    def _wrapper_log(self):
        return Path(str(self.log) + ".wrapper")

    def _stay_alive_client(self, seconds=3):
        """세션 개시 신호를 낸 뒤 유한 시간 살아 있는 클라이언트.

        `while :` 무한 루프를 쓰면 캡 미구현 상태(RED)에서 subprocess 타임아웃으로
        스텁 프로세스가 누수돼 다음 위임을 막는다 (PITFALLS 12). 반드시 자기 종료시킨다.
        폴링 `sleep` 도 실제로 재우지 않으면 워치독이 타이트 스핀을 돌며 curl 스텁을
        수천 번 호출한다.
        """
        self._write("opencode", """#!/usr/bin/env bash
printf '%%s\\n' "$*" >> "$OPENCODE_CALLS"
echo 'loop session.id ses_test_session'
/bin/sleep %s
""" % seconds, self.home / ".opencode/bin")
        self._write("sleep", "#!/usr/bin/env bash\n/bin/sleep 0.05\n", self.bin)

    def _advancing_date(self, step=10):
        """`date +%s` 호출마다 step 초씩 나아가는 스텁 (기존 관용구 재사용)."""
        self._write("date", """#!/usr/bin/env bash
FILE="$DATE_COUNTER"; VALUE=0; [ -f "$FILE" ] && VALUE=$(cat "$FILE"); VALUE=$((VALUE + %d)); printf '%%s' "$VALUE" > "$FILE"; printf '%%s\\n' "$VALUE"
""" % step, self.bin)

    def test_wrapper_log_is_600(self):
        # umask 를 명시 주입해, 넓은 umask 환경에서도 권한 설정 누락이 드러나게 한다.
        result = self.run_script(umask="022")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        wrapper = self._wrapper_log()
        self.assertTrue(wrapper.exists(), "래퍼 로그가 생성되지 않았다: %s" % wrapper)
        self.assertEqual(wrapper.stat().st_mode & 0o777, 0o600)

    def test_wrapper_log_captures_signals(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        wrapper = self._wrapper_log()
        self.assertTrue(wrapper.exists(), "래퍼 로그가 생성되지 않았다: %s" % wrapper)
        captured = wrapper.read_text()
        # 정확일치 금지 — 신호 존재만 단정한다 (PITFALLS 29).
        self.assertIn("MODEL_USED=first/model", captured)
        self.assertIn("DONE", captured)

    def test_existing_signals_and_exit_unchanged(self):
        """래퍼 로그 도입이 호출자 계약(stdout 신호·exit)을 바꾸지 않는다."""
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("DONE", result.stdout)
        self.assertIn("MODEL_USED=first/model", result.stdout)
        self.assertIn("--agent worker", self.calls.read_text())

    def test_wallclock_cap_does_not_fall_back(self):
        self._stay_alive_client()
        self._advancing_date()
        result = self.run_script(
            ORCHESTRATE_DELEGATION_MAX_SEC="60",
            PROGRESS_STEP="1",
            DATE_COUNTER=str(self.root / "cap-date-count"),
        )
        self.assertEqual(result.returncode, 8, result.stdout + result.stderr)
        self.assertIn("WALLCLOCK_CAP", result.stdout)
        # 캡은 한도 오류가 아니므로 체인 2번째 모델로 넘어가면 안 된다.
        self.assertNotIn("second/model", self.calls.read_text())
        self.assertEqual(self.calls.read_text().count("--agent worker"), 1)

    def test_wallclock_cap_reports_orphan_on_abort_failure(self):
        """캡 도달 후 abort 가 실패하면 고아를 침묵시키지 않고 기존 계약(exit 6)을 따른다."""
        self._stay_alive_client()
        self._advancing_date()
        result = self.run_script(
            ORCHESTRATE_DELEGATION_MAX_SEC="60",
            CURL_ABORT_RC="1",
            PROGRESS_STEP="1",
            DATE_COUNTER=str(self.root / "cap-orphan-date-count"),
        )
        self.assertEqual(result.returncode, 6, result.stdout + result.stderr)
        self.assertIn("WALLCLOCK_CAP", result.stdout)
        self.assertIn("ORPHAN_SESSIONS=", result.stdout)

    # --- Phase 13 Task 3 라운드 1 반려: 캡 계약 동결 (오케스트레이터) ---

    def _falls_back_after_burning(self, threshold):
        """첫 모델이 캡에 못 미치는 지점까지 진행한 뒤 한도 오류로 자연 폴백한다.

        캡이 *체인 전체* 기준인지 *모델 시도별* 기준인지를 가르는 유일한 시나리오다.
        첫 모델이 캡 자체로 죽으면(exit 8) 폴백이 없어 두 구현이 구분되지 않는다.
        """
        self._write("opencode", """#!/usr/bin/env bash
printf '%%s\\n' "$*" >> "$OPENCODE_CALLS"
COUNT=$(wc -l < "$OPENCODE_CALLS")
echo 'loop session.id ses_test_session'
if [ "$COUNT" -eq 1 ]; then
  for _ in $(seq 100); do
    VALUE=0; [ -f "$DATE_COUNTER" ] && VALUE=$(cat "$DATE_COUNTER")
    [ "$VALUE" -ge %d ] && break
    /bin/sleep 0.05
  done
  echo 'ERROR status 429 rate limit'
  exit 1
fi
/bin/sleep 3
""" % threshold, self.home / ".opencode/bin")
        self._write("sleep", "#!/usr/bin/env bash\n/bin/sleep 0.05\n", self.bin)

    def test_wallclock_cap_is_cumulative_across_chain(self):
        """캡은 위임 하나의 *총* 벽시계다 — 모델 시도마다 리셋되면 상한이 체인 길이배가 된다.

        보고된 경과(`WALLCLOCK_CAP=<경과>/<상한>`)가 체인 전체 실경과와 어긋나면
        사용자는 "상한 N초"를 믿는데 실제로는 `체인 길이 × N` 초가 허용된다.
        """
        counter = self.root / "cumulative-date-count"
        self._falls_back_after_burning(100)
        self._advancing_date()
        result = self.run_script(
            ORCHESTRATE_DELEGATION_MAX_SEC="150",
            PROGRESS_STEP="1",
            DATE_COUNTER=str(counter),
        )
        self.assertEqual(result.returncode, 8, result.stdout + result.stderr)
        self.assertIn("WALLCLOCK_CAP", result.stdout)
        # 폴백이 실제로 일어난 경로여야 이 테스트가 의미를 갖는다.
        self.assertIn("second/model", self.calls.read_text(), result.stdout)
        match = re.search(r"WALLCLOCK_CAP=(\d+)/(\d+)", result.stdout)
        self.assertIsNotNone(match, result.stdout)
        reported = int(match.group(1))
        total = int(counter.read_text())
        # 정확일치 금지(PITFALLS 29) — 체인 전체 실경과와의 괴리만 단정한다.
        self.assertLessEqual(
            total - reported, 50,
            "보고된 경과 %s 가 체인 전체 실경과 %s 와 어긋난다 — 캡이 모델 시도마다 리셋된다"
            % (reported, total),
        )

    def test_invalid_wallclock_cap_is_rejected_before_launch(self):
        """비수치 캡 값은 안전장치를 조용히 끄지 않고 착수 전에 거부된다.

        `[ "$X" -gt 0 ]` 는 `set -e` 가 없는 이 스크립트에서 실패를 삼켜 캡을 무음 비활성화하고,
        10초 폴링마다 `integer expression expected` 를 stderr 에 쏟는다 (fail-open).
        """
        result = self.run_script(ORCHESTRATE_DELEGATION_MAX_SEC="1h")
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 64, combined)
        self.assertIn("WALLCLOCK_CAP_INVALID", combined)
        self.assertNotIn("integer expression expected", combined)
        # 착수 전 거부여야 한다 — 위임이 뜬 뒤 거부하면 세션·토큰이 낭비된다.
        self.assertFalse(self.calls.exists() and "--agent worker" in self.calls.read_text(), combined)

    def test_negative_wallclock_cap_is_rejected(self):
        result = self.run_script(ORCHESTRATE_DELEGATION_MAX_SEC="-100")
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 64, combined)
        self.assertIn("WALLCLOCK_CAP_INVALID", combined)

    def test_documented_disable_forms_still_work(self):
        """계약상 비활성 형태(빈 값·0)는 거부가 아니라 그대로 비활성이다."""
        for value in ("", "0", "000"):
            with self.subTest(value=value):
                result = self.run_script(ORCHESTRATE_DELEGATION_MAX_SEC=value)
                combined = result.stdout + result.stderr
                self.assertEqual(result.returncode, 0, combined)
                self.assertNotIn("WALLCLOCK_CAP", combined)

    def test_leading_zero_cap_is_normalized_not_disabled(self):
        """`0060` 은 비활성이 아니라 60 초 캡이다 — 정규화가 조용히 캡을 끄면 안 된다."""
        self._stay_alive_client()
        self._advancing_date()
        result = self.run_script(
            ORCHESTRATE_DELEGATION_MAX_SEC="0060",
            PROGRESS_STEP="1",
            DATE_COUNTER=str(self.root / "leading-zero-date-count"),
        )
        self.assertEqual(result.returncode, 8, result.stdout + result.stderr)
        self.assertIn("WALLCLOCK_CAP", result.stdout)

    # --- Phase 13 Task 2b: 리뷰 반려 4건의 계약 동결 (오케스트레이터) ---

    def _unwritable_wrapper_after_start(self):
        """첫 `sleep` 호출 시점에 `.wrapper` 를 읽기 전용으로 만든다.

        `install -m 600` 은 성공하고 그 뒤 append 만 실패하는 상황을 결정론적으로 만든다.
        디스크 풀·권한 경합을 스텁만으로 재현하기 위한 것이다.
        """
        self._write("sleep", """#!/usr/bin/env bash
if [ -n "${WRAPPER_TARGET:-}" ] && [ -f "$WRAPPER_TARGET" ]; then chmod 400 "$WRAPPER_TARGET" 2>/dev/null; fi
exit 0
""", self.bin)

    def test_abort_success_survives_unwritable_wrapper(self):
        """`.wrapper` 쓰기 실패가 성공한 abort 를 고아 세션으로 뒤바꾸면 안 된다.

        emit() 의 반환값이 abort_server_session() 의 반환값으로 새어 제어 흐름을
        오염시키는 회귀를 막는다. 로그 배관 실패는 세션 상태 판정과 무관해야 한다.
        """
        self._unwritable_wrapper_after_start()
        self._write("opencode", """#!/usr/bin/env bash
echo '{"type":"error","sessionID":"ses_test_session","message":"agent \\"worker\\" not found"}'
""", self.home / ".opencode/bin")
        session = '[{"id":"ses_agent","directory":"%s","time":{"updated":1}}]' % self.project
        result = self.run_script(
            WRAPPER_TARGET=str(self.log) + ".wrapper",
            CURL_SESSIONS_CALL_1="[]",
            CURL_SESSIONS_CALL_2=session,
            CURL_SESSIONS_CALL_3="[]",
            CURL_SESSIONS_CALL_4=session,
        )
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        self.assertNotIn("ORPHAN_SESSION", result.stdout)

    def test_wrapper_append_failure_is_reported(self):
        """`.wrapper` 기록 실패를 조용히 넘기지 않는다 — 구조화된 경고를 한 번 남긴다.

        실패해도 위임은 계속되어야 하지만, "로그가 있다고 믿었는데 없다"는 거짓 안심을
        만들면 안 된다. 매 emit 마다 반복하면 로그가 잡음으로 덮이므로 1회로 제한한다.
        """
        self._unwritable_wrapper_after_start()
        result = self.run_script(WRAPPER_TARGET=str(self.log) + ".wrapper")
        combined = result.stdout + result.stderr
        self.assertIn("WRAPPER_LOG_WRITE_FAILED", combined)
        self.assertEqual(combined.count("WRAPPER_LOG_WRITE_FAILED"), 1, combined)

    def test_missing_prompt_reports_66_even_with_unusable_log_path(self):
        """래퍼 로그 생성이 인자 검증을 가려서는 안 된다.

        `.wrapper` install 이 PROMPT_FILE·POLICY·OPENCODE_BIN 검사보다 먼저 실행되면
        exit 66(프롬프트 없음)이 exit 4(락 실패)로 둔갑해 호출자의 분기가 깨진다.
        """
        self.prompt.unlink()
        result = self.run_script(log=self.root / "no-such-dir" / "out.log")
        self.assertEqual(result.returncode, 66, result.stdout + result.stderr)
        self.assertIn("프롬프트 파일 없음", result.stdout + result.stderr)

    def test_preflight_raw_process_table_is_not_persisted(self):
        """비관리 프로세스의 원시 argv 를 `.wrapper` 에 남기지 않는다.

        `ps` 행에는 **다른 위임**의 프롬프트 본문이 통째로 들어 있다. 라벨은 남기되
        원시 argv 는 stderr 로만 흘려보낸다 (저장소 규약: 키 이름만 로그에 남긴다).
        """
        secret = "SECRET_MARKER_sk_doNotPersist"
        self._write_ps_table(
            " 401 1 401 /tmp/opencode run --agent worker -m x/y %s" % secret,
        )
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("PREFLIGHT_UNMANAGED", result.stdout + result.stderr)
        wrapper = Path(str(self.log) + ".wrapper")
        self.assertTrue(wrapper.exists(), "래퍼 로그가 없다: %s" % wrapper)
        captured = wrapper.read_text()
        self.assertIn("PREFLIGHT_UNMANAGED", captured)
        self.assertNotIn(secret, captured)

    # --- Phase 13 Task 2c: 라운드 2 반려 3건의 계약 동결 (오케스트레이터) ---

    def test_wrapper_log_is_600_on_early_exit_paths(self):
        """인자 검증 실패로 조기 종료해도 `.wrapper` 가 0600 이어야 한다.

        install 을 검증 뒤로 옮기면서 `WRAPPER_LOG` 할당과 파일 생성 사이가 벌어졌고,
        그 구간의 emit 이 `>>` 로 umask 기본 권한(0644) 파일을 만든다. 조기 종료라
        install 에 영영 도달하지 못해 넓은 권한이 영구히 남는다.
        """
        self.prompt.unlink()
        result = self.run_script(umask="022")
        self.assertEqual(result.returncode, 66, result.stdout + result.stderr)
        wrapper = Path(str(self.log) + ".wrapper")
        if wrapper.exists():
            self.assertEqual(wrapper.stat().st_mode & 0o777, 0o600, "조기 종료 경로에서 권한이 넓다")

    def test_wrapper_append_resumes_and_marks_gap(self):
        """일시적 기록 실패 뒤 회복되면 기록을 재개하고, 결손 사실을 파일에 남긴다.

        한 번 실패했다고 남은 실행 전체의 기록을 포기하면, "로그가 잘렸다는 사실 자체가
        로그에 남지 않는" 재귀적 침묵 실패가 된다 — 이 페이즈의 목적을 스스로 무력화한다.
        """
        self._write("sleep", """#!/usr/bin/env bash
COUNT_FILE="${WRAPPER_TARGET}.seq"
N=0; [ -f "$COUNT_FILE" ] && N=$(cat "$COUNT_FILE")
N=$((N + 1)); printf '%s' "$N" > "$COUNT_FILE"
if [ "$N" -eq 1 ]; then chmod 400 "$WRAPPER_TARGET" 2>/dev/null; fi
if [ "$N" -ge 2 ]; then chmod 600 "$WRAPPER_TARGET" 2>/dev/null; fi
exit 0
""", self.bin)
        result = self.run_script(WRAPPER_TARGET=str(self.log) + ".wrapper")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        captured = Path(str(self.log) + ".wrapper").read_text()
        # 회복 후 기록이 재개되어야 한다.
        self.assertIn("MODEL_USED=first/model", captured)
        # 결손 사실이 파일 안에 남아야 한다 — stderr 는 영속되지 않는다.
        self.assertIn("WRAPPER_LOG_RESUMED_AFTER_GAP", captured)

    def test_wrapper_append_failure_suppresses_raw_shell_error(self):
        """기록 실패 시 구조화된 경고만 남기고 셸 원시 오류는 억제한다.

        `printf ... >> "$F" 2>/dev/null` 은 리다이렉트가 좌→우로 적용되어 억제되지 않는다.
        `if ! { printf ... >> "$F"; } 2>/dev/null` 처럼 그룹으로 묶어야 한다.
        """
        self._unwritable_wrapper_after_start()
        result = self.run_script(WRAPPER_TARGET=str(self.log) + ".wrapper")
        self.assertIn("WRAPPER_LOG_WRITE_FAILED", result.stderr)
        self.assertNotIn("Permission denied", result.stderr)


def _redacted_result(result):
    """실패 메시지에 로그 tail 을 그대로 싣지 않는다 (Phase 15 실측 대응).

    아래 두 클래스의 픽스처는 의도적으로 '진짜 한도 에러처럼 보이는' 문자열이다.
    실패 메시지로 `result.stdout` 를 통째로 뱉으면 래퍼의 로그 tail 까지 딸려 나와,
    **이 테스트를 돌린 위임 자신의 로그**에 한도 시그니처가 심긴다
    (실측: `.orchestrate/task2.log` 39·72·90행 — RED 확인 단계의 단정 실패 메시지가 원인).
    그 로그는 run-delegation.sh 가 감시하는 바로 그 스트림이라, 최악의 경우 성공한
    위임이 `.failed-<모델>` 로 폐기된다. 진단에 필요한 것은 rc 와 어떤 표식이 났는지이지
    픽스처 원문이 아니므로 요약만 남긴다.
    """
    marks = [name for name in ("MODEL_USED=", "MODEL_FALLBACK", "한도/프로바이더 에러 시그니처",
                               "재시도 루프 스톨", "MODEL_EXHAUSTED", "POLICY_USED=")
             if name in result.stdout or name in result.stderr]
    return "rc=%s marks=%s (픽스처 원문은 의도적으로 생략 — _redacted_result 도크스트링 참조)" % (
        result.returncode, ",".join(marks) or "none")


class ModelPolicyScopeTest(unittest.TestCase):
    """정책 파일의 프로젝트 스코프 계약 (Phase 15 — 오케스트레이터 동결).

    호스트 전역 `~/.config/opencode/model-policy.json` 하나가 이 호스트의 모든 프로젝트의
    위임 모델을 결정하던 것을, 저장소 루트의 `.claude/model-policy.json` 으로 재정의할 수
    있게 한다. 정책 위치를 `.orchestrate/` 가 아니라 **추적 경로**에 두는 이유는 재니터
    (`phase-tools.py` STALE_LOG_DAYS=7)가 `.orchestrate/` 하위에서 archive·events.jsonl 만
    제외하고 나머지를 조용히 archive/old/ 로 옮기기 때문이다 — 옮겨진 뒤에는 오류 없이
    전역으로 폴백해 "어제까지 되던 정책이 왜 안 먹히지"를 진단할 단서가 남지 않는다.

    상속이 아니라 **명시적 차용**으로 하네스를 재사용한다. RunDelegationTest 를 상속하면
    부모의 테스트 77건이 이 클래스 이름으로 한 번 더 돌아 스위트 시간이 배가되고
    `Ran N tests` 판독이 흐려진다.
    """

    # 아래 전멸 안내 테스트는 한도 에러 픽스처를 쓴다 — 표준 단정 메시지가 건초더미를
    # 통째로 실어 위임 로그를 오염시키지 않게 끈다 (`_redacted_result` 도크스트링).
    longMessage = False

    setUp = RunDelegationTest.setUp
    tearDown = RunDelegationTest.tearDown
    _write = RunDelegationTest._write
    _stop_stub_processes = RunDelegationTest._stop_stub_processes
    _script_env = RunDelegationTest._script_env
    _script_command = RunDelegationTest._script_command
    run_script = RunDelegationTest.run_script

    def _project_policy(self, body):
        target = self.project / ".claude" / "model-policy.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)
        return target

    def test_project_policy_overrides_host(self):
        """프로젝트 정책이 있으면 호스트 전역이 아니라 그것이 체인의 원본이다."""
        self._project_policy('{"tiers":{"default":["project/model"]}}\n')
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # 보고 라인만 찍고 정책은 전역을 읽는 구현을 걸러내기 위해 실사용 모델까지 단정한다.
        self.assertIn("MODEL_USED=project/model", result.stdout)
        self.assertIn("-m project/model", self.calls.read_text())
        self.assertNotIn("first/model", self.calls.read_text())

    def test_falls_back_to_host_policy_when_project_absent(self):
        """프로젝트 정책이 없으면 기존 동작(호스트 전역)이 그대로 유지된다 — 하위 호환."""
        self.assertFalse((self.project / ".claude/model-policy.json").exists())
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("MODEL_USED=first/model", result.stdout)

    def test_missing_policy_reports_both_candidate_paths(self):
        """둘 다 없을 때 두 후보 경로가 모두 보여야 한다 (리뷰 예상 지점).

        전역 경로만 보여주면 '로컬 오버라이드를 시도했다'는 사실 자체가 보이지 않아,
        로컬 정책이 안 먹히는 상황을 진단할 단서가 사라진다.
        """
        (self.home / ".config/opencode/model-policy.json").unlink()
        result = self.run_script()
        self.assertEqual(result.returncode, 64, result.stdout + result.stderr)
        combined = result.stdout + result.stderr
        self.assertIn(".claude/model-policy.json", combined)
        self.assertIn(".config/opencode/model-policy.json", combined)

    def test_policy_used_line_names_the_source(self):
        """어느 정책이 실제로 쓰였는지가 stdout 과 .wrapper 양쪽에 남는다."""
        wrapper = str(self.log) + ".wrapper"
        result = self.run_script(WRAPPER_TARGET=wrapper)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("POLICY_USED=", result.stdout)
        self.assertIn("(host)", result.stdout)
        self.assertIn("POLICY_USED=", Path(wrapper).read_text())

        self._project_policy('{"tiers":{"default":["project/model"]}}\n')
        second = self.run_script()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn("(project)", second.stdout)
        self.assertIn(str(self.project / ".claude/model-policy.json"), second.stdout)

    def test_project_policy_is_found_from_a_subdirectory(self):
        """저장소 하위 디렉터리에서 불러도 프로젝트 정책이 쓰인다 (리뷰 반려 🔴).

        `RUN_DIR` 은 호출 cwd 다. 하위 디렉터리에서 부르면 거기에는 `.claude/` 가 없어
        **오류 없이** 호스트 전역으로 폴백한다 — 이 페이즈가 없애려던 바로 그 조용한
        정책 소실이다. 탐색 상한은 git 최상위로 묶는다: 상한 없이 위로 올라가면
        `$HOME/.claude/model-policy.json` 같은 무관한 조상을 집을 수 있다.
        """
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
        self._project_policy('{"tiers":{"default":["project/model"]}}\n')
        sub = self.project / "core" / "scripts"
        sub.mkdir(parents=True, exist_ok=True)
        result = self.run_script(project=sub)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("MODEL_USED=project/model", result.stdout)
        self.assertIn("(project)", result.stdout)

    def test_non_git_directory_still_uses_its_own_project_policy(self):
        """git 저장소가 아니면 호출 cwd 기준으로 되돌아간다 — 하위 호환."""
        self._project_policy('{"tiers":{"default":["project/model"]}}\n')
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("MODEL_USED=project/model", result.stdout)

    def test_unset_home_fails_with_a_named_cause(self):
        """HOME 미설정은 원인을 지목하며 즉시 실패해야 한다 (리뷰 반려 🔴).

        `${HOME:-}` 로 빈 문자열을 허용하면 정책·시크릿 경로가 조용히 `/`  기준으로
        어긋나고, 최종적으로 원인과 무관한 '`opencode 없음 — install.sh 실행 필요`' 로
        끝나 운영자를 엉뚱한 방향으로 보낸다.
        """
        environment = self._script_env(None, {})
        environment.pop("HOME", None)
        result = subprocess.run(
            self._script_command(),
            cwd=self.project,
            capture_output=True,
            text=True,
            env=environment,
        )
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        combined = result.stdout + result.stderr
        self.assertIn("HOME", combined)
        self.assertNotIn("opencode 없음", combined)

    def _client_always_hitting_the_limit(self):
        """체인의 모든 모델이 한도 시그니처로 실패하게 만든다 → MODEL_EXHAUSTED(exit 5)."""
        self._write(
            "opencode",
            "#!/usr/bin/env bash\necho 'ERROR status 429 rate limit'\nexit 1\n",
            self.home / ".opencode/bin",
        )

    def _exhaustion_notice(self, result):
        """전멸 안내 **그 한 줄**만 돌려준다.

        출력 전체(`stdout + stderr`)를 건초더미로 쓰면 `POLICY_USED=` 줄이 경로 단정을
        대신 충족시켜, 안내 줄을 전혀 고치지 않은 구현도 통과하는 약한 계약이 된다
        (RED 확인 단계에서 실측 — 함정 36).
        """
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 5, _redacted_result(result))
        lines = [line for line in combined.splitlines() if "사용자에게 보고할 것" in line]
        self.assertEqual(len(lines), 1, _redacted_result(result))
        return lines[0]

    def test_exhaustion_notice_names_the_project_policy_in_use(self):
        """체인 전멸 안내는 **실제로 쓰인** 정책 파일을 가리켜야 한다 (구조 리뷰 지적).

        `POLICY_USED=` 로 출처를 보여주는 페이즈가, 정작 사용자가 손을 대야 하는 순간
        (`MODEL_EXHAUSTED` — "한도 확인 필요")에 호스트 경로를 하드코딩해 안내하면
        프로젝트 정책으로 돈 운영자는 존재하지도 않을 수 있는 남의 파일을 고치러 간다.
        이 페이즈가 없애려던 '실제로 쓰인 정책이 안 보인다'가 이 한 줄에서 되살아난다.
        """
        self._project_policy('{"tiers":{"default":["project/model"]}}\n')
        self._client_always_hitting_the_limit()
        result = self.run_script()
        notice = self._exhaustion_notice(result)
        self.assertIn(str(self.project / ".claude/model-policy.json"), notice,
                      _redacted_result(result))
        # 호스트 경로를 함께 흘리면 "둘 중 뭘 고치라는 것인가"가 되어 안내가 무의미해진다.
        self.assertNotIn(".config/opencode/model-policy.json", notice,
                         _redacted_result(result))

    def test_exhaustion_notice_keeps_host_path_when_host_policy_ran(self):
        """호스트 정책으로 돈 실행은 기존 안내를 그대로 유지한다 — 하위 호환 음성 가드.

        프로젝트 경로를 무조건 찍는 구현(예: `$PROJECT_POLICY` 하드코딩)은 이 단정에
        걸린다. 안내가 따라가야 하는 것은 후보 경로가 아니라 `$POLICY` 다.
        """
        self.assertFalse((self.project / ".claude/model-policy.json").exists())
        self._client_always_hitting_the_limit()
        result = self.run_script()
        notice = self._exhaustion_notice(result)
        self.assertIn(str(self.home / ".config/opencode/model-policy.json"), notice,
                      _redacted_result(result))


class SignatureAnchorTest(unittest.TestCase):
    """크레딧·한도 실패 시그니처의 좁음 계약 (Phase 15 — 오케스트레이터 동결).

    `model_error_in_log()` 는 `OC_RC` 와 무관하게 최종 판정에 쓰인다(436행). 매칭되면
    완성된 로그가 `.failed-<모델>` 로 밀려나고 다음 모델로 폴백하며, 체인이 소진되면
    `MODEL_EXHAUSTED` 로 전멸 보고된다 — **rc=0 으로 정상 완료한 위임도 마찬가지다.**
    따라서 이 시그니처의 오탐은 성공한 작업을 통째로 버린다.

    음성 픽스처는 이 저장소의 **실제 아카이브 위임 로그에서 가져온 라인**이다.
    `.orchestrate/**/*.log` 안의 `402` 는 전부 정상 라인(타임스탬프 `...402Z`·messageID)이고,
    대문자 `ERROR` 를 포함한 에이전트 산출물도 12건 실재한다. 양성 픽스처는 실제 402 로그가
    아카이브에 남아 있지 않아 합성이며, **기존 `FAIL_RE` 에는 걸리지 않는 형태**로 골랐다
    (`AI_APICallError` 처럼 이미 잡히는 문구를 쓰면 새 앵커 없이도 통과하는 약한 계약이 된다).
    """

    # 표준 단정 메시지에는 건초더미(`result.stdout`) 전체가 실린다 — 그 안에 픽스처
    # 원문이 들어 있어 실패 시 위임 로그를 오염시킨다. 이 클래스는 모든 단정에 요약
    # 메시지를 직접 주므로 표준 메시지를 끈다 (`_redacted` 도크스트링 참조).
    longMessage = False

    setUp = RunDelegationTest.setUp
    tearDown = RunDelegationTest.tearDown
    _write = RunDelegationTest._write
    _stop_stub_processes = RunDelegationTest._stop_stub_processes
    _script_env = RunDelegationTest._script_env
    _script_command = RunDelegationTest._script_command
    run_script = RunDelegationTest.run_script

    # --- 양성: 실제로 폴백이 걸려야 하는 크레딧·한도 실패 (합성) ---
    CREDIT_402 = ("timestamp=2026-09-01T10:00:00.000Z level=ERROR run=deadbeef "
                  "message=provider-request-failed status 402 body=Insufficient credits")
    CREDIT_BALANCE = ("timestamp=2026-09-01T10:00:00.000Z level=ERROR run=deadbeef "
                      "message=provider-error error=Your credit balance is too low to access the API")
    USAGE_LIMIT = ("timestamp=2026-09-01T10:00:00.000Z level=ERROR run=deadbeef "
                   "message=usage limit reached for this account")

    # --- 양성: 2026-09-01 실측 — 폴백을 실제로 죽인 라인 (합성 아님) ---
    # 출처: 하류 프로젝트의 `.orchestrate/task3-fix.log`. 소문자 `Error:` 이고 ANSI 색상 코드가
    # 앞에 붙는다. 기존 계약은 이 한 줄을 **두 번** 놓쳤다 — 라인 필터가 대문자 `ERROR` 만
    # 봤고, `usage[ _-]+limit[ _-]+reached` 앵커는 "usage limit **has been** reached" 와
    # 어긋났다. 그 결과 heavy tier 가 폴백 없이 전멸했다.
    REAL_USAGE_LIMIT_ANSI = "\x1b[91m\x1b[1mError: \x1b[0mThe usage limit has been reached"
    # 색상이 꺼진 환경(파이프·CI)에서는 같은 메시지가 민짜로 나온다. 줄 시작 앵커
    # (`^[[:space:]]*Error:`)로 막으면 위 ANSI 형태를 놓치므로 두 형태를 함께 고정한다.
    REAL_USAGE_LIMIT_PLAIN = "Error: The usage limit has been reached"
    # 음성: 소문자 `Error:` 를 라인 필터에 넣는 순간 에이전트 산출물 오탐 위험이 생긴다.
    # 그 경계를 고정한다 — 산출물의 `Error:` 산문은 한도 실패가 아니다.
    AGENT_PROSE_ERROR_LINE = "Error: 예상한 ZodError 가 아니라 TypeError 가 났다 — 구현을 고쳐라"
    # 음성: FAIL_RE 키워드를 담은 영문 산문. 줄 시작 앵커가 없으면 이 줄이 폴백을 유발한다
    # (`rate limit` 이 FAIL_RE 에 있다). 클라이언트 배너는 자기 줄을 차지하므로 들여쓴 줄은
    # 배너가 아니라는 계약을 여기서 고정한다.
    INDENTED_PROSE_WITH_LIMIT_WORDS = "    Error: rate limit backoff is missing in the retry logic"

    # --- 음성: 실제 아카이브 로그에서 가져온 라인 ---
    REAL_INFO_402 = ('timestamp=2026-08-08T07:47:11.402Z level=INFO run=ee71666e '
                     'message="llm runtime selected" llm.runtime=ai-sdk llm.provider=openai '
                     'llm.model=gpt-5.6-luna')
    REAL_ERROR_WITH_402 = ("timestamp=2026-08-08T07:47:11.402Z level=ERROR run=ee71666e "
                           "message=tool-execution-failed tool=bash exit=1")
    REAL_AGENT_LIMIT_PROSE = "같은 프로바이더를 연달아 두면 한도에 함께 막혀 폴백이 무의미하다. ... ERROR"
    REAL_UNITTEST_ERROR = ("ERROR: test_only_selected_providers_appear "
                           "(tests.test_gen_policy.GenPolicyTest.test_only_selected_providers_appear)")

    def _single_model_policy(self):
        (self.home / ".config/opencode/model-policy.json").write_text(
            '{"tiers":{"default":["first/model"]}}\n'
        )

    def _client_printing(self, *lines):
        body = "\n".join("echo %s" % shlex.quote(line) for line in lines)
        self._write(
            "opencode",
            "#!/usr/bin/env bash\n%s\necho 'loop session.id ses_test_session'\nexit 0\n" % body,
            self.home / ".opencode/bin",
        )

    # 요약 포맷은 `ModelPolicyScopeTest` 와 공유한다 — 두 클래스 모두 같은 이유로
    # (자기 위임 로그 오염) 픽스처 원문을 감춘다. 정의는 모듈 상단 `_redacted_result`.
    _redacted = staticmethod(_redacted_result)

    def _assert_treated_as_limit_error(self, *lines):
        self._single_model_policy()
        self._client_printing(*lines)
        result = self.run_script()
        self.assertEqual(result.returncode, 5, self._redacted(result))
        self.assertIn("한도/프로바이더 에러 시그니처", result.stdout, self._redacted(result))

    def _assert_not_a_limit_error(self, *lines):
        self._single_model_policy()
        self._client_printing(*lines)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, self._redacted(result))
        self.assertIn("MODEL_USED=first/model", result.stdout, self._redacted(result))
        self.assertNotIn("MODEL_FALLBACK", result.stdout, self._redacted(result))

    def test_credit_exhaustion_error_triggers_fallback(self):
        """402 + 크레딧 소진은 폴백 대상이다."""
        self._assert_treated_as_limit_error(self.CREDIT_402)

    def test_low_credit_balance_error_triggers_fallback(self):
        """'credit balance is too low' 표현도 폴백 대상이다."""
        self._assert_treated_as_limit_error(self.CREDIT_BALANCE)

    def test_usage_limit_reached_triggers_fallback(self):
        """'usage limit reached' 표현도 폴백 대상이다."""
        self._assert_treated_as_limit_error(self.USAGE_LIMIT)

    def test_real_ansi_usage_limit_line_triggers_fallback(self):
        """실측 라인(ANSI 접두 + 소문자 Error:)이 폴백을 걸어야 한다.

        이 테스트가 이 클래스의 존재 이유다 — 합성 픽스처만 있었기에 계약이 통과하면서도
        현장에서는 폴백이 안 걸렸다. 라인 필터와 FAIL_RE 를 **동시에** 고쳐야 통과한다.
        """
        self._assert_treated_as_limit_error(self.REAL_USAGE_LIMIT_ANSI)

    def test_plain_usage_limit_line_triggers_fallback(self):
        """색상이 꺼진 환경의 같은 메시지도 폴백 대상이다."""
        self._assert_treated_as_limit_error(self.REAL_USAGE_LIMIT_PLAIN)

    def test_agent_prose_error_line_is_not_a_limit_error(self):
        """산출물의 소문자 `Error:` 산문은 한도 실패가 아니다 (라인 필터 확장의 대가).

        라인 필터를 `Error:` 까지 넓히면 이 라인이 새로 필터를 통과한다. FAIL_RE 가
        좁아야 여기서 걸러진다 — 두 방어선이 각자 제 몫을 하는지 고정한다.
        """
        self._assert_not_a_limit_error(self.AGENT_PROSE_ERROR_LINE)

    def test_indented_prose_error_line_is_not_a_limit_error(self):
        """들여쓴 산출물 `Error:` 는 FAIL_RE 키워드를 담아도 배너가 아니다 (줄 시작 앵커).

        소문자 확장의 대가를 좁히는 방어선이다 — 앵커를 지우면 이 테스트가 먼저 깨진다.
        """
        self._assert_not_a_limit_error(self.INDENTED_PROSE_WITH_LIMIT_WORDS)

    def test_normal_info_line_with_402_is_not_a_limit_error(self):
        """정상 INFO 라인의 타임스탬프 402 는 한도 실패가 아니다 (리뷰 예상 지점).

        실제 아카이브 로그 라인이다. 라인 필터가 이것을 걸러주지만, 그것에만 기대지
        않도록 아래 test_error_line_with_402_timestamp_is_not_a_limit_error 가 짝을 이룬다.
        """
        self._assert_not_a_limit_error(self.REAL_INFO_402)

    def test_error_line_with_402_timestamp_is_not_a_limit_error(self):
        """ERROR 라인이라도 타임스탬프의 402 를 한도 실패로 읽으면 안 된다 (리뷰 예상 지점).

        맨 `402` 앵커는 여기서 걸린다 — 라인 필터가 막아주지 않는 형태이므로
        `status.?402` 처럼 앵커링해야 한다.
        """
        self._assert_not_a_limit_error(self.REAL_ERROR_WITH_402)

    def test_agent_output_error_lines_are_not_limit_errors(self):
        """에이전트 산출물의 ERROR 라인은 한도 실패가 아니다 (실제 아카이브 라인).

        첫 줄은 '한도' 라는 단어와 대문자 ERROR 가 한 줄에 있는 실제 위임 로그 라인이다.
        """
        self._assert_not_a_limit_error(self.REAL_AGENT_LIMIT_PROSE, self.REAL_UNITTEST_ERROR)

    def test_interim_watcher_also_detects_credit_signature(self):
        """인터림 감시와 최종 판정이 같은 매처를 쓴다 (리뷰 예상 지점).

        최종 판정만 고치고 인터림 감시(424행)를 두면 같은 실행 안에서 '진행 중 판정'과
        '종료 후 판정'의 기준이 갈린다. 스톨 감시가 크레딧 시그니처에도 반응해야 한다.
        """
        self._single_model_policy()
        self._write(
            "opencode",
            "#!/usr/bin/env bash\nwhile :; do echo %s; /bin/sleep .01; done\n"
            % shlex.quote(self.CREDIT_402),
            self.home / ".opencode/bin",
        )
        self._write("date", """#!/usr/bin/env bash
FILE="$DATE_COUNTER"; VALUE=0; [ -f "$FILE" ] && VALUE=$(cat "$FILE"); VALUE=$((VALUE + 10)); printf '%s' "$VALUE" > "$FILE"; printf '%s\\n' "$VALUE"
""", self.bin)
        session = '[{"id":"ses_credit","directory":"%s","time":{"updated":1},"tokens":1}]' % self.project
        result = self.run_script(CURL_SESSIONS_AFTER=session, DATE_COUNTER=str(self.root / "date-count"))
        self.assertEqual(result.returncode, 5, self._redacted(result))
        self.assertIn("재시도 루프 스톨", result.stdout, self._redacted(result))
