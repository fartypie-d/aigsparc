#!/usr/bin/env python3
"""orchestrate phase 레지스트리 도구 — init / claim / close / janitor / dashboard-mounts / tasks.

phase 번호의 유일한 진실의 원천은 ~/.local/state/orchestrate/registry/<project>.json.
git 밖·세션 밖 파일이므로 병렬 세션의 브랜치 가시성 한계와 세션 절단에 영향받지 않는다.
모든 레지스트리 갱신은 flock 안에서 수행된다.

사용:
  python3 scripts/phase-tools.py init --default-branch develop --docs-dir docs/phases
  python3 scripts/phase-tools.py claim <slug> [--base <ref>]
  python3 scripts/phase-tools.py close <N> [--keep-worktree] [--force] [--target <ref>]
  python3 scripts/phase-tools.py janitor
  python3 scripts/phase-tools.py dashboard-mounts [--print-path]
  python3 scripts/phase-tools.py tasks <N> [--set <task>=<status>] [--next]
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path

WORKTREE_BASE = ".claude/worktrees"
PHASE_RE = re.compile(r"phase[_-]?(\d+)", re.IGNORECASE)
STALE_LOG_DAYS = 7
STALE_PR_DAYS = 3
# 병합돼 있어도 janitor가 절대 삭제하지 않는 장수 브랜치
PROTECTED_BRANCHES = {"main", "master", "develop", "even-mode"}


def state_dir() -> Path:
    base = Path(os.environ.get(
        "ORCH_STATE_DIR", str(Path.home() / ".local/state/orchestrate")))
    d = base / "registry"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sh(args, cwd=None, check=True, timeout=60):
    return subprocess.run(
        [str(a) for a in args], cwd=cwd, check=check, timeout=timeout,
        capture_output=True, text=True)


def git(root, *args, check=True, timeout=60):
    return sh(["git", "-C", root, *args], check=check, timeout=timeout)


def find_root() -> Path:
    """워크트리 안에서 실행돼도 메인 체크아웃 루트를 돌려준다."""
    r = sh(["git", "rev-parse", "--git-common-dir"])
    common = Path(r.stdout.strip())
    if not common.is_absolute():
        common = (Path.cwd() / common).resolve()
    return common.parent


def find_docs_root(main_root: Path) -> Path:
    """호출 cwd 체크아웃의 문서 루트를 반환한다.

    레지스트리는 메인, 문서는 cwd 체크아웃 우선(KF-13)으로 접근한다. git 밖이면
    메인 루트로 폴백하지 않고 명시 오류를 낸다.
    """
    r = sh(["git", "rev-parse", "--show-toplevel"], check=False)
    if r.returncode != 0 or not r.stdout.strip():
        raise SystemExit(
            f"git 최상위를 해석할 수 없다 (cwd={Path.cwd()}): {r.stderr.strip()}")
    top = Path(r.stdout.strip()).resolve()
    if not (top / ".git").exists():
        raise SystemExit(f"해석된 최상위에 .git 이 없다: {top}")
    return top


def is_clean(path) -> bool:
    return git(path, "status", "--porcelain", check=False).stdout.strip() == ""


def is_merged(root, ref, target) -> bool:
    return git(root, "merge-base", "--is-ancestor", "--", ref, target,
               check=False).returncode == 0


def merge_target(root, db: str) -> str:
    """origin/<db>가 있으면 그것을, 없으면 로컬 <db>를 병합 판정 기준으로 쓴다."""
    if git(root, "rev-parse", "--verify", f"origin/{db}",
           check=False).returncode == 0:
        return f"origin/{db}"
    return db


def scan_max_phase(root: Path, docs_dir: str) -> int:
    nums = [0]
    for f in phase_document_files(root, docs_dir):
        m = PHASE_RE.search(f.name)
        if m:
            nums.append(int(m.group(1)))
    branches = git(root, "branch", "-a", check=False).stdout
    nums += [int(m.group(1)) for m in PHASE_RE.finditer(branches)]
    wt_base = root / WORKTREE_BASE
    if wt_base.is_dir():
        for d in wt_base.iterdir():
            m = PHASE_RE.search(d.name)
            if m:
                nums.append(int(m.group(1)))
            # 워크트리 안에서 번호가 리네임되면 문서만이 유일한 근거다 (166→167 실측)
            for f in phase_document_files(d, docs_dir):
                m = PHASE_RE.search(f.name)
                if m:
                    nums.append(int(m.group(1)))
    return max(nums)


def phase_document_files(root: Path, docs_dir: str):
    """스캐폴드 제외 재귀 페이즈 문서를 반환한다."""
    base = root / docs_dir
    if not base.is_dir():
        return
    for path in base.rglob("*.md"):
        parts = path.relative_to(base).parts
        if any(part in ("TEMPLATES", "specs", "images") for part in parts):
            continue
        if PHASE_RE.search(path.name):
            yield path


def default_docs_dir(root: Path) -> str:
    """문서 내용까지 확인해 init의 기본 문서 경로를 고른다."""
    docs_phases = root / "docs" / "phases"
    legacy_docs = root / "DOCs"
    if docs_phases.is_dir() and any(
            PHASE_RE.search(path.name)
            for path in phase_document_files(root, "docs/phases")):
        return "docs/phases"
    if legacy_docs.is_dir():
        return "DOCs"
    return "docs/phases"


class Registry:
    """flock 하에 레지스트리 파일을 읽고 쓰는 컨텍스트 매니저."""

    def __init__(self, root: Path):
        self.root = root
        self.path = state_dir() / f"{root.name}.json"
        self._lock_path = self.path.with_suffix(".lock")
        self._fh = None
        self.data = None

    def __enter__(self):
        self._fh = open(self._lock_path, "w")
        fcntl.flock(self._fh, fcntl.LOCK_EX)
        if self.path.exists():
            self.data = json.loads(self.path.read_text())
        return self

    def __exit__(self, *exc):
        fcntl.flock(self._fh, fcntl.LOCK_UN)
        self._fh.close()

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + "\n")
        tmp.rename(self.path)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def cmd_init(args):
    root = find_root()
    with Registry(root) as reg:
        if reg.data is not None and not args.reseed:
            print(f"레지스트리 존재 — next_phase={reg.data['next_phase']} (변경 없음)")
            return 0
        if args.docs_dir is not None:
            docs_dir = args.docs_dir
        elif reg.data is not None:
            docs_dir = reg.data["docs_dir"]
        else:
            docs_dir = default_docs_dir(root)
        seed = scan_max_phase(root, docs_dir) + 1
        reg.data = {
            "project": root.name,
            "root": str(root),
            "default_branch": args.default_branch,
            "docs_dir": docs_dir,
            "next_phase": seed,
            "active": reg.data["active"] if reg.data else [],
        }
        reg.save()
        print(f"초기화 완료 — project={root.name} next_phase={seed}")
    return 0


def cmd_claim(args):
    root = find_root()
    with Registry(root) as reg:
        if reg.data is None:
            print("레지스트리 없음 — 먼저 init을 실행하세요", file=sys.stderr)
            return 64
        d = reg.data
        n = d["next_phase"]
        slug = re.sub(r"[^a-z0-9-]+", "-", args.slug.lower()).strip("-")
        branch = f"feature/phase{n}-{slug}"
        wt_rel = f"{WORKTREE_BASE}/phase{n}-{slug}"
        db = d["default_branch"]
        git(root, "fetch", "origin", db, check=False, timeout=30)
        base = args.base or merge_target(root, db)
        r = git(root, "worktree", "add", "-b", branch, wt_rel, base, check=False)
        if r.returncode != 0:
            # 실패 시 카운터를 올리지 않는다 — flock을 쥔 채라 경쟁 없음
            print(f"worktree add 실패:\n{r.stderr}", file=sys.stderr)
            return 1
        d["next_phase"] = n + 1
        d["active"].append({
            "phase": n,
            "slug": slug,
            "worktree": wt_rel,
            "branch": branch,
            "base": base,
            "claimed_at": now_iso(),
            "source": os.environ.get("ORCH_SOURCE", "cli"),
        })
        reg.save()
    print(f"PHASE={n}")
    print(f"WORKTREE={root / wt_rel}")
    print(f"BRANCH={branch}")
    return 0


def doc_status(root: Path, docs_dir: str, n: int, worktree: Path | None):
    """지시서 PHASE<n>_*.md의 frontmatter status 값. (경로, 값) 또는 (None, None)."""
    search = [root / docs_dir]
    if worktree is not None:
        search.append(worktree / docs_dir)
    for base in search:
        if not base.is_dir():
            continue
        for f in sorted(base.glob(f"PHASE{n}_*.md")):
            for line in f.read_text(errors="replace").splitlines()[:15]:
                m = re.match(r"status:\s*(\S+)", line.strip())
                if m:
                    return f, m.group(1)
    return None, None


def archive_orchestrate(root: Path, n: int) -> int:
    """메인 체크아웃 .orchestrate/에서 phase n 관련 파일을 archive로 이동."""
    orch = root / ".orchestrate"
    if not orch.is_dir():
        return 0
    dest = orch / "archive" / f"phase{n}"
    moved = 0
    for item in list(orch.iterdir()):
        if item.name == "archive":
            continue
        if re.match(rf"(p{n}[-_.]|phase{n}([-_.]|$))", item.name):
            dest.mkdir(parents=True, exist_ok=True)
            item.rename(dest / item.name)
            moved += 1
    return moved


def cmd_close(args):
    root = find_root()
    n = args.number
    lines = []
    with Registry(root) as reg:
        if reg.data is None:
            print("레지스트리 없음 — 먼저 init을 실행하세요", file=sys.stderr)
            return 64
        d = reg.data
        db = d["default_branch"]
        if args.target:
            if git(root, "rev-parse", "--verify", args.target,
                   check=False).returncode != 0:
                print(f"--target ref 를 찾을 수 없음: {args.target}",
                      file=sys.stderr)
                return 2
            targets = [args.target]
        else:
            targets = []
            default_target = merge_target(root, db)
            if git(root, "rev-parse", "--verify", default_target,
                   check=False).returncode == 0:
                targets.append(default_target)
            if default_target != db and \
                    git(root, "rev-parse", "--verify", db,
                        check=False).returncode == 0:
                targets.append(db)
            current = git(root, "symbolic-ref", "--short", "HEAD",
                          check=False).stdout.strip()
            if current and current not in targets:
                targets.append(current)
        if not targets:
            lines.append("병합 판정 기준 없음(default_branch/HEAD 확인 불가) — 보존")
        entry = next((e for e in d["active"] if e["phase"] == n), None)
        wt_rel = entry["worktree"] if entry else None
        if wt_rel is None:
            hits = sorted((root / WORKTREE_BASE).glob(f"phase{n}-*")) \
                if (root / WORKTREE_BASE).is_dir() else []
            wt_rel = str(hits[0].relative_to(root)) if hits else None
        wt = (root / wt_rel) if wt_rel else None
        wt_exists = wt is not None and wt.is_dir()

        doc, status = doc_status(root, d["docs_dir"], n, wt if wt_exists else None)
        if status is not None and status != "done" and not args.force:
            print(f"지시서 status가 done이 아님 ({doc}: {status}) — "
                  f"frontmatter를 갱신하거나 --force로 우회하세요", file=sys.stderr)
            return 2

        branch = entry["branch"] if entry else None
        if wt_exists:
            wt_branch = git(wt, "rev-parse", "--abbrev-ref", "HEAD",
                            check=False).stdout.strip() or branch
            if not is_clean(wt):
                lines.append(f"워크트리 dirty — 보존: {wt_rel}")
            elif args.keep_worktree:
                lines.append(f"워크트리 보존(--keep-worktree): {wt_rel}")
            elif wt_branch and any(is_merged(root, wt_branch, target)
                                   for target in targets if target != wt_branch):
                git(root, "worktree", "remove", wt_rel)
                lines.append(f"워크트리 제거: {wt_rel}")
                branch = wt_branch
            else:
                lines.append(f"워크트리 미병합 — 보존: {wt_rel} ({wt_branch})")

        if branch and not (wt_rel and (root / wt_rel).is_dir()):
            if any(is_merged(root, branch, target)
                   for target in targets if target != branch) and \
                    git(root, "branch", "-d", branch, check=False).returncode == 0:
                lines.append(f"로컬 브랜치 삭제: {branch}")

        moved = archive_orchestrate(root, n)
        if moved:
            lines.append(f".orchestrate 아카이브: {moved}개 파일")

        if entry:
            d["active"] = [e for e in d["active"] if e["phase"] != n]
            reg.save()
            lines.append("레지스트리 항목 제거")

    print(f"phase {n} 마감:")
    for ln in lines or ["정리할 항목 없음"]:
        print(f"  - {ln}")
    return 0


def stale_prs(root: Path):
    """gh가 있으면 3일+ 정체된 열린 PR 목록. 실패는 조용히 빈 목록."""
    import shutil as _shutil
    if _shutil.which("gh") is None:
        return []
    r = sh(["gh", "pr", "list", "--state", "open",
            "--json", "number,title,isDraft,updatedAt"],
           cwd=root, check=False, timeout=10)
    if r.returncode != 0:
        return []
    out = []
    try:
        prs = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return []
    now = datetime.now().astimezone()
    for pr in prs:
        upd = datetime.fromisoformat(pr["updatedAt"].replace("Z", "+00:00"))
        age = (now - upd).days
        if age >= STALE_PR_DAYS:
            draft = " (draft)" if pr.get("isDraft") else ""
            out.append(f"PR #{pr['number']}{draft} {age}일 정체 — {pr['title'][:40]}")
    return out


def cmd_janitor(args):
    try:
        return _janitor_inner()
    except Exception as e:  # 세션 시작을 막지 않는다
        print(f"JANITOR: 오류로 건너뜀 ({type(e).__name__}: {e})")
        return 0


def _janitor_inner():
    root = find_root()
    auto, warn = [], []
    with Registry(root) as reg:
        if reg.data is None:
            print("JANITOR: 레지스트리 없음 — init 필요")
            return 0
        d = reg.data
        db = d["default_branch"]
        target = merge_target(root, db)
        active_branches = {e["branch"] for e in d["active"]}

        # 1. 유령 레지스트리 항목
        for e in list(d["active"]):
            if not (root / e["worktree"]).is_dir():
                d["active"].remove(e)
                auto.append(f"유령 항목 제거: phase{e['phase']}")

        # 2. 워크트리: 병합+clean → 제거 / 그 외 보고
        wt_base = root / WORKTREE_BASE
        if wt_base.is_dir():
            for wt in sorted(wt_base.iterdir()):
                if not wt.is_dir():
                    continue
                br = git(wt, "rev-parse", "--abbrev-ref", "HEAD",
                         check=False).stdout.strip()
                if not is_clean(wt):
                    warn.append(f"dirty 워크트리: {wt.name} ({br})")
                elif br and is_merged(root, br, target):
                    git(root, "worktree", "remove",
                        str(wt.relative_to(root)), check=False)
                    git(root, "branch", "-d", br, check=False)
                    d["active"] = [e for e in d["active"] if e["worktree"]
                                   != str(wt.relative_to(root))]
                    auto.append(f"병합된 워크트리 제거: {wt.name}")
                else:
                    warn.append(f"미병합 워크트리: {wt.name} ({br})")

        # 3. 병합된 로컬 브랜치
        merged = git(root, "branch", "--merged", target,
                     check=False).stdout.splitlines()
        cur = git(root, "symbolic-ref", "--short", "HEAD",
                  check=False).stdout.strip()
        for b in (x.strip().lstrip("+ ") for x in merged):
            if not b or b.startswith("*") or b in (db, cur) \
                    or b in PROTECTED_BRANCHES or b in active_branches:
                continue
            if git(root, "branch", "-d", b, check=False).returncode == 0:
                auto.append(f"병합된 브랜치 삭제: {b}")

        # 4. 오래된 .orchestrate 파일 → archive/old/
        orch = root / ".orchestrate"
        if orch.is_dir():
            import time as _time
            cutoff = _time.time() - STALE_LOG_DAYS * 86400
            moved = 0
            for item in list(orch.iterdir()):
                if item.name in ("archive", "events.jsonl"):
                    continue
                if item.stat().st_mtime < cutoff:
                    dest = orch / "archive" / "old"
                    dest.mkdir(parents=True, exist_ok=True)
                    item.rename(dest / item.name)
                    moved += 1
            if moved:
                auto.append(f".orchestrate 아카이브: {moved}건")

        # 5. 메인 체크아웃 이탈·미푸시
        if cur and cur != db:
            warn.append(f"메인 체크아웃이 {db}가 아님: {cur} (메인=안정 전용 위반)")
        if not is_clean(root):
            warn.append("메인 체크아웃 dirty")
        if target != db:
            ahead = git(root, "rev-list", "--count", f"{target}..{db}",
                        check=False).stdout.strip()
            if ahead and ahead != "0":
                warn.append(f"{db}가 origin보다 {ahead}커밋 앞섬 (미푸시)")

        # 6. in-progress 방치 문서 (레지스트리 active에 없는 것)
        active_nums = {e["phase"] for e in d["active"]}
        docs = root / d["docs_dir"]
        if docs.is_dir():
            for f in sorted(docs.glob("PHASE*.md")):
                status = None
                for line in f.read_text(errors="replace").splitlines()[:15]:
                    m = re.match(r"status:\s*(\S+)", line.strip())
                    if m:
                        status = m.group(1)
                        break
                mnum = PHASE_RE.search(f.name)
                if status == "in-progress" and mnum \
                        and int(mnum.group(1)) not in active_nums:
                    warn.append(f"in-progress 방치 문서: {f.name}")

        warn.extend(stale_prs(root))
        reg.save()

    summary = f"JANITOR({root.name}): 자동정리 {len(auto)}건 / 확인필요 {len(warn)}건"
    print(summary)
    for ln in (auto + warn)[:12]:
        print(f"  - {ln}")
    log = state_dir().parent / f"janitor-{root.name}.log"
    with open(log, "a") as fh:
        fh.write(f"[{now_iso()}] {summary}\n")
        for ln in auto + warn:
            fh.write(f"  {ln}\n")
    return 0


TASK_STATUSES = ("pending", "in-progress", "done", "blocked", "superseded")
TASK_FILE_RE = re.compile(r"^task(\d+)\.md$")


def parse_task_frontmatter(text: str) -> dict[str, str]:
    # docs-index.py parse_frontmatter 최소 사본 — 하이픈 파일명이라 import 불가 (PHASE11 전제 실측)
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fm: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def find_tasks_dir(root: Path, docs_dir: str, phase: int) -> Path | None:
    hits = sorted((root / docs_dir).glob(f"PHASE{phase}_*.tasks"))
    dirs = [h for h in hits if h.is_dir()]
    return dirs[0] if dirs else None


def task_title(text: str) -> str:
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def cmd_tasks(args: argparse.Namespace) -> int:
    root = find_root()
    with Registry(root) as reg:
        if reg.data is None:
            print("레지스트리 없음 — 먼저 init", file=sys.stderr)
            return 2
        docs_dir = reg.data["docs_dir"]
    docs_root = find_docs_root(root)
    searched_docs_root = docs_root
    tasks_dir = find_tasks_dir(docs_root, docs_dir, args.phase)
    if tasks_dir is None and docs_root != root:
        tasks_dir = find_tasks_dir(root, docs_dir, args.phase)
        docs_root = root
        if tasks_dir is not None:
            print("문서를 cwd 체크아웃에서 찾지 못해 메인 체크아웃에서 찾았다: "
                  f"{root}", file=sys.stderr)
    if tasks_dir is None:
        print(f"PHASE{args.phase}_*.tasks 디렉터리 없음 "
              f"({docs_dir}; 탐색: {searched_docs_root}, {root})", file=sys.stderr)
        return 2

    if args.set:
        try:
            n_str, _, status = args.set.partition("=")
            n = int(n_str)
        except ValueError:
            print(f"--set 형식은 <task번호>=<status>: {args.set!r}", file=sys.stderr)
            return 2
        if status not in TASK_STATUSES:
            print(f"허용 status 아님: {status!r} (허용: {', '.join(TASK_STATUSES)})",
                  file=sys.stderr)
            return 2
        path = tasks_dir / f"task{n}.md"
        if not path.exists():
            print(f"task 파일 없음: {path}", file=sys.stderr)
            return 2
        text = path.read_text()
        if text.startswith("---") and text.find("\n---", 3) != -1:
            end = text.find("\n---", 3)
            head, body = text[: end + 4], text[end + 4:]
            if re.search(r"^status:\s*\S+$", head, re.MULTILINE):
                head = re.sub(r"^status:\s*\S+$", f"status: {status}", head,
                              count=1, flags=re.MULTILINE)
            else:
                head = head[:-4] + f"status: {status}\n---"
            path.write_text(head + body)
        else:
            path.write_text(f"---\ntask: {n}\nstatus: {status}\n---\n\n" + text)
        print(f"task {n} → {status}: {path.resolve()}")
        return 0

    entries = []
    for f in sorted(tasks_dir.iterdir()):
        m = TASK_FILE_RE.match(f.name)
        if not m:
            continue
        fm = parse_task_frontmatter(f.read_text())
        entries.append({
            "task": int(m.group(1)),
            # frontmatter 부재는 디폴트 대입 없이 unknown으로 그대로 노출 (silent fallback 금지)
            "status": fm.get("status", "unknown"),
            "title": task_title(f.read_text()),
            "path": str(f.relative_to(docs_root)),
        })
    entries.sort(key=lambda e: e["task"])

    if args.next:
        runnable = [e for e in entries if e["status"] == "in-progress"] or \
                   [e for e in entries if e["status"] == "pending"]
        if not runnable:
            return 1
        print(runnable[0]["task"])
        return 0

    complete = bool(entries) and all(
        e["status"] in ("done", "superseded") for e in entries
    )
    print(json.dumps(
        {"phase": args.phase, "docs_root": str(docs_root), "tasks": entries,
         "complete": complete},
        ensure_ascii=False, indent=2,
    ))
    return 0


def retry_guard_snapshot() -> str:
    """현재 git 워크트리의 내용 기반 스냅샷 해시를 반환한다."""
    root_result = subprocess.run(
        ("git", "rev-parse", "--show-toplevel"), cwd=Path.cwd(),
        capture_output=True, text=False, timeout=60)
    if root_result.returncode != 0:
        stderr = root_result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git 최상위 해석 실패: {stderr}")
    root = Path(os.fsdecode(root_result.stdout).strip()).resolve()
    commands = (
        ("git", "status", "-z", "-uall"),
        ("git", "diff", "--binary", "HEAD"),
        ("git", "ls-files", "-z", "--full-name", "--others", "--exclude-standard"),
    )
    results = []
    for command in commands:
        result = subprocess.run(
            command, cwd=root, capture_output=True, text=False, timeout=60)
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"git 명령 실패 ({' '.join(command)}): {stderr}")
        results.append(result.stdout)

    digest = hashlib.sha256()
    digest.update(results[0])
    digest.update(results[1])
    for relative_path in sorted(path for path in results[2].split(b"\0") if path):
        path = root / os.fsdecode(relative_path)
        try:
            path_stat = os.lstat(path)
        except OSError:
            content_hash = hashlib.sha256(
                b"retry-guard:unreadable\0" + relative_path
            ).hexdigest()
        else:
            if stat.S_ISLNK(path_stat.st_mode):
                try:
                    link_target = os.fsencode(os.readlink(path))
                    content_hash = hashlib.sha256(
                        b"retry-guard:symlink\0" + relative_path + b"\0" + link_target
                    ).hexdigest()
                except OSError:
                    content_hash = hashlib.sha256(
                        b"retry-guard:symlink-unreadable\0" + relative_path
                    ).hexdigest()
            else:
                try:
                    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                except OSError:
                    content_hash = hashlib.sha256(
                        b"retry-guard:unreadable\0" + relative_path + b"\0" +
                        str(path_stat.st_size).encode("ascii") + b"\0" +
                        str(path_stat.st_mtime_ns).encode("ascii")
                    ).hexdigest()
                else:
                    try:
                        opened_stat = os.fstat(fd)
                        if not stat.S_ISREG(opened_stat.st_mode):
                            content_hash = hashlib.sha256(
                                b"retry-guard:special\0" + relative_path + b"\0" +
                                str(opened_stat.st_mode).encode("ascii")
                            ).hexdigest()
                        else:
                            content_digest = hashlib.sha256()
                            while True:
                                chunk = os.read(fd, 65536)
                                if not chunk:
                                    break
                                content_digest.update(chunk)
                            content_hash = content_digest.hexdigest()
                    except OSError:
                        content_hash = hashlib.sha256(
                            b"retry-guard:unreadable\0" + relative_path + b"\0" +
                            str(path_stat.st_size).encode("ascii") + b"\0" +
                            str(path_stat.st_mtime_ns).encode("ascii")
                        ).hexdigest()
                    finally:
                        os.close(fd)
        digest.update(relative_path)
        digest.update(b"\0")
        digest.update(content_hash.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def retry_guard_state_location(args: argparse.Namespace, root: Path) -> tuple[Path, str, str]:
    """상태 파일과 supervisor-state.sh에 넘길 project/XDG_STATE_HOME을 해석한다."""
    if args.state is None:
        xdg_state = Path(os.environ.get(
            "XDG_STATE_HOME", str(Path.home() / ".local" / "state")))
        return (xdg_state / "orchestrate" / "supervisor" / f"{root.name}.json",
                root.name, str(xdg_state))

    state_path = Path(args.state)
    if state_path.suffix != ".json" or state_path.parent.name != "supervisor" \
            or state_path.parent.parent.name != "orchestrate" or not state_path.stem:
        raise ValueError(
            "--state는 <XDG_STATE_HOME>/orchestrate/supervisor/<project>.json 레이아웃이어야 한다")
    project = state_path.stem
    if not re.fullmatch(r"[A-Za-z0-9._-]+", project):
        raise ValueError("--state의 프로젝트명은 영문자·숫자·.·_·- 만 사용할 수 있다")
    return state_path, project, str(state_path.parents[2])


def cmd_retry_guard(args: argparse.Namespace) -> int:
    """직전 실패 뒤 워크트리에 변경이 없으면 같은 파트 재시도를 막는다."""
    if not re.fullmatch(r"[0-9]+", args.phase):
        print(f"retry-guard 오류: phase는 십진 정수여야 한다: {args.phase}",
              file=sys.stderr)
        return 1
    try:
        root = find_root()
        state_path, project, xdg_state = retry_guard_state_location(args, root)
        if state_path.is_symlink():
            raise ValueError(f"상태 파일이 심링크라 거부했다: {state_path}")
        if not state_path.exists():
            print(f"retry-guard 상태 파일이 없다: {state_path}", file=sys.stderr)
            return 2
        if not stat.S_ISREG(os.lstat(state_path).st_mode):
            raise ValueError(f"상태 파일이 정규 파일이 아니라 거부했다: {state_path}")
        raw_state = state_path.read_bytes()
        state = json.loads(raw_state)
        if not isinstance(state, dict):
            raise ValueError("상태 JSON은 객체여야 한다")
        snapshot = retry_guard_snapshot()
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError,
            subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(f"retry-guard 오류: {error}", file=sys.stderr)
        return 1

    if args.check or not args.record:
        failure = state.get("last_failure")
        if failure is None:
            return 0
        if not isinstance(failure, dict) or not isinstance(
                failure.get("worktree_hash"), str):
            print("retry-guard 오류: last_failure.worktree_hash가 없다", file=sys.stderr)
            return 1
        if "phase" not in failure or "part" not in failure:
            print("retry-guard 통지: 스코프 없는 구버전 기록을 그대로 비교했다",
                  file=sys.stderr)
        elif str(failure["phase"]) != str(args.phase) or \
                str(failure["part"]) != str(args.part):
            print("retry-guard 통지: 스코프 불일치로 통과 "
                  f"(기록 phase={failure['phase']} part={failure['part']}; "
                  f"요청 phase={args.phase} part={args.part})", file=sys.stderr)
            return 0
        if failure["worktree_hash"] == snapshot:
            print(f"retry_exhausted: phase={args.phase} part={args.part} 워크트리 변경 없음")
            return 3
        return 0

    failure = state.get("last_failure")
    if failure is None:
        failure = {}
        state["last_failure"] = failure
    if not isinstance(failure, dict):
        print("retry-guard 오류: last_failure는 객체여야 한다", file=sys.stderr)
        return 1
    failure["worktree_hash"] = snapshot
    failure["phase"] = args.phase
    failure["part"] = args.part
    env = os.environ.copy()
    env["XDG_STATE_HOME"] = xdg_state
    command = [str(Path(__file__).resolve().with_name("supervisor-state.sh")), "set", project,
               "-", "--baseline", hashlib.sha256(raw_state).hexdigest()]
    try:
        result = subprocess.run(
            command, input=json.dumps(state, ensure_ascii=False) + "\n",
            text=True, capture_output=True, env=env, timeout=60)
    except (FileNotFoundError, PermissionError, OSError) as error:
        print(f"retry-guard 상태 기록 스크립트 실행 실패: {error}",
               file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired:
        print("retry-guard 상태 기록 시간이 초과됐다 (60초)", file=sys.stderr)
        return 1
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        print(f"retry-guard 상태 기록 실패 (exit {result.returncode}): {detail}",
              file=sys.stderr)
        if result.returncode == 3:
            return 4
        if result.returncode == 2:
            return 2
        return 1
    return 0


def cmd_dashboard_mounts(args: argparse.Namespace) -> int:
    """레지스트리의 존재하는 문서 디렉터리로 대시보드 compose override를 만든다."""
    registry_dir = state_dir()
    override_path = registry_dir.parent / "dashboard-compose.override.yml"
    if args.print_path:
        print(override_path)
        return 0

    project_docs: list[tuple[str, str, Path, Path]] = []
    registry_paths = sorted(registry_dir.glob("*.json"))
    for registry_path in registry_paths:
        try:
            entry = json.loads(registry_path.read_text(encoding="utf-8"))
            if not isinstance(entry, dict):
                raise ValueError("레지스트리 항목은 객체여야 함")
            project = entry["project"]
            root = entry["root"]
            docs_dir = entry["docs_dir"]
            if not all(isinstance(value, str) for value in
                       (project, root, docs_dir)):
                raise ValueError("project, root, docs_dir는 문자열이어야 함")
        except (json.JSONDecodeError, KeyError, OSError, TypeError, ValueError) as error:
            print(f"경고: 레지스트리 항목 건너뜀 ({registry_path.name}: {error})",
                  file=sys.stderr)
            continue

        try:
            mount_path = Path(root) / docs_dir
            if not Path(root).is_absolute():
                raise ValueError("프로젝트 root가 절대경로가 아님")
            root_path = Path(root).resolve()
            docs_path = mount_path.resolve()
            if any(ord(char) < 32 or ord(char) == 127
                   for value in (root, docs_dir, str(mount_path))
                   for char in value):
                raise ValueError("경로에 제어 문자가 있음")
            try:
                docs_path.relative_to(root_path)
            except ValueError as error:
                raise ValueError("문서 경로가 프로젝트 root 밖에 있음") from error
            if docs_path == root_path:
                raise ValueError("문서 경로가 프로젝트 root와 같음")
            if not docs_path.is_dir():
                print(f"경고: 문서 디렉터리 건너뜀 (project={project!r}, "
                      f"registry={registry_path.name!r}, path={str(docs_path)!r}: "
                      "디렉터리가 없음)", file=sys.stderr)
                continue
        except (OSError, RuntimeError, ValueError) as error:
            print(f"경고: 문서 디렉터리 건너뜀 (project={project!r}, "
                  f"registry={registry_path.name!r}, "
                  f"path={str(Path(root) / docs_dir)!r}: {error})", file=sys.stderr)
            continue
        project_docs.append((project, registry_path.name, docs_path, mount_path))

    mounts: list[str] = []
    seen_paths: set[Path] = set()
    for project, registry_name, docs_path, mount_path in sorted(
            project_docs, key=lambda item: item[0]):
        if mount_path in seen_paths:
            print(f"경고: 문서 디렉터리 건너뜀 (project={project!r}, "
                  f"registry={registry_name!r}, path={str(mount_path)!r}: "
                  "중복 마운트 경로)", file=sys.stderr)
            continue
        seen_paths.add(mount_path)
        mounts.append(f"{docs_path}:{mount_path}:ro")

    if not mounts:
        override_path.unlink(missing_ok=True)
        if registry_paths:
            print(f"경고: 레지스트리 항목 {len(registry_paths)}개 중 마운트 0개",
                  file=sys.stderr)
        return 0

    registry_mount = f"{registry_dir}:/data/orchestrate-registry:ro"
    lines = [
        "services:",
        "  usage-dashboard:",
        "    volumes:",
        f"      - {json.dumps(registry_mount, ensure_ascii=False)}",
    ]
    lines.extend(f"      - {json.dumps(mount, ensure_ascii=False)}" for mount in mounts)
    lines.extend([
        "    environment:",
        "      - USAGE_REGISTRY_DIR=/data/orchestrate-registry",
        "",
    ])
    tmp = override_path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines), encoding="utf-8")
    tmp.rename(override_path)
    print(override_path)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="phase-tools")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="레지스트리 생성·시드")
    p_init.add_argument("--default-branch", required=True)
    p_init.add_argument("--docs-dir", default=None)
    p_init.add_argument("--reseed", action="store_true")
    p_init.set_defaults(fn=cmd_init)

    p_claim = sub.add_parser("claim", help="phase 번호 발급 + 워크트리 생성")
    p_claim.add_argument("slug")
    p_claim.add_argument("--base", default=None)
    p_claim.set_defaults(fn=cmd_claim)

    p_close = sub.add_parser("close", help="페이즈 마감 원샷 정리")
    p_close.add_argument("number", type=int)
    p_close.add_argument("--keep-worktree", action="store_true")
    p_close.add_argument("--force", action="store_true")
    p_close.add_argument("--target", default=None,
                         help="병합 판정에 사용할 단일 ref")
    p_close.set_defaults(fn=cmd_close)

    p_jan = sub.add_parser("janitor", help="세션 시작 잔재 정리·보고 (항상 exit 0)")
    p_jan.set_defaults(fn=cmd_janitor)

    p_mounts = sub.add_parser("dashboard-mounts",
                              help="대시보드 문서·레지스트리 마운트 override 생성")
    p_mounts.add_argument("--print-path", action="store_true",
                          help="생성 없이 override 대상 경로만 출력")
    p_mounts.set_defaults(fn=cmd_dashboard_mounts)

    p_tasks = sub.add_parser("tasks", help="task 상태 조회(JSON)·갱신 — 무인 드라이버·대시보드용")
    p_tasks.add_argument("phase", type=int)
    p_tasks.add_argument("--set", metavar="N=STATUS",
                         help=f"taskN.md frontmatter status 갱신 (허용: {', '.join(TASK_STATUSES)})")
    p_tasks.add_argument("--next", action="store_true",
                         help="실행 가능 task 번호만 출력 (in-progress 우선, 없으면 최소 pending; 전무 시 exit 1)")
    p_tasks.set_defaults(fn=cmd_tasks)

    p_retry = sub.add_parser("retry-guard", help="무변경 실패 재시도를 차단")
    p_retry.add_argument("phase")
    p_retry.add_argument("part")
    retry_mode = p_retry.add_mutually_exclusive_group()
    retry_mode.add_argument("--record", action="store_true",
                            help="현재 워크트리 스냅샷을 직전 실패 상태로 기록")
    retry_mode.add_argument("--check", action="store_true",
                            help="직전 실패 뒤 워크트리 변경 여부 확인 (기본)")
    p_retry.add_argument("--state", default=None, help="감독 상태 JSON 경로")
    p_retry.set_defaults(fn=cmd_retry_guard)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
