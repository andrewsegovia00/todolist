from db.repos import config_repo


def test_get_or_create_tag_is_idempotent(fake_db):
    a = config_repo.get_or_create_tag("foo")
    b = config_repo.get_or_create_tag("FOO")  # case-insensitive match
    assert a["id"] == b["id"]
    assert len(config_repo.list_tags()) == 1


def test_settings_roundtrip_and_checkins_toggle(fake_db):
    assert config_repo.checkins_enabled() is True  # defaults true when unset
    config_repo.set_setting("checkins_enabled", "false")
    assert config_repo.checkins_enabled() is False
    config_repo.set_setting("checkins_enabled", "true")  # upsert, not duplicate
    assert config_repo.checkins_enabled() is True


def test_default_status_is_first_in_pipeline(fake_db):
    assert config_repo.get_default_status()["name"] == "Idea"


def test_archive_bucket_hides_from_active_list(fake_db):
    b = config_repo.add_bucket("The Shop")
    assert any(x["name"] == "The Shop" for x in config_repo.list_buckets())
    config_repo.archive_bucket(b["id"])
    assert all(x["name"] != "The Shop" for x in config_repo.list_buckets())
    assert any(x["name"] == "The Shop" for x in config_repo.list_buckets(active_only=False))
