"""실행 시점에 설정되는 값 (예: Hedge 모드)."""

IS_HEDGE = False

# 심볼별 일시 스킵(거래소 오픈 금지/점검 등)
# key: symbol, value: unix epoch seconds until which to skip
SKIP_UNTIL: dict[str, int] = {}
