from gui.services.health_metrics_service import HealthMetricsService


def test_fps_calculation_and_window():
    times = [0.0]

    def fake_time():
        return times[0]

    svc = HealthMetricsService(frame_window_seconds=2.0, time_func=fake_time)
    # simulate 5 frames 0.4s apart -> total span 1.6s -> fps = 5 / 1.6 = 3.125
    for i in range(5):
        times[0] = i * 0.4
        svc.frame_tick()
    sample = svc.sample()
    assert sample.fps == round(5 / 1.6, 2)
    # Advance time past window so old frames drop
    times[0] = 5.0
    svc.frame_tick()
    sample2 = svc.sample()
    assert sample2.fps == 0.0  # only one frame in window


def test_db_qps():
    times = [0.0]

    def fake_time():
        return times[0]

    counter = {"n": 0}

    def provider():
        return counter["n"]

    svc = HealthMetricsService(time_func=fake_time)
    svc.register_db_counter(provider)
    # simulate queries
    times[0] = 0.0
    svc.sample()  # baseline
    counter["n"] = 20
    times[0] = 2.0
    s2 = svc.sample()
    # 20 queries over 2s => 10 qps
    assert s2.db_qps == 10.0


def test_memory_fields_present():
    svc = HealthMetricsService()
    sample = svc.sample()
    assert sample.mem_current_kb >= 0
    assert sample.mem_peak_kb >= sample.mem_current_kb
