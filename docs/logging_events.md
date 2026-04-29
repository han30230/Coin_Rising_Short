# Logging Events Convention

이 문서는 `coin_rising_short` 전략의 구조화 로그(JSON line) 규칙을 정의합니다.

## Base Fields

모든 파일 로그(`logs/bot.log`)에는 아래 필드가 기본 포함됩니다.

- `ts`: UTC ISO-8601 timestamp
- `level`: log level (`INFO`, `WARNING`, `ERROR` ...)
- `logger`: logger name (예: `coin_rising_short.orders`)
- `msg`: 사람이 읽는 메시지
- `event`: 머신 파싱용 이벤트 키
- `env`: 실행 환경 (`mainnet` / `testnet`)
- `strategy`: 전략 식별자 (현재 `coin_rising_short`)
- `exchange`: 거래소 식별자 (현재 `binance_futures`)

## Event Naming Rules

- `snake_case`만 사용
- 동사 기반 과거형 또는 상태형으로 명확히 작성
  - 좋은 예: `order_placed`, `sync_completed`, `timestamp_resync`
- 너무 일반적인 이름 금지
  - 나쁜 예: `error`, `done`, `status`
- 기존 의미와 충돌되는 이름 재사용 금지

## Recommended Extra Fields

이벤트 성격에 맞춰 `extra`에 아래 컨텍스트를 추가합니다.

- 주문 관련: `symbol`, `order_id`, `side`, `direction`, `price`, `qty`, `status_code`
- 감시 관련: `symbol`, `rank`, `last_price`, `change_pct`
- 동기화 관련: `tracked_symbols`
- 재시도/제한 관련: `wait_sec`, `attempt`

숫자 정밀도가 중요한 값(가격/수량/퍼센트)은 문자열(`str(Decimal)`)로 저장을 권장합니다.

## Current Event Catalog

### Startup / Runtime

- `startup`
- `time_sync_done`
- `hedge_mode_checked`

### Sync

- `state_empty`
- `sync_started`
- `sync_completed`

### Market Monitor

- `gainer_ranked`
- `entry_filled`
- `entry_recorded`
- `reentry_recorded`
- `entry_closed_without_tp`

### Orders

- `leverage_set`
- `leverage_set_failed`
- `order_placed`
- `order_place_failed`
- `tp_order_placed`

### Rate Limit / Time

- `http_rate_limit_get`
- `http_rate_limit_post`
- `signed_rate_limit`
- `timestamp_resync`

## Example

```json
{
  "ts": "2026-03-23T12:34:56.123456+00:00",
  "level": "INFO",
  "logger": "coin_rising_short.orders",
  "msg": "SELL 주문 성공: BTCUSDT @ 70000.1 (positionSide=SHORT, orderId=123456789)",
  "event": "order_placed",
  "env": "mainnet",
  "strategy": "coin_rising_short",
  "exchange": "binance_futures",
  "symbol": "BTCUSDT",
  "order_id": 123456789,
  "side": "SELL",
  "price": "70000.1",
  "qty": "0.01",
  "position_side": "SHORT"
}
```

## Change Process

새 이벤트 추가 시 아래를 함께 반영합니다.

1. 코드에서 `logger.<level>(..., extra={"event": "<new_event>", ...})` 사용
2. 이 문서의 `Current Event Catalog`에 이벤트 등록
3. 이벤트명/필수 컨텍스트가 규칙을 만족하는지 점검
