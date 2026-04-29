import os
from decimal import Decimal, getcontext
from dotenv import load_dotenv

getcontext().prec = 16

_PACKAGE_ROOT = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_PACKAGE_ROOT)

load_dotenv(dotenv_path=os.path.join(_PROJECT_ROOT, ".env"))

API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_SECRET")

ENV = (os.getenv("BINANCE_ENV") or "mainnet").lower()
BASE_URL_FUTURES = "https://fapi.binance.com" if ENV == "mainnet" else "https://testnet.binancefuture.com"
BASE_URL_SPOT = "https://api.binance.com" if ENV == "mainnet" else "https://testnet.binance.vision"

if not API_KEY or not API_SECRET:
    raise Exception("❌ .env에서 API 키를 불러오지 못했습니다!")

POSITION_USDT = Decimal("50")
PREMIUM_PCT = Decimal("0.01")
DISCOUNT_PCT = Decimal("0.01")
GAINER_THRESHOLD_PCT = Decimal("20")
MIN_VOLUME_USDT = Decimal("1_000_000")
REENTRY_RISE_PCT = Decimal("50")
REENTRY_MAX_COUNT = 4
TAKE_PROFIT_PCT = Decimal("10")
POLL_INTERVAL_SEC = 10

LEVERAGE = int(os.getenv("LEVERAGE") or "5")
HTTP_MAX_RETRIES = int(os.getenv("HTTP_MAX_RETRIES") or "5")

POSITION_STATE_PATH = os.getenv("POSITION_STATE_FILE") or os.path.join(
    _PROJECT_ROOT, "position_state.json"
)
TRADE_JOURNAL_PATH = os.getenv("TRADE_JOURNAL_FILE") or os.path.join(
    _PROJECT_ROOT, "logs", "trade_journal.csv"
)
FORCE_HEDGE = (os.getenv("FORCE_HEDGE") or "false").lower() == "true"

# 업비트 상장 코인만 거래 대상으로 제한 (기본: true)
FILTER_UPBIT_LISTED = (os.getenv("FILTER_UPBIT_LISTED") or "true").lower() == "true"

# 추가 펀더멘털/상장 연차 필터
MIN_LISTED_DAYS = int(os.getenv("MIN_LISTED_DAYS") or "365")
MIN_MARKET_CAP_USD = Decimal(os.getenv("MIN_MARKET_CAP_USD") or "200000000")
MIN_MCAP_FDV_RATIO = Decimal(os.getenv("MIN_MCAP_FDV_RATIO") or "0.65")

# 펀딩비 필터: lastFundingRate 가 이 값보다 커야 진입 허용
# -0.005 == -0.5%
MIN_FUNDING_RATE = Decimal(os.getenv("MIN_FUNDING_RATE") or "-0.005")
