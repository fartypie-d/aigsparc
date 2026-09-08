---
phase: 10
date: 2026-08-17
kind: task
domain: scripts, install, tests, docs
status: done
commits: 49a7e05..b230d8a (23개 — feat 3 · fix 4 · test 10 · docs 6)
cost: $43.85 (오케스트레이터 측 session-cost.py 실측. opencode 위임 토큰은 별도 프로바이더 한도)
compactions: 0
interventions: 5
summary: kit-doctor — 설치 자가진단(도구·CLI·전역 자산 존재·drift) + 누락 자산만 채우는 --add-missing (기존 파일 불변)
---

# 작업 지시서 — 로드맵 ② doctor·upgrade UX (2026-08-17)

로드맵 출처: `docs/superpowers/specs/2026-08-17-aigsprac-rebrand-design.md` 페이즈 ②.
근거: ruflo 감사에서 "진짜였던" 두 축 중 하나 = 설치·진단 UX. 규모 수사는 이식하지 않는다.

## 인터뷰 결과

- **스코프**: ① 통합 자가진단 스크립트 신설 (필수 도구·CLI 유무 + **전역 자산 존재 및 킷 원본 대비
  drift**) ② 진단이 참조할 **공유 매니페스트** 신설 ③ `./install.sh --doctor` 얇은 위임
  ④ 누락 자산만 채우는 `--add-missing` (기존 파일 절대 불변) ⑤ README·WORKFLOW 문서 반영.
- **범위 밖 (후속 페이즈로)**: 모델 정책·체인 진단(기존 `model-doctor.sh` 소관), 프로젝트 스캐폴드
  진단(기존 `hook-selfcheck.sh`·`adopt-project.sh` 소관), 컨테이너·MCP 상태 점검.
  → 사용자 인터뷰에서 진단 범위를 "도구·CLI + 전역 자산 존재·drift"로 한정 선택했다.
- **우선순위**: 테스트 동결(Task 1) → 진단 본체(Task 2) → install.sh 진입점(Task 3) →
  `--add-missing`(Task 4) → 문서(Task 5).
- **제약**:
  - `install.sh` 의 **복사 로직(`backup_and_copy` 호출부)은 이번 페이즈에서 손대지 않는다** —
    매니페스트는 doctor 전용 참조본이고, 불일치는 동결 테스트가 잡는다.
  - `install.sh` 는 이미 1768줄이다. 신규 코드는 `core/scripts/kit-doctor.sh` 로 분리하고
    install.sh 증가분은 플래그 파싱 + 위임 dispatch 최소량으로 제한한다.
  - `scripts/*` 는 `core/scripts/*` 심링크다 — **원본은 `core/scripts/` 에 만든다**.
  - `tests/` 는 오케스트레이터가 작성·동결한다. **위임은 `tests/` 를 수정 금지** (PITFALLS 14).
  - 테스트는 실제 `~/.claude`·`~/.config` 를 건드리지 않는다 — `HOME` 주입.
- **크기 등급**: **standard** (대상 파일 6개 + 신규 CLI 표면. `kit-scripts` 는 ⚠️ 도메인이라
  최소 standard이며 task는 처음부터 heavy tier).

## 비판적 검토 — 스펙 문구를 그대로 따르지 않은 이유

실측 결과 스펙의 `upgrade --add-missing` 은 **대부분 이미 존재한다**. 그대로 신규 구현하면 중복(🔴)이다.

| 실측 | 근거 | 결론 |
|---|---|---|
| 프로젝트 스캐폴드 증분 추가 | `lib/stamp.sh:24 stamp_copy` = 기존 파일 절대 안 덮음 + `.orchestrate/.stamp-copied` 매니페스트. `adopt-project.sh` 재실행이 곧 증분 추가 | 신규 엔진 금지 — 재실행 경로를 안내만 |
| 전역 자산 갱신 | `install.sh:842 backup_and_copy` — 재실행 시 diff 나면 백업 후 갱신 | 신규 엔진 금지 — 재실행 경로를 안내만 |
| 모델 체인 진단 | `core/opencode/model-doctor.sh` (`--policy/--secrets/--opencode-bin/--skip-smoke`) | doctor 가 재구현 금지 (이번 범위 밖) |
| 훅 진단 | `core/scripts/hook-selfcheck.sh` | 동일 |
| **부재** | 통합 리포트(OK/WARN/FAIL), **drift 보고**("내 파일이 킷 원본보다 낡았다"), 누락만 채우기 | 이번 페이즈의 실제 가치 |

따라서 `--add-missing` 은 **누락(=부재) 항목만 복사**하고, **drift 항목은 보고만** 한다
(갱신은 기존 `./install.sh` 재실행 경로 안내). 파괴적 동작을 새로 만들지 않는다.

## 전제 실측

| 전제 | 근거 | 판정 |
|---|---|---|
| install.sh 에 doctor/upgrade 계열 플래그가 없다 | `install.sh:74-80` (`--claude/--codex/--providers=/--containers=/--plan=`) | 유지 |
| 전역 자산 복사 지점은 7곳이다 | `install.sh:1540-1544`(claude skills tree), `1550-1552`(codex prompts), `1560-1564`(4 파일), `1567-1570`(secrets.env seed) | 유지 |
| 필수 도구 목록은 git curl python3 jq 다 | `install.sh:781` `for c in git curl python3 jq` | 유지 |
| opencode 설치 판정은 `$HOME/.opencode/bin/opencode` 실행권한이다 | `install.sh:1481` | 유지 |
| `INSTALL_PARSE_ONLY` 는 harness 자동감지(91-93) **뒤**, 함수 정의 **앞**(95-102)에서 종료한다 | `install.sh:91-102` | 유지 — dispatch 위치 설계에 반영 |
| 하네스 미검출 시 `install.sh` 는 exit 64 로 죽는다 | `install.sh:92` `|| exit 64` | **유지(위험)** — doctor 는 이 지점 **앞**에서 dispatch해야 깨진 호스트에서도 돈다 (Task 3) |
| `secrets.env` 는 사용자 값 보유 파일이라 덮지 않는다 | `install.sh:1567-1573` | 유지 — 매니페스트 `seed` 모드 |
| `scripts/` 는 전부 `../core/scripts/` 심링크다 | `ls -la scripts/` 실측 | 유지 |
| 기존 테스트에 `--doctor` 하드코딩 충돌 없음 | `grep -rn 'doctor' tests/` → `test_model_doctor.py` 만 (별 기능) | 유지 |

## 매니페스트 규격 (Task 2가 이 규격대로 만든다 — 발명 금지)

`core/install-manifest.tsv` — 탭 구분 4열, `#` 주석·빈 줄 허용:

```
# harness	mode	src(KIT_DIR 상대)	dst($HOME 상대)
any	file	core/onboard/ONBOARD-PROCEDURE.md	.config/orchestrate/ONBOARD-PROCEDURE.md
any	file	core/opencode/opencode.json	.config/opencode/opencode.json
any	file	core/opencode/model-doctor.sh	.config/opencode/model-doctor.sh
any	file	core/opencode/provider-models.json	.config/opencode/provider-models.json
any	seed	core/opencode/secrets.env.example	.config/opencode/secrets.env
claude	tree	adapters/claude/global/skills	.claude/skills
codex	tree	adapters/codex/global/prompts	.codex/prompts
```

- `harness`: `any` | `claude` | `codex` — 해당 하네스가 선택되지 않으면 점검 대상에서 제외.
- `mode`:
  - `file` — dst 존재 확인 + `cmp -s` 로 킷 원본 대비 **drift** 판정.
  - `seed` — 존재만 확인 (사용자 값 보유. drift 판정 금지).
  - `tree` — src 하위 **최상위 항목마다** dst/<이름> 존재 확인 + `diff -r -q` 로 drift 판정.

## 리포트 규격 (Task 2)

한 항목당 한 줄, 접두사 고정 (테스트가 이 문자열을 단정한다):

```
OK   <범주>: <대상>
WARN <범주>: <대상> — <사유>
FAIL <범주>: <대상> — <사유>
DRIFT <범주>: <대상> — 킷 원본과 다르다 (갱신: ./install.sh 재실행)
```

- 마지막 줄에 요약: `KIT_DOCTOR: ok=<n> warn=<n> drift=<n> fail=<n> added=<n>` (5필드 고정.
  읽기 전용 실행에서는 `added=0`.)
- 종료 코드: `fail>0` → **1**, 그 외(warn·drift만) → **0**.

### 심각도 판정 (2026-08-17 확정 — 리뷰 지적으로 초판의 자기모순을 해소했다)

초판은 "하네스 자산 부재 = WARN"이라 썼는데 위임 프롬프트에는 "tree 부재 = FAIL"이라 써서
스펙이 자기모순이었다. 두 리뷰어가 같은 지점을 지적했다. **확정 규칙**:

| 상태 | 조건 |
|---|---|
| `FAIL` | 필수 도구(`git curl python3 jq`) 부재 / **점검 대상인 매니페스트 행**(`any` + 선택·감지된 하네스)의 `file`·`tree` 자산 부재 / 매니페스트를 읽을 수 없음 / 경로 봉쇄 위반 행 |
| `WARN` | 선택 도구(`docker`·`claude`·opencode) 부재 / `seed` 자산 부재 / **하네스 미검출로 스킵된 행**(행마다 1줄) / 매니페스트 유효 행 0건 / 읽을 수 없는 파일 / 비교 실패 / 심링크 dst |
| `DRIFT` | 존재하나 내용 상이 (`file`·`tree` 만. `seed` 는 판정하지 않는다) |

근거: 선택된 하네스의 자산 부재는 **실제 결함이고 `--add-missing` 으로 고칠 수 있다** — WARN 으로
낮추면 사용자가 고치지 않는다. 반대로 하네스를 감지하지 못해 **점검조차 못 한 행**은 결함 판정이
아니라 "확인 못 했다"는 사실을 행마다 보고해야 한다 (통째로 침묵하면 거짓 안심이 된다).

## Task 목록

| # | 제목 | 담당 | 상태 | 커밋 |
|---|---|---|---|---|
| 1 | 회귀 테스트 동결 (오케스트레이터 직접 작성) | 오케스트레이터 | 완료 | `49a7e05` |
| 2 | `core/install-manifest.tsv` + `core/scripts/kit-doctor.sh` 진단 본체 | `kit-scripts` (heavy) | **완료** (리뷰 1회 반려 → 수정 후 3종 SIGN OFF) | `22f75b3`, `1f4c41d` |
| 3 | `install.sh --doctor` 위임 dispatch | `kit-scripts` (heavy) | **완료** (수정 2회: 회귀 2건 + 리뷰 반려 2건) | `f705f1b`, `c097d18` |
| 4 | `kit-doctor.sh --add-missing` (누락만 복사, 기존 파일 불변) | `kit-scripts` (heavy) | **완료** (수정 1회: 리뷰 반려 4건) | `79633ac`, `764eacf` |
| 5 | README·WORKFLOW 문서 반영 | `kit-docs` | **완료** (수정 1회: 국문 어법 3곳) | `12bd289`, `1427fa7` |

### 오케스트레이터 동결 테스트 커밋 (위임 산출물과 분리 — PITFALLS 27)

`49a7e05`(16건 RED) → `f694032`(경로 봉쇄 3) → `b2d2f70`(거짓 안심 4) → `48a5933`(파싱 훅) →
`1db2b59`(심링크 부모) → `d985e27`(정확일치 단정) → `1aabd31`(심링크 단정 조임) →
`d52b81f`(복구 정직성 3) → `5c46698`(옵션 조합 거부) = **동결 30건**

상세: `docs/phases/PHASE10_doctor-upgrade-ux.tasks/task<N>.md`

## 리뷰 예상 지점 — RED 사전 고정

| 지점 | 예상 지적 | 고정 RED 테스트 (담당) |
|---|---|---|
| drift 판정이 조용히 성공 처리 (`cmp` 실패 삼킴) | 🔴 silent failure — 낡은 자산을 OK로 보고 | `test_kit_doctor.py::test_modified_asset_reports_drift` (Task 2) |
| `--add-missing` 이 기존 파일을 덮음 | 🔴 사용자 데이터 손실 | `test_kit_doctor.py::test_add_missing_never_overwrites_existing` (Task 4) |
| 하네스 미검출 호스트에서 `--doctor` 가 exit 64 로 죽음 | 🔴 doctor 무용 (install.sh:92) | `test_kit_doctor.py::test_doctor_runs_without_detected_harness` (Task 3) |
| 매니페스트가 install.sh 복사부와 어긋남 | 🟠 자산 추가 시 doctor 가 조용히 놓침 | `test_kit_doctor.py::test_manifest_covers_install_copy_targets` (Task 1·2) |
| `seed` 항목(secrets.env)을 drift로 오판 | 🟠 사용자 키 입력을 "낡음"으로 보고 | `test_kit_doctor.py::test_seed_entry_never_reports_drift` (Task 2) |

## 전파 제약 누적

- **Task 2 → Task 4 (보안, security-reviewer 재현)**: 매니페스트 `src`·`dst` 의 `..`·절대경로를
  거부하고 심링크 dst 에는 쓰지 않아야 한다. 읽기 전용인 지금은 정보 노출(🟠)이지만 복사 기능이
  붙는 순간 임의 파일 쓰기(🔴)가 된다. 동결 테스트 `DoctorPathContainmentTest` 3건으로 강제.
- **Task 2 → Task 3**: `kit-doctor.sh` 의 실제 인자는 `--home`·`--kit`·`--manifest`·`--claude`·`--codex`
  이고 알 수 없는 인자는 exit 64 다. dispatch 시 이 이름을 그대로 쓸 것.
- **Task 2 → Task 4·5**: 요약 줄은 `KIT_DOCTOR: ok= warn= drift= fail= added=` 5필드 고정
  (Task 2 는 `added=0` 을 항상 출력한다). 필드를 빼거나 순서를 바꾸면 테스트가 깨진다.

## 리뷰 라운드 기록

| task | 라운드 | 리뷰어 | 판정 | 요지 |
|---|---|---|---|---|
| 2 | 1 | security-reviewer | ✅ 조건부 SIGN OFF | 🟠 매니페스트 경로 이탈(CWE-22) 재현, 🟡 심링크 추종 — Task 4 선행 조건으로 지정 |
| 2 | 1 | bash-reviewer | ❌ BLOCK | 🔴 "위임이 동결 테스트 수정" → **오진(기각)**, 🟠 심각도 오분류(=스펙 자기모순), 🟠 경로 봉쇄 |
| 2 | 1 | silent-failure-hunter | ❌ BLOCK | 🔴 하네스 미검출 시 자산 점검 통째 침묵(거짓 안심), 🟠 빈 매니페스트, 🟡 cmp stderr |
| 2 | 2 | bash-reviewer | ✅ SIGN OFF | 6건 재현 검증 통과, 🔴 오진 기각 수용(위임 로그 확인), 🟡 부모-부재 폴백 이관 |
| 2 | 2 | silent-failure-hunter | ✅ SIGN OFF | 원 지적 해소 확인, 🟠 `--add-missing` no-op·🟡 폴백을 Task 4 로 이관 |

**리뷰가 실제로 잡은 것**: 오케스트레이터가 동결한 16건이 전부 통과한 상태에서도
🔴 거짓 안심(하네스 미검출 시 `.claude/skills`·`.codex/prompts` 점검을 통째로 침묵하고
`fail=0 exit 0`)이 남아 있었다. 이 지적으로 동결 테스트를 7건 추가했다(총 23건 → 이후 30건).

| task | 라운드 | 리뷰어 | 판정 | 요지 |
|---|---|---|---|---|
| 3 | 1 | bash-reviewer | ✅ SIGN OFF | 6개 계약 전부 재현 검증 (dispatch 위치·bash 3.2·부작용 0) |
| 3 | 1 | security-reviewer | ✅ SIGN OFF | 인자 주입 차단·`exec` 종료코드 전파 확인. 🟡 `INSTALL_PARSE_ONLY` CI 함정 → 문서화 |
| 3 | 1 | silent-failure-hunter | ❌ BLOCK | 🔴 `--doctor` 가 `--containers`·`--providers`·언어를 **아무 경고 없이 삼킴** |
| 4 | 1 | bash-reviewer | ✅ SIGN OFF | 셸 7항목 통과. 🟠🟡 를 silent-failure 와 **독립 재현** |
| 4 | 1 | security-reviewer | ✅ SIGN OFF | CWE-22/59 차단을 변이 검증 2종으로 독립 확인 |
| 4 | 1 | silent-failure-hunter | ❌ BLOCK | 🔴 seed `chmod` 실패 후 644 영구 은폐 / 🔴 tree 부분복사 후 `DRIFT+exit 0` 고착 |
| 5 | 1 | code-reviewer | ❌ BLOCK | 사실관계 전부 정확. 국문 어법 3곳 (조사 2 + 어미 1) |

### 리뷰 조합에서 실제 검출자가 누구였나 (로스터 근거 실측)

같은 코드를 7회 리뷰했는데 **BLOCK 3건은 전부 `silent-failure-hunter`** 에서 나왔다.
세 지적 모두 "기능이 실패했는데 성공으로 보고" 계열이고, bash·security 리뷰어는 같은 코드를
통과시켰다(Task 4 에서 bash-reviewer 가 같은 🟠🟡 를 독립 발견했으나 비차단 판정).
로스터가 `kit-scripts` 에 이 리뷰어를 매핑해 둔 근거가 실측으로 확인됐다.

### 사전 고정한 "리뷰 예상 지점" 의 적중률 (워크플로우 개선 근거)

지시서에 5개를 사전 고정했고 그중 리뷰어가 실제로 지적한 것은 **2개**(경로 봉쇄, drift 조용한 성공)다.
나머지 🔴 4건은 예상하지 못한 축에서 나왔다:
① 하네스 미검출 시 점검 침묵 ② seed 권한 사후 미검사 ③ tree 부분복사 고착
④ 진단 모드가 설치 옵션을 조용히 삼킴. 공통점은 **"점검·복구하지 못한 것을 성공으로 보고"** 이며,
개별 함수의 정확성이 아니라 **도구가 하는 약속과 실제 보장의 격차**다.
다음 페이즈의 리뷰 예상 지점에는 이 축("이 도구가 약속한 것 중 검증하지 않는 것은 무엇인가")을
한 줄로 넣을 것.

## 수정 라운드 이후 재검증 (2026-08-17)

| task | 라운드 | 리뷰어 | 판정 | 요지 |
|---|---|---|---|---|
| 2 | 2 | bash / silent-failure | ✅✅ SIGN OFF | 6건 해소 재현 확인. 🟡 부모-부재 폴백을 Task 4 로 이관 |
| 3 | 2 | (오케스트레이터 직접 검증) | ✅ | 파싱 훅 회귀·bash 3.2 빈 배열 해소, 옵션 조합 거부 4종 exit 64 실측 |
| 4 | 2 | silent-failure | ❌ BLOCK | 🔴 원자화가 만든 **신규** 결함: `.kit-partial` 잔재 비가시 축적 / 🟠 잔재가 복구를 영구 차단 |
| 4 | 3 | silent-failure | ✅ SIGN OFF | 잔재 가시화·재시도 복구 재현 확인. 🟠 1건 잔여(아래) |
| 5 | 2 | code-reviewer | ✅ 조건부 SIGN OFF | 국문 3곳 해소. 🟠 문서 갭 2건 → `4cd2b07` 로 반영 완료 |

### 미해결 — 후속 페이즈로 이관

| # | 항목 | 근거·해법 |
|---|---|---|
| 1 | 🟠 **tree 모드에서 소스에서 이름이 사라진 엔트리의 잔재는 비가시** | `check_staging_leftovers` 가 소스 엔트리 이름을 순회하므로, 킷 버전이 바뀌어 스킬이 리네임·삭제되면 그 잔재가 어떤 진단 모드에도 나타나지 않는다 (`legacy-skill-removed-from-kit.kit-partial.555` 재현). 해법: 목적지 디렉터리를 `find "$dst" -maxdepth 1 -name '*.kit-partial.*'` 로 직접 스캔 — 아래 3번 오탐 범위도 함께 축소된다. **Task 4 는 수정 2회차를 소진**해 이 페이즈에서 더 재위임하지 않았다 |
| 2 | 🟡 `--home` 에 상대 경로를 주면 봉쇄 판정이 CWD 에 의존 | 기존 전제(`HOME_DIR` 은 절대 경로). 실사용 기본값은 `$HOME` 이라 영향 없음 |
| 3 | 🟡 잔재 glob 오탐 | 사용자가 만든 `*.kit-partial-backup` 류 파일명이 잔재로 오분류된다. 도구는 읽기 전용이라 삭제하지 않지만 "직접 삭제해도 안전하다" 문구가 오해를 부를 수 있다 |
| 4 | 🟡 seed `chmod` TOCTOU | `cp` → `chmod 600` 사이 짧은 창. `install.sh:1577-1579` 의 기존 관행과 동일 |
| 5 | 범위 밖(인터뷰 결정) | 모델 정책·프로젝트 스캐폴드·컨테이너/MCP 진단 — 각각 `model-doctor.sh`·`hook-selfcheck.sh`·후속 소관 |

## 자동 결정 로그

(오토 모드 아님 — 해당 없음)
