from db.repos import deadtime_repo


def test_list_open_filters_by_window(fake_db):
    deadtime_repo.add_task("short", duration_est_min=10)
    deadtime_repo.add_task("long", duration_est_min=60)
    deadtime_repo.add_task("no estimate")  # None duration -> always fits

    fits = [t["content"] for t in deadtime_repo.list_open(max_minutes=15)]
    assert "short" in fits
    assert "no estimate" in fits
    assert "long" not in fits


def test_list_open_orders_by_priority_desc(fake_db):
    deadtime_repo.add_task("low", priority=1)
    deadtime_repo.add_task("high", priority=9)
    deadtime_repo.add_task("mid", priority=5)

    order = [t["content"] for t in deadtime_repo.list_open()]
    assert order == ["high", "mid", "low"]


def test_complete_task_marks_done_and_drops_from_open(fake_db):
    t = deadtime_repo.add_task("do it")
    deadtime_repo.complete_task(t["id"])
    assert deadtime_repo.list_open() == []
