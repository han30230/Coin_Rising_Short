from coin_rising_short import client, config, monitor, orders, runtime, sync


def run() -> None:
    print(f"⚙️ Binance Futures + Spot 공존 필터 버전 시작 (ENV={config.ENV})")
    client.refresh_time_offset()
    print(f"⏱️ 서버 시간 오프셋 동기화 완료 (LEVERAGE={config.LEVERAGE}x)")

    if config.FORCE_HEDGE:
        orders.set_dual_side_position(True)
    runtime.IS_HEDGE = orders.get_dual_side_position()
    print("Hedge mode?:", runtime.IS_HEDGE)

    sync.sync_state_with_exchange()
    monitor.monitor_loop()


if __name__ == "__main__":
    run()
