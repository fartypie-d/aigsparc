---
task: 2
status: done
---

## Task 2: 래퍼 stdout → `.wrapper` 로그 영속화

- **에이전트**: `kit-scripts`
- **모델**: `heavy` (⚠️ 도메인 — 로스터 규정)
- **대상 파일**: `core/scripts/run-delegation.sh` (1개)
- **선행**: Task 1
- **목표**: 래퍼가 stdout으로만 내보내던 진단 신호를 `$LOG_FILE.wrapper`에도 남긴다.
  폴백·락 대기·세션 abort가 사후 집계 가능해진다. **stdout 출력은 종전과 100% 동일하게 유지**한다.

### 배경 (왜 필요한가)

`MODEL_FALLBACK`·`LOCK_WAIT`·`SESSION_ABORTED`·`MODEL_USED=`가 전부 stdout으로만 나가
로그 파일에 남지 않는다. 실측 결과 8월 한 달간 폴백이 8회 발생했으나
(`.failed-*` 파일로만 역추적 가능) 어느 위임에서 왜 일어났는지 기록이 없다.

- **재사용**: `그대로 재사용 core/scripts/run-delegation.sh:231 install -m 600 /dev/null "$LOG_FILE"`
  — `.wrapper` 파일 생성도 **이 패턴 그대로** 쓴다. 새 권한 헬퍼 함수를 만들지 말 것.
  (`: > file` 뒤 `chmod` 2단계는 읽기 가능한 창을 만들므로 금지 — 주석에 이유가 있다.)

### 구현 방식 (지정)

`emit()` 함수를 도입해 기존 `echo "..."`를 대체한다:

```
emit() { printf '%s\n' "$*"; [ -n "${WRAPPER_LOG:-}" ] && printf '%s\n' "$*" >> "$WRAPPER_LOG"; }
```

**`exec > >(tee ...)` 형태의 프로세스 치환을 쓰지 말 것.** 이 스크립트는 `exec 9>` flock,
`nohup ... &` 백그라운드 자식, `wait "$OC_PID"`에 의존한다. 프로세스 치환은 이 셋을 전부
흔들 수 있고, 그 실패가 조용하다. 명시적 이중 기록이 검증도 쉽다.

- stderr로 나가는 `>&2` 출력(`PREFLIGHT_UNMANAGED`, `LOCK_TIMEOUT`, `MODEL_EXHAUSTED` 등)도
  `.wrapper`에 남긴다 — 단, **stderr 스트림 자체는 그대로 유지**한다.
- `$LOG_FILE`이 모델 폴백 시 `.failed-<slug>`로 `mv` 되는데, **`.wrapper`는 옮기지 않는다**
  (한 위임의 전체 폴백 이력이 한 파일에 남아야 한다).

### 완료 조건

1. `python3 -m unittest discover -s tests -k test_run_delegation` → Task 1이 동결한
   `test_wrapper_log_is_600`·`test_wrapper_log_captures_signals`·
   `test_existing_signals_and_exit_unchanged` **GREEN**. `Ran N tests`의 N을 보고에 포함.
2. `bash -n core/scripts/run-delegation.sh`
3. **변이 검증**: `.orchestrate/mut13-2/`에 저장소 전체를 복사하고 (`/tmp` 금지 —
   `external_directory` 자동 거부, PITFALLS 6·15), 사본에서 `emit()`의 `.wrapper` 기록 줄을
   삭제 → 위 테스트가 **FAIL**함을 확인하고 출력을 보고에 첨부한다.
   (스크립트만 복사하면 테스트가 원본을 참조해 변이가 무효다.)

### 금지

- 대상 파일 외 수정 — **특히 `tests/` 수정 금지** (오케스트레이터 동결분, PITFALLS 14)
- `git commit`·`git push`·docker 조작
- `scripts/run-delegation.sh`(심링크) 수정 — 항상 `core/scripts/`를 고친다
- stdout 신호의 문구·순서·exit 코드 변경 (호출자 계약)

## 리뷰 이력

| 라운드 | 판정 | 🔴 | 🟠 | 수정 커밋 |
|---|---|---|---|---|
| 1 | 반려 | 2 | 2 | 1daa493 (emit 반환값 분리·기록 실패 신호·검증 순서·argv 비영속) |
| 2 | 반려 | 2 | 1 | da907a8 (조기 0600·기록 재개·원시 오류 억제) |
| 3 | **SIGN OFF** | 0 | 1 | — |

라운드 3 리뷰어 3종(`bash-reviewer`·`security-reviewer`·`silent-failure-hunter`) 전원 SIGN OFF.
세 리뷰어 모두 완료 조건 3건(3종 GREEN·`bash -n`·변이 검증)을 **구현자 보고 인용이 아니라
저장소 사본에서 독자 재현**했고, 라운드 1·2 반려 7건의 재발 없음을 대응 테스트로 확인했다.

### 잔여 🟠 (Task 2 범위 밖으로 판정 — 후속)

`WRAPPER_LOG_WRITE_FAILURE_REPORTED` 가 프로세스 수명 동안 리셋되지 않는다
(`core/scripts/run-delegation.sh` emit 함수). 첫 기록 실패 이후 **별개의 두 번째 실패
에피소드**는 stderr 경고도, `.wrapper` 의 `WRAPPER_LOG_RESUMED_AFTER_GAP` 결손 마커도 남기지
않는다 — `.wrapper` 가 표식 없이 끊겨 "정상 종료된 것처럼" 보인다. 이 페이즈의 목적(사후 집계)을
정확히 무력화하는 사각지대다. 재현: silent-failure-hunter 가 독립 스크립트로 확인
(에피소드 2 의 실패 3회가 0회 보고).

수정 권고: `WRAPPER_LOG_WRITE_FAILED` 가 1→0 으로 전환되는 두 지점에서
`WRAPPER_LOG_WRITE_FAILURE_REPORTED=0` 도 함께 리셋. 같은 에피소드 내 반복은 여전히 1회 보고,
독립된 새 에피소드는 다시 1회 보고.

**위임 단독으로 완결 불가** — 다중 에피소드 계약을 명문화하는 새 동결 테스트가 필요하고
`tests/` 는 오케스트레이터 전속이다 (PITFALLS 14).

### 🟡 (정보성)

- `.wrapper` 는 emit 마다 `>>` 로 재오픈되므로 로그 디렉터리 쓰기 권한을 가진 제3자의 심링크
  교체에 노출된다. `$LOG_FILE`·`$PROMPT_FILE` 에도 원래 있던 미방어 영역이고 지시서가 지정한
  구현 스켈레톤 그대로라 신규 위험은 아니다 (security-reviewer).
- 기록 실패 시 `sleep 1` 재시도가 매 emit 을 최대 1초 블로킹할 수 있다는 점이 미문서화
  (silent-failure-hunter). 워치독 타이밍을 깨뜨리지는 않음이 실측됨.
