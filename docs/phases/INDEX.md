# docs/phases 인덱스 (자동 생성 — `scripts/docs-index.py`)

> 21개 페이즈 문서. 과거 작업은 이 표를 스캔 → 문서 열기 → `git show <commit>`.
> 표는 수정하지 말 것 (재생성 시 덮어씀). 신규 문서에 frontmatter를 달면 정확히 반영된다.

| Phase | Date | Kind | Domain | Status | Summary | 문서 | Commits |
|---|---|---|---|---|---|---|---|
| 17 | 2026-09-02 | task | scripts, install, tests, docs | done | 감독 계층 하드닝 — 감독 시작 계층(PROCEDURE·supervise 커맨드)을 키트로 이관 + owner PID 리스(A1)·원자 쓰기(A | [PHASE17_supervisor-hardening.md](PHASE17_supervisor-hardening.md) | 4af2824..2ec0dfc (+ 마감 커밋, 로컬 32개) |
| 16 | 2026-09-02 | task | scripts, tests, docs | done | 감독 체계 선행 — phase-tools tasks 워크트리 해석(KF-13)·session-cost --project/--session(KF- | [PHASE16_supervisor-bootstrap.md](PHASE16_supervisor-bootstrap.md) | 16825fa..b5f98ba (+ 마감 커밋) |
| 15 | 2026-09-01 | task | scripts, tests, docs | done | 위임 모델 정책의 프로젝트 스코프화(.claude/model-policy.json) + 크레딧·한도 실패 시그니처를 좁은 앵커로 확장 — 초안  | [PHASE15_model-policy-scope.md](PHASE15_model-policy-scope.md) | 7398461..0bc05dd |
| 15 | 2026-09-01 | review | scripts, tests, docs | done | 모델 정책 스코프 페이즈의 리뷰 총괄 — 반려 2라운드, 문서 표면 과소측정으로 task 신설 1회, 리뷰 결과 고아화 사고 1건 | [PHASE15_model-policy-scope.md](reviews/PHASE15_model-policy-scope.md) | 7398461..8cc33cd |
| 14 | 2026-09-01 | task | scripts, docs | done | tobuilder-bot 실적용 피드백(KF-1·KF-2) 반영 — docs-index가 DESIGN_·PLAN_ 문서를 인덱싱·kind 추론하 | [PHASE14_kf-docs-index.md](PHASE14_kf-docs-index.md) | 587c46f..66abab4 (7개 — feat 1 · fix 1 · test 2 · docs 3) |
| 13 | 2026-08-19 | task | scripts, docs | done | 위임 계측(.wrapper 로그·reject_cause)·총 벽시계 캡·구조 리뷰어 신설 | [PHASE13_delegation-observability.md](PHASE13_delegation-observability.md) | 05d4ccf..74c3717 (21개 — feat 3 · fix 4 · test 4 · docs 10) |
| 13 | 2026-08-19 | review | scripts, docs | done | 위임 관측성·안정성 페이즈의 리뷰 총괄 — 반려 3라운드 + 구조 리뷰어 첫 가동 결과 | [PHASE13_delegation-observability.md](reviews/PHASE13_delegation-observability.md) | 05d4ccf..74c3717 |
| 12 | 2026-09-01 | plan | scripts, tests, docs | draft | 위임 모델 정책의 프로젝트별 분리 + 한도 실패 시그니처 확장 — bash-reviewer REJECT 판정과 재현 근거, 착수 시 이 문서를  | [PLAN_model-policy-scope.md](PLAN_model-policy-scope.md) | - |
| 12 | 2026-09-01 | task | scripts, tests | done | 진입점별 KIT·프로젝트 루트 해석 통일 — scripts/ 심링크와 core/scripts/ 실경로 어느 쪽으로 불러도 같은 루트가 나오게 ( | [PHASE12_doctor-symlink-entrypoint.md](PHASE12_doctor-symlink-entrypoint.md) | 75eb80c..05308ba (10개 — fix 3 · test 5 · docs 2) |
| 11 | 2026-08-17 | task | scripts, skill | done | task 상태 기계판독화 — task 파일 frontmatter(status) + phase-tools tasks 서브커맨드 (Ralph 패턴  | [PHASE11_task-status-frontmatter.md](PHASE11_task-status-frontmatter.md) | fbece86..547c91d (지시서·구현 TDD 6건·스킬 규칙) |
| 10 | 2026-08-17 | task | scripts, install, tests, docs | done | kit-doctor — 설치 자가진단(도구·CLI·전역 자산 존재·drift) + 누락 자산만 채우는 --add-missing (기존 파일 불변 | [PHASE10_doctor-upgrade-ux.md](PHASE10_doctor-upgrade-ux.md) | 49a7e05..b230d8a (23개 — feat 3 · fix 4 · test 10 · docs 6) |
| 9 | 2026-08-17 | task | docs, install | done | dev-orchestrate-kit → aigsprac 리브랜딩 — 라이브 표면 치환 + 백로님 스토리 + 저장소·로컬 리네임 | [PHASE9_aigsprac-rebrand.md](PHASE9_aigsprac-rebrand.md) | 5ab35b8..8c0702e (10개 — task0~6 + 1b + 인덱스 2) |
| 8 | 2026-08-15 | task | scripts, docs | done | DOCs/ → docs/phases/ 소문자 통일 (킷 도그푸딩) — 이동 + 툴링 경로 탈하드코딩 + 참조 일괄 갱신 | [PHASE8_docs-lowercase.md](PHASE8_docs-lowercase.md) | f8d78d6, b190b4f, 855663c, f73f1ae, d69186a, 8099038 |
| 7 | 2026-08-15 | plan | docs, scripts | draft | DOCs/ → 소문자 docs/ 통일 실행 계획 — 미착수, 페이즈 착수 시 근거 문서 | [PLAN_docs-lowercase-migration.md](PLAN_docs-lowercase-migration.md) | - |
| 7 | 2026-08-14 | task | install, containers, docs | done | 대시보드 컨테이너의 프로젝트 DOCs 마운트를 오케스트레이트 레지스트리에서 자동 생성 | [PHASE7_dashboard-registry-mounts.md](PHASE7_dashboard-registry-mounts.md) | c3a8a07, 691eb88, 200292d, 9fe84b7, d0c6ca5 |
| 6 | 2026-08-14 | task | install, docs | done | usage-dashboard 를 --containers=dashboard 로 설치·기동 — 컨테이너 파이프라인 일반화 (서브모듈 경로·포트·문구 | [PHASE6_dashboard-container-option.md](PHASE6_dashboard-container-option.md) | db71ef2,9724994,4984ff3,082b286 |
| 5 | 2026-08-12 | task | scripts, docs | done | run-delegation v3 — opencode serve+attach 병렬 위임 (전역 직렬화 해소, 프로젝트별 직렬 유지) | [PHASE5_serve-attach-parallel-delegation.md](PHASE5_serve-attach-parallel-delegation.md) | PR #7·#8·#9 (main 병합) |
| 4 | 2026-08-11 | task | install, docs | done | install.sh 메뉴 UX 개편 — 체크박스 TUI, 마법사 뒤로가기, 구독 인증·컨테이너·MCP 스텝, 원인별 수동 조치 안내 | [PHASE4_install-menu-tui.md](PHASE4_install-menu-tui.md) | 4f34115..28321ed (파트 4-1~4-4, 세션 7 분 12개 포함) |
| 3 | 2026-08-11 | task | containers, docs | done | insane-cloak 서브모듈 범프 (fc88eaa→2f99245, MCP 절 포함) + 키트 README 에 MCP 사용법 절 추가 | [PHASE3_insane-cloak-mcp-bump.md](PHASE3_insane-cloak-mcp-bump.md) | 07ecca0,9e2846a + 마감 문서 커밋 (PR 병합) |
| 2 | 2026-08-11 | task | scripts, tests | done | Phase 1 리뷰 🟡 후속 정리 — install.sh 스트림·메시지·주석, 테스트 timeout, docs-index 심링크 버그, phas | [PHASE2_post-phase1-cleanup.md](PHASE2_post-phase1-cleanup.md) | 45b6d2a,8441144,83945f0,b183254,b220a0c + 마감 문서 커밋 |
| 1 | 2026-08-10 | task | scripts, tests, docs | done | install.sh UX 개편 — 필수 도구 자동 설치·claude 동의 설치·번호 선택 메뉴 + bash-guard 오탐 수정 | [PHASE1_install-ux-overhaul.md](PHASE1_install-ux-overhaul.md) | a50ec79..6b2bba1 (15개) + 마감 문서 커밋 |
