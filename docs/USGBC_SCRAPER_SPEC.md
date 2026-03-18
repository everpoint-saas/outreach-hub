# USGBC Directory Scraper - Implementation Spec

> Created: 2026-02-09
> Status: Ready for implementation
> Assignee: Gemini (implementation), Claude (strategy/review)

---

## Overview

USGBC(US Green Building Council)의 공개 디렉토리에서 LEED 전문가 및 기업 정보를 수집하는 스크래퍼.
기존 Google Maps 스크래퍼 대비 **이메일이 직접 노출**되어 크롤링 단계를 건너뛸 수 있음.

### Why USGBC?

| 비교 | Google Maps | USGBC Directory |
|------|-------------|-----------------|
| 이메일 직접 노출 | X (웹사이트 크롤링 필요) | **O (프로필에 있음)** |
| LEED 확실성 | 키워드 기반 (불확실) | **100% (자격증 보유자)** |
| 웹사이트 포함 | ~70% | **O (Organizations)** |
| 규모 | 무한 (검색 기반) | People 130K / Orgs 4K |
| 이메일 수집 성공률 | ~20% | **~80-90%** |

---

## Architecture: Elasticsearch API Direct Access

USGBC 디렉토리는 Elasticsearch 기반. Playwright 불필요. HTTP POST로 직접 데이터 조회 가능.

### API Endpoint

```
POST https://pr-msearch.usgbc.org/{index}/_search
Content-Type: application/json
```

### Index Names

| Directory | Index Name |
|-----------|-----------|
| People (개인) | `elasticsearch_index_live_usgbc_persons_dev` |
| Organizations (기업) | `elasticsearch_index_live_usgbc_usgbc_org_dev` |

### Authentication

공개 API. API 키, 인증 토큰 없음. Anonymous access.

---

## Part 1: Organizations Scraper (Priority)

### Target

USGBC 멤버 기업 중 "Building/LEED Consultants" 카테고리, 미국 소재.
약 **4,000개** 기업.

### Response Fields

| Field | Description | Example |
|-------|-------------|---------|
| `title` | 회사명 | "Longevity Partners" |
| `org_email` | 회사 이메일 | "info@longevity.co" |
| `org_phone` | 전화번호 | "+1 512-555-1234" |
| `org_website` | 웹사이트 URL | "https://longevity.co" |
| `org_mailto` | 담당자 이름 | "John Smith" |
| `level` | 멤버십 레벨 | "Silver" |
| `member_category` | 카테고리 | "Professional Firms" |
| `member_subcategory` | 서브카테고리 | "Building/LEED Consultants" |
| `city_name` | 도시 | "Austin" |
| `state_name` | 주 | "Texas" |
| `country_name` | 국가 | "United States" |
| `org_membersince` | 가입일 (timestamp) | 1420070400 |
| `org_revenue` | 매출 규모 | "$1M-$10M" |

### Query Template

```json
{
  "query": {
    "bool": {
      "must": [
        {"match": {"published_status": "1"}},
        {"match": {"show_org_name_dir": "Yes"}},
        {"range": {"org_validto": {"gte": <CURRENT_UNIX_TIMESTAMP>}}}
      ],
      "must_not": [
        {"terms": {"country_name.raw": ["Iran", "Sudan", "Syria", "North Korea"]}},
        {"match": {"per_associations.raw": "Chapter"}}
      ],
      "filter": [
        {"terms": {"member_subcategory.raw": ["Building/LEED Consultants"]}},
        {"terms": {"country_name.raw": ["United States"]}}
      ]
    }
  },
  "from": 0,
  "size": 100,
  "sort": [{"org_membersince": {"order": "desc"}}],
  "track_total_hits": true
}
```

### Pagination Strategy

Default `size` is 12. Increase to **100** per request to reduce API calls.
4,000 orgs / 100 per page = **40 requests**.

```python
for page in range(0, total_hits, 100):
    query["from"] = page
    # POST request
    # Parse results
    # Delay between requests
```

### Available Filters

| Filter | Field | Example Values |
|--------|-------|---------------|
| Subcategory | `member_subcategory.raw` | "Building/LEED Consultants", "Energy Services", "Engineering" |
| Country | `country_name.raw` | "United States", "Canada" |
| State | `state_name.raw` | "California", "New York", "Texas" |
| Level | `level.raw` | "Platinum", "Gold", "Silver", "Organizational" |

### Optional: State-by-State Scraping

미국 전체를 한번에 가져와도 되고, 주별로 나눠서 가져올 수도 있음:

```json
"filter": [
    {"terms": {"member_subcategory.raw": ["Building/LEED Consultants"]}},
    {"terms": {"country_name.raw": ["United States"]}},
    {"terms": {"state_name.raw": ["California"]}}
]
```

---

## Part 2: People Scraper

### Target

LEED AP BD+C 자격증 보유자, 미국 소재.
약 **130,000명** (전체), BD+C 필터 시 더 적음.

### Response Fields

| Field | Description | Example |
|-------|-------------|---------|
| `per_fname` | 이름 | "Amanda" |
| `per_lname` | 성 | "Frazier" |
| `per_email` | 이메일 | "amanda@company.com" |
| `per_phone` | 전화번호 | "+1 555-123-4567" |
| `per_orgname` | 소속 회사 | "Green Building Corp" |
| `per_job_title` | 직함 | "Senior Estimator" |
| `leed_credential` | LEED 자격증 | "LEED AP BD+C" |
| `country_name` | 국가 | "United States" |
| `state_name` | 주 | "California" |

### Query Template

```json
{
  "query": {
    "bool": {
      "must": [
        {"match": {"published_status": "1"}},
        {"match": {"show_name_in_directory": "Yes"}},
        {
          "bool": {
            "should": [
              {"exists": {"field": "leed_credential"}},
              {"exists": {"field": "relationships"}}
            ]
          }
        }
      ],
      "must_not": [
        {"match": {"per_fname": ""}},
        {"terms": {"country_name.raw": ["Iran", "Sudan", "Syria", "North Korea"]}}
      ],
      "filter": [
        {"terms": {"leed_credential.raw": ["LEED AP BD+C"]}},
        {"terms": {"country_name.raw": ["United States"]}}
      ]
    }
  },
  "from": 0,
  "size": 100,
  "sort": [{"updated_date": {"order": "desc"}}],
  "track_total_hits": true
}
```

### Available Credential Filters

- `LEED Green Associate`
- `LEED AP BD+C` (Building Design + Construction) - **primary target**
- `LEED AP O+M` (Operations + Maintenance)
- `LEED AP ID+C` (Interior Design + Construction)
- `LEED AP ND` (Neighborhood Development)
- `LEED AP Homes`
- `LEED Fellow`

---

## Implementation Plan

### File Structure

```
mailing_list/
  usgbc_scraper.py          # NEW: USGBC API scraper
  gui/
    main_window.py           # UPDATE: Add USGBC tab or integrate into existing tabs
```

### usgbc_scraper.py - Skeleton

```python
"""
USGBC Directory Scraper

Scrapes LEED professionals and organizations from USGBC's public
Elasticsearch-based directory API.

No Playwright needed - direct HTTP API calls.
"""

import requests
import pandas as pd
import time
import os
from datetime import datetime

API_BASE = "https://pr-msearch.usgbc.org"
ORGS_INDEX = "elasticsearch_index_live_usgbc_usgbc_org_dev"
PEOPLE_INDEX = "elasticsearch_index_live_usgbc_persons_dev"

PAGE_SIZE = 100
DELAY_BETWEEN_REQUESTS = 1.0  # seconds, be respectful


class USGBCScraper:
    def __init__(self, log_callback=print):
        self.log = log_callback
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        })

    def _search(self, index: str, query: dict) -> dict:
        """Execute Elasticsearch query against USGBC API."""
        url = f"{API_BASE}/{index}/_search"
        response = self.session.post(url, json=query)
        response.raise_for_status()
        return response.json()

    def scrape_organizations(
        self,
        subcategory: str = "Building/LEED Consultants",
        country: str = "United States",
        state: str = None,
        level: str = None,
        max_results: int = None
    ) -> str:
        """
        Scrape USGBC member organizations.

        Args:
            subcategory: Member subcategory filter
            country: Country filter
            state: Optional state filter (e.g., "California")
            level: Optional membership level filter (e.g., "Platinum")
            max_results: Optional limit on total results

        Returns:
            str: Path to output CSV file
        """
        self.log(f"Scraping USGBC Organizations: {subcategory} in {country}")

        # Build filters
        filters = [
            {"terms": {"member_subcategory.raw": [subcategory]}},
            {"terms": {"country_name.raw": [country]}}
        ]
        if state:
            filters.append({"terms": {"state_name.raw": [state]}})
        if level:
            filters.append({"terms": {"level.raw": [level]}})

        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"published_status": "1"}},
                        {"match": {"show_org_name_dir": "Yes"}},
                        {"range": {"org_validto": {"gte": int(time.time())}}}
                    ],
                    "must_not": [
                        {"terms": {"country_name.raw": ["Iran", "Sudan", "Syria", "North Korea"]}},
                        {"match": {"per_associations.raw": "Chapter"}}
                    ],
                    "filter": filters
                }
            },
            "from": 0,
            "size": PAGE_SIZE,
            "sort": [{"org_membersince": {"order": "desc"}}],
            "track_total_hits": True
        }

        all_orgs = []
        offset = 0

        # First request to get total count
        query["from"] = 0
        result = self._search(ORGS_INDEX, query)
        total = result["hits"]["total"]["value"]
        self.log(f"Total organizations found: {total}")

        if max_results:
            total = min(total, max_results)

        while offset < total:
            if offset > 0:
                query["from"] = offset
                result = self._search(ORGS_INDEX, query)

            hits = result["hits"]["hits"]
            if not hits:
                break

            for hit in hits:
                src = hit["_source"]
                org = {
                    "Company": src.get("title", ""),
                    "Email": src.get("org_email", ""),
                    "Phone": src.get("org_phone", ""),
                    "Website": src.get("org_website", ""),
                    "Contact_Person": src.get("org_mailto", ""),
                    "Level": src.get("level", ""),
                    "Category": src.get("member_category", ""),
                    "Subcategory": src.get("member_subcategory", ""),
                    "City": src.get("city_name", ""),
                    "State": src.get("state_name", ""),
                    "Country": src.get("country_name", ""),
                    "Member_Since": src.get("org_membersince", ""),
                    "Revenue": src.get("org_revenue", ""),
                    "Source": "usgbc_organizations",
                    "Scraped_At": datetime.now().isoformat()
                }
                all_orgs.append(org)

            offset += PAGE_SIZE
            self.log(f"  Fetched {min(offset, total)}/{total} organizations...")
            time.sleep(DELAY_BETWEEN_REQUESTS)

        # Save to CSV
        if all_orgs:
            df = pd.DataFrame(all_orgs)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"data/raw/usgbc_orgs_{timestamp}.csv"
            os.makedirs("data/raw", exist_ok=True)
            df.to_csv(output_file, index=False)
            self.log(f"Saved {len(all_orgs)} organizations to {output_file}")
            return output_file
        else:
            self.log("No organizations found.")
            return None

    def scrape_people(
        self,
        credential: str = "LEED AP BD+C",
        country: str = "United States",
        state: str = None,
        max_results: int = None
    ) -> str:
        """
        Scrape LEED professionals from USGBC directory.

        Args:
            credential: LEED credential filter
            country: Country filter
            state: Optional state filter
            max_results: Optional limit on total results

        Returns:
            str: Path to output CSV file
        """
        self.log(f"Scraping USGBC People: {credential} in {country}")

        filters = [
            {"terms": {"leed_credential.raw": [credential]}},
            {"terms": {"country_name.raw": [country]}}
        ]
        if state:
            filters.append({"terms": {"state_name.raw": [state]}})

        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"published_status": "1"}},
                        {"match": {"show_name_in_directory": "Yes"}},
                        {
                            "bool": {
                                "should": [
                                    {"exists": {"field": "leed_credential"}},
                                    {"exists": {"field": "relationships"}}
                                ]
                            }
                        }
                    ],
                    "must_not": [
                        {"match": {"per_fname": ""}},
                        {"terms": {"country_name.raw": ["Iran", "Sudan", "Syria", "North Korea"]}}
                    ],
                    "filter": filters
                }
            },
            "from": 0,
            "size": PAGE_SIZE,
            "sort": [{"updated_date": {"order": "desc"}}],
            "track_total_hits": True
        }

        all_people = []
        offset = 0

        query["from"] = 0
        result = self._search(PEOPLE_INDEX, query)
        total = result["hits"]["total"]["value"]
        self.log(f"Total people found: {total}")

        if max_results:
            total = min(total, max_results)

        while offset < total:
            if offset > 0:
                query["from"] = offset
                result = self._search(PEOPLE_INDEX, query)

            hits = result["hits"]["hits"]
            if not hits:
                break

            for hit in hits:
                src = hit["_source"]
                person = {
                    "Name": f"{src.get('per_fname', '')} {src.get('per_lname', '')}".strip(),
                    "Email": src.get("per_email", ""),
                    "Phone": src.get("per_phone", ""),
                    "Company": src.get("per_orgname", ""),
                    "Title": src.get("per_job_title", ""),
                    "Credential": src.get("leed_credential", ""),
                    "State": src.get("state_name", ""),
                    "Country": src.get("country_name", ""),
                    "Source": "usgbc_people",
                    "Scraped_At": datetime.now().isoformat()
                }
                all_people.append(person)

            offset += PAGE_SIZE
            self.log(f"  Fetched {min(offset, total)}/{total} people...")
            time.sleep(DELAY_BETWEEN_REQUESTS)

        # Save to CSV
        if all_people:
            df = pd.DataFrame(all_people)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"data/raw/usgbc_people_{timestamp}.csv"
            os.makedirs("data/raw", exist_ok=True)
            df.to_csv(output_file, index=False)
            self.log(f"Saved {len(all_people)} people to {output_file}")
            return output_file
        else:
            self.log("No people found.")
            return None


if __name__ == "__main__":
    scraper = USGBCScraper()

    # Test: Scrape first 100 LEED consultant organizations in US
    scraper.scrape_organizations(max_results=100)

    # Test: Scrape first 100 LEED AP BD+C professionals in US
    scraper.scrape_people(max_results=100)
```

---

## Pipeline Integration

### CSV Output Format

USGBC 스크래퍼의 CSV 출력은 기존 파이프라인(`process_leads.py`)과 호환되어야 함.

**Organizations CSV columns:**
```
Company, Email, Phone, Website, Contact_Person, Level, Category, Subcategory,
City, State, Country, Member_Since, Revenue, Source, Scraped_At
```

**People CSV columns:**
```
Name, Email, Phone, Company, Title, Credential, State, Country, Source, Scraped_At
```

### process_leads.py 수정 사항

USGBC 데이터는 **이미 이메일이 있으므로** 기존 파이프라인의 email crawling 단계를 건너뜀.

1. `load_raw_data()`: USGBC CSV도 `data/raw/`에서 로딩됨 (이미 glob 패턴으로 처리)
2. `is_blacklisted()`: USGBC 데이터에는 blacklist 대상 없음 (이미 LEED 관련 확인됨)
3. `score_lead()`: USGBC는 이미 LEED 확인됨 -> 기본 점수를 높게 설정
4. 소스 식별: `_source_file`에 "usgbc"가 포함되면 USGBC 소스로 인식

**수정 포인트:**

```python
# process_leads.py - score_lead() 수정
def score_lead(row: pd.Series) -> int:
    # ... existing logic ...

    # USGBC leads are pre-qualified LEED professionals/companies
    if "_source_file" in row and "usgbc" in str(row["_source_file"]).lower():
        score = max(score, 5)  # High base score for USGBC leads

    return score
```

```python
# process_leads.py - dedup 로직에 USGBC 추가
# Split by source type
is_linkedin = df["_source_file"].str.contains("linkedin", case=False, na=False)
is_usgbc = df["_source_file"].str.contains("usgbc", case=False, na=False)
df_google = df[~is_linkedin & ~is_usgbc]
df_linkedin = df[is_linkedin]
df_usgbc = df[is_usgbc]

# USGBC: dedup by Email (most reliable identifier)
df_usgbc = df_usgbc.drop_duplicates(subset=["Email"], keep="first")

# Recombine
df = pd.concat([df_usgbc, df_google, df_linkedin], ignore_index=True)
```

```python
# process_leads.py - daily targets에서 USGBC 우선
# USGBC targets first (highest quality), then Google Maps
is_usgbc = df["_source_file"].str.contains("usgbc", case=False, na=False)
df_usgbc_targets = df[is_usgbc].head(DAILY_TARGET_COUNT)
remaining = DAILY_TARGET_COUNT - len(df_usgbc_targets)
df_google_targets = df[~is_usgbc].head(remaining)
today = pd.concat([df_usgbc_targets, df_google_targets], ignore_index=True)
```

---

## GUI Integration

### Option A: Separate USGBC Tab (Recommended)

`gui/tab_usgbc.py` 생성. 기존 Google Maps 탭과 유사한 구조:

- Credential 선택 드롭다운 (LEED AP BD+C, O+M, ID+C, etc.)
- Country/State 필터
- "Scrape Organizations" / "Scrape People" 버튼
- Progress log
- 결과 미리보기 테이블

### Option B: Existing Tab에 통합

Google Maps 탭에 "Source" 드롭다운 추가:
- Google Maps
- USGBC Organizations
- USGBC People

선택에 따라 UI 옵션이 변경됨.

### Worker Thread

```python
# gui/workers.py - 추가
class USGBCScraperThread(QThread):
    log_signal = Signal(str)
    finished_signal = Signal(str)

    def __init__(self, mode, params):
        super().__init__()
        self.mode = mode  # "organizations" or "people"
        self.params = params

    def run(self):
        from usgbc_scraper import USGBCScraper
        scraper = USGBCScraper(log_callback=self.log_signal.emit)

        if self.mode == "organizations":
            result = scraper.scrape_organizations(**self.params)
        else:
            result = scraper.scrape_people(**self.params)

        if result:
            self.finished_signal.emit(f"Done! Saved to: {result}")
        else:
            self.finished_signal.emit("No results found.")
```

---

## Rate Limiting & Respect

USGBC는 공개 디렉토리이지만 과도한 요청은 피해야 함:

- `DELAY_BETWEEN_REQUESTS = 1.0` (1초 간격)
- `PAGE_SIZE = 100` (한번에 100개씩, 총 40회 요청으로 4000개 기업)
- Organizations 전체 수집: ~40초 소요
- People 전체 수집 (BD+C만): 수에 따라 다르지만 분 단위
- User-Agent 헤더 포함
- 에러 시 exponential backoff 적용

---

## Expected Results

### Organizations (4,000개)

```
전체 USGBC 멤버 기업: ~4,000
  → Building/LEED Consultants 필터: 수백~천 개
  → 이메일 있는 비율: ~80-90%
  → 웹사이트 있는 비율: ~90%+

이메일 없는 10-20%는 기존 crawl_emails.py로 웹사이트에서 추출 가능
```

### People (130,000명 중 BD+C 필터)

```
LEED AP BD+C + US: 수천~수만 명
  → 이메일 있는 비율: ~60-70% (개인 프로필이라 덜 채워놓는 경우)
  → 회사명 있는 비율: ~80%+

이메일 없으면 회사명 -> 도메인 추측 -> email crawl 가능
```

---

## Implementation Priority

```
1. usgbc_scraper.py 작성 (이 문서의 skeleton 기반)
2. Organizations 스크래핑 먼저 테스트 (수가 적고, 이메일/웹사이트 있는 비율 높음)
3. process_leads.py에 USGBC 소스 통합
4. People 스크래핑 추가
5. GUI 탭 추가
```

---

## Testing

### Quick Smoke Test

```python
# Terminal에서 바로 테스트 가능
python -c "
from usgbc_scraper import USGBCScraper
s = USGBCScraper()
s.scrape_organizations(max_results=10)
"
```

### Validation

1. CSV 파일이 `data/raw/usgbc_orgs_*.csv`에 생성되는지 확인
2. Email 컬럼이 비어있지 않은 비율 체크
3. `process_leads.py` 실행 시 USGBC 소스가 인식되는지 확인
4. `today_targets.csv`에 USGBC 리드가 포함되는지 확인
