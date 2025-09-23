from gui.design.elevation import ElevationRole, ELEVATION_ROLE_LEVEL


def test_elevation_alignment_doc_presence():
    import os

    path = os.path.join("docs", "elevation_alignment_report.md")
    assert os.path.exists(path), "Elevation alignment report missing"
    content = open(path, "r", encoding="utf-8").read()
    # Ensure every role enum name appears
    for role in ElevationRole:
        assert role.name in content or role.value in content, f"Role {role} not documented"
    # Ensure numeric levels are referenced
    for lvl in set(ELEVATION_ROLE_LEVEL.values()):
        assert f" {lvl} " in content or f"| {lvl} |" in content or f" {lvl}\n" in content
