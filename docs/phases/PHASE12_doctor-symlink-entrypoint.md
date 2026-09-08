---
phase: 12
date: 2026-09-01
kind: task
domain: scripts, tests
status: done
commits: 75eb80c..05308ba (10개 — fix 3 · test 5 · docs 2)
cost: $33.01
compactions: 0
interventions: 1
summary: 진입점별 KIT·프로젝트 루트 해석 통일 — scripts/ 심링크와 core/scripts/ 실경로 어느 쪽으로 불러도 같은 루트가 나오게 (설치된 프로젝트 배치 불변)
---

# 작업 지시서 — 진입점별 루트 해석 통일 (2026-09-01)

> Phase 12 재개. 2026-08-17 에 RED 1건만 동결한 채 중단됐고, 그 사이 main 이 39 커밋
> 진행했다. 재개하며 리베이스하고 스코프를 **클래스 수정**으로 확장했다.

## 인터뷰 결과
- **스코프**: `kit-doctor.sh` · `docs-index.py` · `hook-selfcheck.sh` 세 스크립트의
  루트 해석을 진입점 무관하게 통일. `run-delegation.sh` 는 **제외**(아래 전제 실측 참조).
- **우선순위**: Task 1(문서에 노출된 실사용 버그) → Task 2(잠재 함정).
- **제약**: 설치된 프로젝트 배치(`<proj>/scripts/` 실파일, `core/` 없음)를 깨뜨리지 말 것.
  `tests/` 는 오케스트레이터가 동결했다 — **위임은 `tests/` 를 수정하지 않는다**(함정 14).
- **크기 등급**: standard (`kit-scripts` = ⚠️ 도메인 → 파일 수와 무관하게 최소 standard).

## 배경 — 실측된 증상

`scripts/` 는 `core/scripts/` 를 가리키는 **파일 심링크 모음**이다. 세 스크립트가 저마다
다른 규약으로 루트를 계산해, **각자 한쪽 진입점에서만 맞고 반대쪽에서 깨진다**:

| 스크립트 | 필요한 루트 | `scripts/` (문서가 안내) | `core/scripts/` (실경로) |
|---|---|---|---|
| `kit-doctor.sh` | **KIT** 루트 | ❌ `/home/jh` 로 계산 → `FAIL 매니페스트` | ✅ |
| `docs-index.py` | **프로젝트** 루트 | ✅ | ❌ `문서 디렉터리를 찾을 수 없습니다: <root>/core/docs/phases` |
| `hook-selfcheck.sh` | **프로젝트** 루트 | ✅ | ❌ `core/` 를 루트로 착각 → 훅 전부 exit 127 |

`kit-doctor.sh` 의 깨진 쪽이 **README.md·README.ko.md·docs/WORKFLOW.ko.md 에 문서화된
진입점**이라 사용자에게 실제로 노출된다. 나머지 둘의 깨진 쪽은 이 저장소 안에서만
도달 가능하고 문서화된 곳이 없다 — 실사용 결함이 아니라 잠재 함정이다.

## 전제 실측

| 전제 | 근거 | 판정 |
|---|---|---|
| 설치된 프로젝트도 `core/scripts/` 배치를 쓴다 | `lib/stamp.sh:30` `_stamp_copy_tree "$_kit/core/scripts" "$_target/scripts"` — **실파일로 복사**, `core/` 없음 | **뒤집힘** → 루트까지의 단계 수가 배치마다 다르다. `../..` 일괄 고정은 설치된 모든 프로젝트를 깨뜨린다 |
| `--doctor` 는 심링크 경로로 kit-doctor 를 부른다 | `install.sh:112` `exec bash "$KIT_DIR/core/scripts/kit-doctor.sh"` — **실경로** | 뒤집힘 → 실경로는 회귀 가드로 반드시 보존 |
| `run-delegation.sh` 도 같은 버그다 | `core/scripts/run-delegation.sh:67` `SCRIPT_DIR` 은 형제 스크립트(`opencode-serve-ctl.sh`) 참조에만 쓰이고, 형제는 두 배치 모두에 존재 | 유지(무결) → **스코프 제외** |
| `os.path.abspath` 가 심링크를 푼다 | 파이썬 표준 — `abspath` 는 정규화만, `realpath` 가 심링크를 푼다 | 뒤집힘 → `docs-index.py` 는 `realpath` 로 바꿔야 한다 |
| `tests/_install_helpers.py` 에 재사용 가능한 격리 헬퍼가 있다 | `KIT = Path(__file__).resolve().parents[1]`, `temporary_directory()`(저장소 내 스크래치) | 유지 → 동결 테스트가 그대로 재사용 |

## 해석 규약 (두 task 공통 — 이대로 구현할 것)

1. **`$0`(또는 `__file__`)의 파일 심링크를 먼저 실경로로 푼다.**
   - bash: macOS 기본 bash 3.2 호환이어야 한다 → `readlink -f` 금지, **루프**로 푼다
     (상대 링크는 링크가 있던 디렉터리 기준으로 합성, 순환 방지 상한 포함).
   - python: `os.path.abspath` → **`os.path.realpath`**.
2. **푼 뒤의 루트 계산**은 스크립트가 원하는 루트에 따라 다르다:
   - `kit-doctor.sh` → **KIT 루트** = 실경로 디렉터리의 `../..` (킷 안에서만 의미 있음).
     기존 `--kit` 오버라이드는 그대로 유지한다.
   - `docs-index.py` · `hook-selfcheck.sh` → **프로젝트 루트**, 배치 의존:
     실경로 디렉터리의 부모가 `core` 이고 그 부모가 킷이면(`core/install-manifest.tsv` 존재)
     한 단계 더 올라가고, 아니면 부모가 곧 프로젝트 루트다.
     (`core` 이름만으로 판단하지 말 것 — 프로젝트 이름이 `core` 인 경우를 오판한다.)
3. 규약을 각 파일 상단 주석 한 줄로 남긴다.

> **의도적 선택 — 공용 헬퍼를 만들지 않는다.** 심링크 해석 루프를 두 bash 스크립트에
> 인라인 중복시킨다. 헬퍼를 두면 "헬퍼를 찾으려면 먼저 경로를 풀어야 하는" 부트스트랩
> 문제가 생기고, 호출부가 2곳뿐이라 추상화 이득이 적다(YAGNI). 두 사본은 **동일한
> 형태**로 유지하고 같은 규약 주석을 단다. 구조 리뷰어가 중복을 지적하면 다음 페이즈에서
> 재검토한다.

## 동결 테스트 (오케스트레이터 작성·커밋 완료 — 위임 수정 금지)

커밋 `7852b29` + `75eb80c`. RED 3 / 회귀 가드 3, 각각 단독 실행으로 상태 확인함:

| 테스트 | 상태 | 지키는 것 |
|---|---|---|
| `test_kit_doctor.py::ManifestTest::test_symlink_entrypoint_resolves_kit_root` | 🔴 RED | Task 1 |
| `test_kit_doctor.py::ManifestTest::test_real_path_entrypoint_resolves_kit_root` | 🟢 가드 | `install.sh --doctor` 호출부 |
| `test_docs_index.py::TestDocsIndex::test_real_path_execution_finds_repository_docs` | 🔴 RED | Task 2 |
| `test_docs_index.py::TestDocsIndex::test_stamped_project_layout_still_finds_docs` | 🟢 가드 | 설치된 프로젝트 배치 |
| `test_hook_selfcheck.py::HookSelfcheckEntrypointTest::test_real_path_entrypoint_passes` | 🔴 RED | Task 2 |
| `test_hook_selfcheck.py::HookSelfcheckEntrypointTest::test_symlink_entrypoint_passes` | 🟢 가드 | 문서가 안내하는 경로 |

## 리뷰 예상 지점

| 지점 | 예상 지적 | 고정 RED |
|---|---|---|
| 두 bash 스크립트의 심링크 해석 루프 | 중복 코드 — 공용 헬퍼로 뽑아야 한다 🟠 | 위 "의도적 선택" 절에 근거 명시. 구조 리뷰어 판단에 맡김 |
| 프로젝트 루트 계산의 `core` 특수 처리 | 이름만 보고 판단하면 `core` 라는 이름의 프로젝트를 오판 🔴 | `test_stamped_project_layout_still_finds_docs` (T2) |
| bash 3.2 호환 | `readlink -f` 사용 시 macOS 에서 침묵 실패 🔴 | `bash -n` + 루프 형태 육안 확인 (T1·T2 완료 조건) |

## Task 목록

| # | 제목 | 에이전트 | 상태 | 커밋 |
|---|---|---|---|---|
| 1 | kit-doctor.sh — KIT 루트를 심링크 진입점에서도 해석 | `kit-scripts` | done | `88b9634` |
| 2 | docs-index.py · hook-selfcheck.sh — 프로젝트 루트를 배치 무관하게 해석 (+경화) | `kit-scripts` | done | `6944b8f` + 수정 라운드 |

> Task 2 는 리뷰 중 스코프가 확장됐다 — silent-failure-hunter 가 Task 1 의 해석 루프에서
> 무경고 오진단 경로 4건을 실측했고, 그 루프를 `hook-selfcheck.sh` 로 복제하기 전에
> 계약을 고치는 편이 싸다고 판단해 사용자 승인을 받아 경화를 Task 2 에 포함시켰다.

## 리뷰 결과

### Task 1 — ✅ 통과 (🔴 0)

| 리뷰어 | 판정 |
|---|---|
| `bash-reviewer` | PASS — 🔴 0 / 🟠 0 / 🟡 1 |
| `security-reviewer` | PASS — 🔴 0 / 🟠 0 / 🟡 2 (경로 봉쇄 계약 무손상, `test_kit_doctor` 31/31) |
| `silent-failure-hunter` | 🔴 0 / 🟠 4 — 무경고 오진단 경로. Task 2 로 이월해 수정 |

### Task 2 — ❌ 반려 → 수정 라운드 1회로 해소

| 리뷰어 | 판정 |
|---|---|
| `bash-reviewer` | PASS — 🔴 0 / 🟠 0 / 🟡 1 |
| `python-reviewer` | PASS — 🔴 0 / 🟠 1 |
| `silent-failure-hunter` | **🔴 4 → 반려** |

리뷰어 간 등급이 갈려(같은 마커 약화를 🟡/🟠/🔴 로) 오케스트레이터가 직접 재현해 확정했다:

| 반려 | 확정 근거 |
|---|---|
| 후행 슬래시가 해석을 조기 종료 (🔴) | `entry → "mid/"` 와 `entry2 → "mid"` 가 같은 체인인데 답이 갈렸다 — 슬래시 있으면 `<T>`, 없으면 `<T>/deep`. 오류 없이 exit 0 인 조용한 오답 |
| `scripts/` 단독을 킷 마커로 인정 (🔴) | 비킷 프로젝트가 `core/scripts/` + 최상위 `scripts/` 를 가지면 오승격. **원인은 오케스트레이터의 픽스처** — `core/install-manifest.tsv` 를 안 만들어 구현이 약한 추론에 기대게 했다 |
| 조부모 상승 실패를 무경고 스킵 (🔴) | 세 줄 위 형제 코드(`_root_parent`)는 같은 상황에서 `exit 1` 한다 — 일관성 결여 |
| `HOOK_SELFCHECK_FAIL` 계약 미준수 (🟠) | 실패인데 문서가 grep 하라는 키워드가 없어 "조용한 실패"와 구분 불가 |

### Task 2 재검증 — ✅ 통과

| 리뷰어 | 판정 |
|---|---|
| `silent-failure-hunter` (재검증) | **PASS — 🔴 0 / 🟠 0** — 반려 4건 전부 해소, 새 침묵 경로 0건 |

### 마감 구조 리뷰 (`structure-reviewer`, 페이즈 1회)

- **부채**: 마커 승격 블록 14줄이 `kit-doctor.sh`·`hook-selfcheck.sh` 에 바이트 단위로 중복.
  이 블록은 `SCRIPT_DIR` 확정 **뒤**라 부트스트랩 순환이 없어 공용 헬퍼 추출이 가능하다
  (심링크 해석 루프 쪽은 순환이 있어 중복 유지 근거가 유효 — 오케스트레이터가 두 부분을
  근거 없이 묶어 판단한 것을 리뷰가 뒤집었다). "두 사본을 동일 형태로 유지" 완화책은 이미
  어긋나 있다 — 한쪽은 함수, 다른 쪽은 인라인
- **실측 지적**: 오케스트레이터가 동결한 테스트 클래스가 `if __name__ == "__main__":` **뒤**에
  정의돼 파일 직접 실행 시 스캔에서 누락 → `05308ba` 로 가드를 파일 끝으로 이동
- **후속 제안** (다음 페이즈 후보, 우선순위 순): ① 마커 승격 블록 공용 헬퍼 추출
  ② `tests/test_kit_doctor.py` 810줄 분할 (800줄 상한 초과, 같은 페이즈에 `test_hook_selfcheck.py`
  분리 선례 있음) ③ 킷 마커 규약(`core/install-manifest.tsv` 가 킷 루트의 유일한 신호) 문서화

### 검증 총괄

- 전체 스위트 388건 중 10건 실패 = 전부 컨테이너·대시보드 = **워크트리 서브모듈 미초기화
  환경 실패**(PITFALLS 24). 메인 체크아웃에서 같은 두 파일 29건 전부 OK — 이번 diff 와 무관 확인
- `bash -n` 구문 검사·`hook-selfcheck.sh` 자가진단 통과

## 변이 검증 (`.orchestrate/mut12/`, gitignore)

| 변이 | 결과 |
|---|---|
| kit-doctor `cap` 검사 제거 | ✅ 검출 |
| docs-index `core` 마커 로직 제거 | ✅ 검출 |
| hook-selfcheck `core` 분기 제거 | ✅ 검출 (두 진입점) |
| 후행 슬래시 정규화 제거 | ✅ 검출 |
| `HOOK_SELFCHECK_FAIL` 키워드 제거 | ✅ 검출 |
| 킷 마커를 무조건 참으로 | ✅ 검출 |
| docs-index `realpath`→`abspath` | ⚪ 미검출 — **행동 불변**이라 정상 (마커 로직이 양쪽 배치를 이미 커버) |

## Task 1: kit-doctor.sh — KIT 루트를 심링크 진입점에서도 해석
- **에이전트**: `kit-scripts`
- **모델**: heavy (⚠️ 도메인 — 설치 스크립트가 사용자 홈을 건드린다)
- **대상 파일**: `core/scripts/kit-doctor.sh`
- **선행**: 없음
- **목표**: `bash scripts/kit-doctor.sh` (문서가 안내하는 진입점)로 불러도 KIT 루트가
  저장소 루트로 계산돼 `core/install-manifest.tsv` 를 찾는다. 실경로 호출은 그대로 동작한다.
- **재사용**: 개선 후 재사용 `core/scripts/kit-doctor.sh:6` `SCRIPT_DIR` 계산부 (호출부 = 같은 파일 내
  `KIT_DIR` 1곳). 새 함수·새 파일을 만들지 말 것 — 기존 3줄을 확장한다.
  `--kit` 오버라이드 로직은 이미 있으니 건드리지 말고 그대로 둔다.
- **실패 테스트**: `tests/test_kit_doctor.py::ManifestTest::test_symlink_entrypoint_resolves_kit_root`
  — 심링크 진입점에서 `FAIL 매니페스트` 가 없어야 하고, 매니페스트 항목을 실제로 점검해야 한다.
  **이미 작성·커밋돼 있다. 먼저 실행해 RED 를 눈으로 확인한 뒤 구현할 것.**
- **필독 스킬**: `plankton-code-quality`
- **필수 규칙**:
  - macOS 기본 **bash 3.2 호환** — `readlink -f`·`mapfile`·연관배열 금지. 심링크는 루프로 푼다.
  - 회귀 가드 `test_real_path_entrypoint_resolves_kit_root` 를 깨뜨리지 말 것.
  - `tests/` 수정 금지. 대상 파일 외 수정 금지. `git commit` 금지.
- **완료 조건**:
  1. `python3 -m unittest discover -s tests -k test_symlink_entrypoint_resolves_kit_root` → `Ran 1 test` + `OK`
  2. `python3 -m unittest discover -s tests -k test_real_path_entrypoint_resolves_kit_root` → `Ran 1 test` + `OK`
  3. `bash -n core/scripts/kit-doctor.sh` → 무출력

## Task 2: docs-index.py · hook-selfcheck.sh — 프로젝트 루트를 배치 무관하게 해석
- **에이전트**: `kit-scripts`
- **모델**: heavy (⚠️ 도메인)
- **대상 파일**: `core/scripts/docs-index.py`, `core/scripts/hook-selfcheck.sh`
- **선행**: 없음 (Task 1 과 독립 — 다른 파일)
- **목표**: 두 스크립트를 `scripts/` 심링크로 부르든 `core/scripts/` 실경로로 부르든 같은
  **프로젝트 루트**가 나온다. 설치된 프로젝트 배치(`<proj>/scripts/` 실파일, `core/` 없음)는
  지금과 동일하게 동작한다.
- **재사용**: 개선 후 재사용 `core/scripts/docs-index.py:33`·`:184` 의
  `Path(os.path.abspath(__file__)).parent.parent` (호출부 2곳 — **둘 다** 같이 고쳐야 한다.
  한 곳만 고치면 `docs_label` 계산이 어긋난다) + `core/scripts/hook-selfcheck.sh:5`
  `cd "$(dirname "$0")/.."` (호출부 1곳). 루트 계산을 함수로 한 번만 정의해 두 호출부가
  공유하게 할 것 — `docs-index.py` 안에서 같은 식을 두 번 쓰지 말 것.
  `grep -rn 'abspath\|realpath' core/scripts/` 로 다른 사본이 없음을 확인했다.
- **실패 테스트**:
  - `tests/test_docs_index.py::TestDocsIndex::test_real_path_execution_finds_repository_docs`
  - `tests/test_hook_selfcheck.py::HookSelfcheckEntrypointTest::test_real_path_entrypoint_passes`
  **둘 다 이미 작성·커밋돼 있다. 먼저 실행해 RED 를 확인한 뒤 구현할 것.**
- **필독 스킬**: `python-patterns`
- **필수 규칙**:
  - 프로젝트 루트 판정은 **`core` 라는 이름만으로 하지 말 것** — 킷 마커
    (`core/install-manifest.tsv` 존재)를 함께 확인한다. 이름만 보면 `core` 라는 이름의
    프로젝트를 오판한다.
  - `hook-selfcheck.sh` 는 macOS 기본 **bash 3.2 호환** (`readlink -f` 금지).
  - `docs-index.py` 의 `--docs-dir` 오버라이드 동작을 바꾸지 말 것.
  - `tests/` 수정 금지. 대상 파일 외 수정 금지. `git commit` 금지.
- **완료 조건**:
  1. `python3 -m unittest discover -s tests -k test_real_path_execution_finds_repository_docs` → `Ran 1 test` + `OK`
  2. `python3 -m unittest discover -s tests -k test_real_path_entrypoint_passes` → `Ran 1 test` + `OK`
  3. `python3 -m unittest discover -s tests -k test_stamped_project_layout_still_finds_docs` → `Ran 1 test` + `OK`
  4. `bash -n core/scripts/hook-selfcheck.sh` → 무출력

## 자동 결정 로그
(오토 모드 아님 — 해당 없음)
