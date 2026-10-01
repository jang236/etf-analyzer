# etf-analyzer

이 저장소에는 두 가지가 있다.

1. ETF 분석기 (루트의 파이썬 파일들): FastAPI + MCP 서버. `main.py`, `mcp_server.py`, `naver_etf.py` 등.
2. 부코드 대본 자동화 시스템 (`bucode-script/`, `.claude/agents/`, `.claude/skills/`): 유튜브 대본을 기획부터 검수까지 에이전트로 만드는 파이프라인. 시작은 `bucode-script/README.md`.

## 대화 규칙

- 한국어로 답한다.
- 질문은 한 번에 하나만 한다. 여러 질문을 한 번에 묻지 않는다.
- 결정 지점에서는 산출물 요약 표 하나와 질문 하나만 보여준다. 전문은 파일에 있다.

## 대본 시스템 작업 규칙

- 모든 에이전트는 `bucode-script/knowledge/`의 기준을 먼저 읽는다. 충돌하면 `essence.md`가 우선한다.
- 종목, 수치, 인용을 지어내지 않는다. 없는 데이터는 "필요한 데이터"로 적는다.
- 대본 작업으로 ETF 분석기 코드를 건드리지 않는다. 시연 실행기는 분석기 함수를 읽어서 호출만 한다.
- 타인 영상 자막(`bucode-script/projects/*/transcripts/*.txt`)은 커밋하지 않는다.
- 프로젝트 경로는 항상 `bucode-script/projects/<slug>/`다.
- 데이터는 구글 시트 "레퍼런스 DB"에서 읽고 쓴다. 탭과 규칙은 `bucode-script/library/sheet-map.md`. 브리프에 수집 표를 옮기게 하지 않는다.
- 단계가 끝날 때마다 구글 시트 "대본 제작 로그"에 기록한다. 규칙과 시트 ID는 `bucode-script/library/production-log.md`.
- 종목 데이터는 재무분석기 MCP(`mcp__AI__*`)에서 가져온다. 이 환경에서는 네이버, 야후, DART, 유튜브가 차단돼 있다.
- 결정 지점은 기획 승인, 시연 승인, 최종 승인 세 곳이다. 그 사이는 멈추지 않고 돌린다.
- 결정 지점에서 부코드가 고른 것은 "대본 제작 로그"의 하이라이트 탭에 이유와 함께 자동 기록한다.

## 스킬

- `/script-new <slug>`: 새 영상 브리프 만들기
- `/script-pipeline <slug>`: 단계별 진행
- `/script-review <파일>`: 대본 하나 검수
- `/script-retro <slug>`: 공개 2주 뒤 성과를 결정과 묶어 기록
- `/script-recall <키워드>`: 과거에 좋았던 선택 꺼내 보기
