#!/usr/bin/env python3
"""페이즈 문서 인덱스 생성기.

저장소의 docs/phases/를 우선하고, 없으면 기존 DOCs/ 하위의 작업 지시서·리뷰·조사 문서를
스캔해 해당 디렉터리의 INDEX.md 표를 재생성한다.
문서 상단 frontmatter(--- ... ---)를 우선 읽고, 없으면 파일명·H1에서 best-effort 추출한다.

사용:  python3 scripts/docs-index.py        # docs/phases/INDEX.md 또는 DOCs/INDEX.md 갱신
페이즈 종료 시(orchestrate 9단계) 한 번 실행하면 인덱스가 최신화된다.

frontmatter 규약 (신규 문서 권장):
    ---
    phase: 119
    date: 2026-07-24
    kind: review            # task | review | investigation | design | plan
    domain: config, infra   # 콤마 구분
    status: done            # done | in-progress | superseded | decided | draft
    commits: 346172d        # 콤마 구분
    summary: 한 줄 요약
    ---
"""
from __future__ import annotations
import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path


# 규약: __file__ 의 심링크를 realpath 로 푼 뒤 프로젝트 루트를 판정한다.
# 부모가 core 이고 그 부모(grandparent) 에 킷 마커(core/install-manifest.tsv)
# 가 있으면 한 단계 더 올라간다(=킷 저장소 배치).
# 아니면 부모가 곧 프로젝트 루트다(=설치된 프로젝트 배치, <proj>/scripts/X).
def _resolve_project_root() -> Path:
    """__file__ 심링크를 실경로로 풀어 프로젝트 루트를 반환한다."""
    script_real = Path(os.path.realpath(__file__))
    script_dir = script_real.parent
    parent = script_dir.parent

    if parent.name == "core":
        grandparent = parent.parent
        if (grandparent / "core" / "install-manifest.tsv").is_file():
            return grandparent
    return parent


def default_docs_dir() -> Path:
    """문서 내용까지 확인해 기본 문서 경로를 계산한다."""
    root = _resolve_project_root()
    docs_phases = root / "docs" / "phases"
    legacy_docs = root / "DOCs"
    if docs_phases.is_dir() and any(
            is_included_document(path, docs_phases)
            for path in docs_phases.rglob("*.md")):
        return docs_phases
    if legacy_docs.is_dir():
        return legacy_docs
    return docs_phases

# 스캔 대상 (phase 문서만 — TODO/CTO_BRIEFING/specs/images/TEMPLATES 제외).
# reviews/ 디렉터리의 모든 .md는 패턴과 무관하게 포함한다(아래 main 참조).
INCLUDE_PATTERNS = (
    re.compile(r"^CURRENT_TASK.*\.md$"),
    re.compile(r"^AGENT_PROMPTS.*\.md$"),
    re.compile(r"^PHASE\d+.*\.md$", re.IGNORECASE),
    re.compile(r".*INVESTIGATION.*\.md$"),
    re.compile(r".*REVIEW.*\.md$", re.IGNORECASE),
    re.compile(r"^CASE_STUDY.*\.md$"),
    re.compile(r"^DESIGN([_.-].*)?\.md$"),
    re.compile(r"^PLAN([_.-].*)?\.md$"),
)


def is_included_document(path: Path, docs_dir: Path) -> bool:
    """인덱스 스캔 대상인지 판정한다."""
    if path.name == "INDEX.md":
        return False
    parts = path.relative_to(docs_dir).parts
    if any(part in ("TEMPLATES", "specs", "images") for part in parts):
        return False
    return "reviews" in parts or any(
        pattern.match(path.name) for pattern in INCLUDE_PATTERNS)


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fm: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip("[]")
    return fm


def h1(text: str) -> str:
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def extract(path: Path, docs_dir: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    fm = parse_frontmatter(text)
    rel = path.relative_to(docs_dir)
    name = path.name
    in_reviews = "reviews" in rel.parts
    archived = "archive" in rel.parts

    # phase
    phase = fm.get("phase", "")
    if not phase:
        m = re.search(r"[Pp][Hh][Aa][Ss][Ee][_\s]?(\d+)", name) or re.search(
            r"Phase\s+(\d+)", text[:400]
        )
        phase = m.group(1) if m else ""

    # date
    d = fm.get("date", "")
    if not d:
        m = re.search(r"(\d{4})[-_]?(\d{2})[-_]?(\d{2})", name)
        if m:
            d = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        else:
            m = re.search(r"\d{4}-\d{2}-\d{2}", text[:400])
            d = m.group(0) if m else date.fromtimestamp(path.stat().st_mtime).isoformat()

    # kind
    kind = fm.get("kind", "")
    if not kind:
        if in_reviews or "CODE_REVIEW" in name:
            kind = "review"
        elif "INVESTIGATION" in name:
            kind = "investigation"
        elif name.startswith(("DESIGN_", "DESIGN.", "DESIGN-")):
            kind = "design"
        elif name.startswith(("PLAN_", "PLAN.", "PLAN-")):
            kind = "plan"
        elif name.startswith(("CURRENT_TASK", "AGENT_PROMPTS")):
            kind = "task"
        else:
            kind = "doc"

    # status
    status = fm.get("status", "")
    if not status:
        status = "archived" if archived else ("current" if name == "CURRENT_TASK.md" else "-")

    summary = fm.get("summary", "") or h1(text)
    summary = re.sub(r"\s+", " ", summary)[:80]
    domain = fm.get("domain", "-") or "-"
    commits = fm.get("commits", "") or "-"

    return {
        "phase": phase or "0",
        "date": d,
        "kind": kind,
        "domain": domain,
        "status": status,
        "summary": summary,
        "commits": commits,
        "doc": str(rel).replace(" ", "%20"),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="docs-index")
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=default_docs_dir(),
        help="스캔하고 INDEX.md를 생성할 문서 디렉터리",
    )
    args = parser.parse_args(argv)
    docs_dir = args.docs_dir
    if not docs_dir.is_dir():
        print(
            f"문서 디렉터리를 찾을 수 없습니다: {docs_dir}",
            file=sys.stderr,
        )
        return 1
    index = docs_dir / "INDEX.md"
    rows = []
    for p in docs_dir.rglob("*.md"):
        if not is_included_document(p, docs_dir):
            continue
        rows.append(extract(p, docs_dir))

    def sort_key(r: dict[str, str]):
        try:
            ph = int(r["phase"])
        except ValueError:
            ph = -1
        return (ph, r["date"])

    rows.sort(key=sort_key, reverse=True)

    root = _resolve_project_root()
    try:
        docs_label = docs_dir.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        docs_label = str(docs_dir)

    lines = [
        f"# {docs_label} 인덱스 (자동 생성 — `scripts/docs-index.py`)",
        "",
        f"> {len(rows)}개 페이즈 문서. 과거 작업은 이 표를 스캔 → 문서 열기 → `git show <commit>`.",
        "> 표는 수정하지 말 것 (재생성 시 덮어씀). 신규 문서에 frontmatter를 달면 정확히 반영된다.",
        "",
        "| Phase | Date | Kind | Domain | Status | Summary | 문서 | Commits |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['phase']} | {r['date']} | {r['kind']} | {r['domain']} | "
            f"{r['status']} | {r['summary']} | [{Path(r['doc']).name}]({r['doc']}) | {r['commits']} |"
        )
    lines.append("")
    index.write_text("\n".join(lines), encoding="utf-8")
    print(f"INDEX.md 갱신: {len(rows)}개 문서")
    return 0


if __name__ == "__main__":
    sys.exit(main())
