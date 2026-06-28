from bot.cogs.help_cog import build_help_embed


def test_help_embed_covers_all_command_groups():
    embed = build_help_embed()
    field_names = " ".join(f.name for f in embed.fields)
    assert "#ideas" in field_names
    assert "#schedule" in field_names
    assert "#config" in field_names

    body = " ".join(f.value for f in embed.fields)
    for cmd in ["/ideas", "/buckets", "/close", "/dead", "/task", "/done",
                "/dayoff", "/recap", "/bucket", "/project", "/checkins"]:
        assert cmd in body, f"{cmd} missing from /help"


def test_help_explains_checkins_vs_dayoff():
    body = " ".join(f.value for f in build_help_embed().fields).lower()
    assert "excluded from analytics" in body
    assert "globally" in body
