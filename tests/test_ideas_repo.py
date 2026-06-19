from db.repos import config_repo, ideas_repo


def test_create_idea_defaults_to_first_status(fake_db):
    idea = ideas_repo.create_idea(title="A cool video", notes="raw text")
    status = config_repo.get_default_status()
    assert idea["status_id"] == status["id"]


def test_set_status_moves_pipeline(fake_db):
    idea = ideas_repo.create_idea(title="Bump me")
    updated = ideas_repo.set_status(idea["id"], "Developing")
    developing = config_repo.get_status_by_name("Developing")
    assert updated["status_id"] == developing["id"]


def test_set_status_unknown_returns_none(fake_db):
    idea = ideas_repo.create_idea(title="x")
    assert ideas_repo.set_status(idea["id"], "Nonexistent") is None


def test_actionable_ideas_only_early_pipeline(fake_db):
    ideas_repo.create_idea(title="early")  # default 'Idea'
    late = ideas_repo.create_idea(title="late")
    ideas_repo.set_status(late["id"], "Published")

    titles = [i["title"] for i in ideas_repo.actionable_ideas()]
    assert "early" in titles
    assert "late" not in titles


def test_find_by_title_fuzzy_fallback(fake_db):
    ideas_repo.create_idea(title="Post-rotation price dip breakdown")
    hit = ideas_repo.find_by_title("price dip")
    assert hit is not None
    assert "price dip" in hit["title"].lower()
