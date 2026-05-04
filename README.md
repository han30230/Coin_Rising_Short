# Coin Auto Trading

자동매매 실행 진입점과 전략 코드를 포함한 프로젝트입니다.

## Environment Variables

`.env` 파일을 프로젝트 루트에 두고 아래 키를 설정합니다.

- 필수
  - `BINANCE_API_KEY`
  - `BINANCE_SECRET`
- 선택
  - `BINANCE_ENV` (`mainnet` 또는 `testnet`, 기본값: `mainnet`)
  - `LEVERAGE` (기본값: `5`)
  - `HTTP_MAX_RETRIES` (기본값: `5`)
  - `POSITION_STATE_FILE` (기본값: `position_state.json`)
  - `TRADE_JOURNAL_FILE` (기본값: `logs/trade_journal.csv`)
  - `FILTER_UPBIT_LISTED` (`true`/`false`, 기본값: `true`)
  - `MIN_FUTURES_LISTING_AGE_DAYS` (기본값: `365`, Binance 선물 `onboardDate` 기준)
  - `MIN_FUNDING_RATE` (기본값: `-0.005`, 즉 -0.5%)
  - `FORCE_HEDGE` (`true`/`false`, 기본값: `false`)

예시:

```env
BINANCE_API_KEY=your_api_key
BINANCE_SECRET=your_secret
BINANCE_ENV=mainnet
LEVERAGE=5
HTTP_MAX_RETRIES=5
POSITION_STATE_FILE=position_state.json
TRADE_JOURNAL_FILE=logs/trade_journal.csv
FILTER_UPBIT_LISTED=true
MIN_FUTURES_LISTING_AGE_DAYS=365
MIN_FUNDING_RATE=-0.005
FORCE_HEDGE=false
```

## Logging

- 로그 이벤트 규칙 문서: `docs/logging_events.md`

## Run

- 루트에서 실행:
  - `python Binance_SH_1.py`

## Trade Journal Migration

- 기존 영문 헤더 거래일지를 한글 헤더로 변환:
  - `python migrate_trade_journal.py`
- 백업 파일:
  - `logs/trade_journal.backup.csv`
