# Coin Auto Trading (Binance)

Binance USDT-M 선물 급등 숏 전략 봇입니다. Bybit 봇(`Coin_auto_trading_bybit`)과 동일한 전략·멀티 계정 구조를 사용합니다.

## 전략 요약

| 항목 | 기본값 |
|------|--------|
| 급등 스캔 | +25%, 24h 거래대금 100k USDT |
| ST 감시 | 상위 30개, sticky (진입/포지션 시에만 제거) |
| 진입 | 4h SuperTrend = -1, ~50 USDT limit +1%, 5x |
| 청산 | 4h SuperTrend → 1, 시장가 + 재시도 |
| 재진입 | OFF |
| 최대 포지션 | 봇 추적 50개 (수동 포지션 제외) |

## Environment Variables

`.env` 파일을 프로젝트 루트에 두고 API 키를 설정합니다. 예시는 `.env.example`을 참고하세요.

- 필수: `BINANCE_API_KEY` / `BINANCE_SECRET` (또는 `BINANCE_API_KEY_SH` / `BINANCE_SECRET_SH`)
- 멀티 계정: `BINANCE_API_KEY_JK`, `BINANCE_API_KEY_JK_2` 등

## Run

```bash
# sh 계정 (기본)
python Binance_SH_1.py

# jk / jk2 계정 (별도 터미널)
python run_binance_account.py jk
python run_binance_account.py jk2
```

계정마다 `state/<계정>/`, `logs/<계정>/` 가 분리됩니다. **같은 계정을 두 터미널에서 동시에 실행하지 마세요.**

## Logging

- 로그 이벤트 규칙: `docs/logging_events.md`

## Trade Journal Migration

```bash
python migrate_trade_journal.py
```

## Tests

```bash
python -m unittest discover -s tests -v
```
