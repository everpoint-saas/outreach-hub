# LinkedIn X-Ray Scraper - Effectiveness Analysis

> Date: 2026-02-09
> Verdict: **REMOVE from default workflow**

---

## What It Does

Google에서 `site:linkedin.com/in/ "LEED AP BD+C"` 같은 X-Ray 검색을 실행해서
LinkedIn 프로필 정보(이름, 직함, 회사, URL)를 수집한다.

---

## Why It Doesn't Work

### 1. Email이 없다

LinkedIn 프로필은 이메일을 공개하지 않음. 수집되는 데이터:

```
Name: Mary Ellen Mika
Title: Director, Sustainability / Global ESG
Company: Unknown     <-- 대부분 Unknown
LinkedIn_URL: https://www.linkedin.com/in/mary-ellen-mika-a163136
Website: (없음)
Email: (없음)
Phone: (없음)
```

Google Maps에서는 **회사 웹사이트**가 나오니까 거기서 이메일을 크롤링할 수 있는데,
LinkedIn은 웹사이트도 없고 이메일도 없고 전화번호도 없다.

### 2. Company가 대부분 "Unknown"

Google 검색 결과에서 LinkedIn 프로필 제목을 파싱하는 로직:

```
"Mary Ellen Mika - Director, Sustainability - LinkedIn"
  parts[0] = Name
  parts[1] = Title
  parts[2] = "LinkedIn"  --> filtered to "Unknown"
```

Google이 보여주는 검색 결과 타이틀 포맷이 일관성이 없어서, 회사 이름이 제대로 파싱되는 비율이 매우 낮다.

### 3. Pipeline에서 아웃리치 불가능

LinkedIn 리드가 파이프라인에 들어가면:

```
1. Pipeline: score >= 2 (보장됨) -> today_targets.csv에 포함
2. Email Crawler: Website 없음 -> SKIP
3. Mailing Tab: Email 없음 -> SKIP
```

결과적으로 **daily target 15개 중 7-8개를 LinkedIn 리드가 차지**하는데,
이 리드들은 전부 스킵되니까 실제로는 7-8개만 이메일 발송 가능.

### 4. Google CAPTCHA 리스크 증가

LinkedIn X-Ray는 Google **Search** (google.com)를 직접 친다.
Google Maps scraping과 달리 Google Search는 bot detection이 더 강력함.

LinkedIn X-Ray 실행 -> Google Search에서 CAPTCHA 발생 -> IP 플래그 ->
Google Maps scraping까지 영향 받을 수 있음.

---

## Actual Data (2026-01-05)

| Metric | Google Maps | LinkedIn X-Ray |
|--------|-------------|----------------|
| Raw leads | ~200 | 107 |
| Has Website | ~70% | 0% |
| Has Email (after crawl) | ~50% | 0% |
| Has Phone | ~60% | 0% |
| Company identified | ~95% | ~20% |
| **Contactable** | **~75%** | **0%** |

---

## Alternatives (LinkedIn Lead 활용하려면)

LinkedIn 리드를 실제로 활용하려면 별도 경로가 필요:

### Option A: LinkedIn DM (Manual)
- LinkedIn URL이 있으니 직접 DM 보내기
- 장점: 확실한 도달
- 단점: 수동, 일일 연결 요청 제한 (~100개/주)

### Option B: Email Finder API 연동
- Hunter.io, Apollo.io, Snov.io 같은 서비스 사용
- 이름 + 회사 -> 이메일 추측 (first@company.com 패턴)
- 장점: 높은 정확도 (~70-80%)
- 단점: 유료 ($49-99/월), Company가 "Unknown"이면 못 씀

### Option C: LinkedIn Sales Navigator
- LinkedIn 자체 아웃리치 도구
- InMail 기능으로 직접 메시지
- 단점: $99/월, 별도 구독 필요

### Option D: 회사 도메인 추측
- LinkedIn 프로필에서 company가 있는 경우 -> company 도메인 추측
- "Mars" -> mars.com -> crawl_emails.py로 이메일 크롤링
- 장점: 무료, 기존 파이프라인 활용 가능
- 단점: Company가 "Unknown"이면 못 씀 (현재 ~80%)

---

## Recommendation

### 즉시: Default workflow에서 제거
- `process_leads.py`에서 LinkedIn 소스의 50/50 밸런싱 제거
- Google Maps 리드만으로 daily targets 구성
- LinkedIn 탭은 남겨두되, 기본 파이프라인에서 분리

### 추후: LinkedIn DM 별도 워크플로우 구축 (선택)
- LinkedIn URL 기반으로 DM 보내는 별도 기능 추가
- 현재 cold email 파이프라인과는 분리
- LinkedIn 자동화 도구(Expandi, Dripify) 연동 검토

### 코드 변경 포인트
1. `process_leads.py` line 237-246: LinkedIn 밸런싱 로직 제거 또는 비활성화
2. `process_leads.py` line 146-148: LinkedIn 최소 점수 보장 로직 제거
3. `gui/main_window.py`: LinkedIn 탭 유지하되 "Experimental" 표시 또는 별도 export 기능
