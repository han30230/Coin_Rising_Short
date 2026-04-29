import csv
import os
from typing import Dict, List

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(PROJECT_ROOT, "logs", "trade_journal.csv")
BACKUP_PATH = os.path.join(PROJECT_ROOT, "logs", "trade_journal.backup.csv")

HEADER_MAP: Dict[str, str] = {
    "event": "이벤트",
    "symbol": "코인",
    "direction": "방향",
    "entry_time_utc": "진입시간(UTC)",
    "exit_time_utc": "청산시간(UTC)",
    "entry_order_id": "진입주문ID",
    "tp_order_id": "청산주문ID",
    "entry_price": "진입가",
    "exit_price": "청산가",
    "qty": "수량",
    "notional_usdt": "명목금액USDT",
    "pnl_usdt": "PNL_USDT",
    "profit_pct": "수익률(%)",
    "leveraged_profit_pct": "레버리지적용수익률(%)",
    "note": "비고",
}

TARGET_HEADERS: List[str] = [
    "이벤트",
    "코인",
    "방향",
    "진입시간(UTC)",
    "청산시간(UTC)",
    "진입주문ID",
    "청산주문ID",
    "진입가",
    "청산가",
    "수량",
    "명목금액USDT",
    "PNL_USDT",
    "수익률(%)",
    "레버리지적용수익률(%)",
    "비고",
]


def main() -> None:
    if not os.path.isfile(CSV_PATH):
        print(f"[INFO] 파일 없음: {CSV_PATH}")
        return

    with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        original_headers = reader.fieldnames or []
        if not original_headers:
            print("[INFO] 헤더가 없는 파일입니다. 작업 종료.")
            return

        # 이미 한글 헤더면 종료
        if all(h in TARGET_HEADERS for h in original_headers):
            print("[INFO] 이미 한글 헤더 형식입니다. 작업 없음.")
            return

        rows = list(reader)

    os.makedirs(os.path.dirname(BACKUP_PATH), exist_ok=True)
    with open(BACKUP_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=original_headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    converted_rows = []
    for row in rows:
        new_row = {k: "" for k in TARGET_HEADERS}
        for old_key, value in row.items():
            new_key = HEADER_MAP.get(old_key, old_key)
            if new_key in new_row:
                new_row[new_key] = value
        converted_rows.append(new_row)

    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TARGET_HEADERS)
        writer.writeheader()
        for row in converted_rows:
            writer.writerow(row)

    print("[OK] 마이그레이션 완료")
    print(f" - 원본 백업: {BACKUP_PATH}")
    print(f" - 변환 파일: {CSV_PATH}")


if __name__ == "__main__":
    main()
