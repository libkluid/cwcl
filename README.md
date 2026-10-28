# changwon-jobs

창원시(의창구·성산구) 관공서·공공기관 **직접 채용** 청소 일자리를 수집해
정적 사이트로 배포하는 파이프라인.

## 구조

목적별 4개 레이어로 나뉜다.

```
src/jobs/
├── load/     # 소스별 원본 수집 (목록 rows + 상세 detail)
│   ├── _http.py     # 공용 httpx 클라이언트 + 텍스트/날짜 정규화
│   ├── gne.py       # 경남교육청 교육공무직원(청소원)
│   ├── gojobs.py    # 나라일터(국가기관·지자체 직접 채용)
│   └── changwon.py  # 창원시 통합 일자리 플랫폼
├── merge/    # 목록+상세 → 정규화 문서, dlt 파이프라인
│   ├── normalize.py # iter_documents(): 공통 스키마로 병합
│   └── pipeline.py  # dlt resource + sync()
├── store/    # 누적 데이터 (JSONL)
│   └── jsonl.py     # load/save/upsert/read (보존기간 지원)
└── page/     # store → Hugo 콘텐츠
    └── hugo.py      # write_content(): 문서별 markdown 프론트매터 생성

site/         # Hugo 사이트 (page 레이어 출력)
data/jobs.jsonl  # 누적 스토어 (표시용, 보존기간 적용, 커밋 대상)
data/seen.txt    # id 원장 (지금까지 수집한 모든 id, 커밋 대상)
```

문서 스키마: `{id, source, title, posted_on, closes_on, url, body}`.
`id`는 `<source>:<key>` 로, 병합/중복 제거 키다.

## 동작

```
load (목록+상세)  →  merge (정규화)  →  dlt/DuckDB(임시)  →  store(data/jobs.jsonl, 누적·커밋)
                                                              →  page(site/content/jobs/*.md)  →  hugo  →  site/public
```

- dlt/DuckDB 목적지는 **일회성**이다. 누적 데이터는 커밋되는 `data/jobs.jsonl`에 있고,
  사이트는 이 파일에서 렌더한다.
- `posted_on` 기준 보존기간(기본 180일)으로 오래된 항목을 정리한다.
- 각 공고의 게시일(`posted_on`)과 마감일(`closes_on`)을 사이트에 함께 표시한다.

## 증분 수집
매 실행이 전체를 다시 긁지 않도록 이미 수집한 공고는 건너뛴다.
- 목록에서 이미 아는 id는 **상세 요청을 생략**하고, 한 페이지가 전부 아는 공고면
  페이지네이션을 **중단**한다(목록이 최신순이라 성립).
- 보존기간으로 `data/jobs.jsonl`에서 잘려나간 id도 `data/seen.txt`(id 원장)에 남아
  계속 skip 된다. 원장은 한 번 본 **모든 목록 행의 id**를 담아, 청소 공고가 섞여
  있지 않은 changwon 페이지도 조기 종료된다.
- 강제 전체 재수집: `--full`.

## 소스별 필터
- `gne`: `region=창원` + 세부분류 `청소원`
- `gojobs`: `keyword=청소` + 근무지역 코드 `--gojobs-areas`(기본 `48121,48123` =
  창원시 의창구·성산구). 나라일터는 시군구 코드와 지역명을 **함께** 보내야 필터가 걸린다.
- `changwon`: 업직종/회사명/모집내용 키워드(`--match`, 기본 청소·미화·환경)

## 사용

```bash
uv sync

# 수집 + 정규화 → 스토어 병합
uv run jobs sync --max-pages 3 --detail-delay 0.5

# 스토어 → Hugo 콘텐츠 → 사이트 빌드
uv run jobs render
hugo --source site --minify

# 위 둘을 한 번에
uv run jobs build --max-pages 3
```

주요 옵션: `--sources`, `--max-pages`, `--delay`, `--detail-delay`, `--limit`,
`--region`, `--keyword`, `--gojobs-areas`, `--match`, `--store`, `--seen`,
`--retention-days`, `--full`.

## GitHub Actions

`.github/workflows/collect-and-deploy.yml` 이 매일 **09:00~19:00 KST 사이 2시간마다**
(09, 11, 13, 15, 17, 19시) 및 수동/push 시:

1. `jobs build` 로 수집·정규화·Hugo 콘텐츠 생성 (증분: 새 공고만)
2. `data/jobs.jsonl`·`data/seen.txt` 변경분을 `[skip ci]` 로 커밋
3. `hugo` 빌드 후 GitHub Pages 로 배포

사전 설정: 저장소 **Settings → Pages → Source = "GitHub Actions"**.
