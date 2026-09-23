#!/usr/bin/env python3
"""projects/<slug>/ 폴더를 템플릿으로 만든다. /script-new 스킬이 호출한다.

사용: python tools/new_project.py <slug>
"""
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGES = [
    "01-topic.md",
    "02-thumbnail.md",
    "03-sources.md",
    "04-candidates.md",
    "06-outline.md",
    "07-intro.md",
    "08-body.md",
    "09-review.md",
    "script-final.md",
]


def main():
    if len(sys.argv) != 2:
        sys.exit("사용: new_project.py <slug>")
    slug = sys.argv[1]
    proj = ROOT / "projects" / slug
    if proj.exists():
        sys.exit(f"이미 있음: {proj}")
    (proj / "05-demo-cards").mkdir(parents=True)
    (proj / "transcripts").mkdir()
    today = dt.date.today().isoformat()
    brief = (ROOT / "templates" / "brief.md").read_text(encoding="utf-8")
    (proj / "brief.md").write_text(brief.replace("{{slug}}", slug).replace("{{date}}", today), encoding="utf-8")
    for s in STAGES:
        (proj / s).write_text(f"# {s[:-3]} — {slug}\n\n(아직 비어 있음)\n", encoding="utf-8")
    print(f"생성: {proj}")
    print("다음: brief.md의 역할, 전환 목적, 마무리 유형을 채운 뒤 /script-pipeline", slug)


if __name__ == "__main__":
    main()
