from gui.services.division_table_normalizer import DivisionTableNormalizer
from gui.models import DivisionStandingEntry


def make_entry(**kw):
    base = dict(
        position=1,
        team_name="Team",
        matches_played=10,
        wins=6,
        draws=2,
        losses=2,
        goals_for=30,
        goals_against=20,
        points=20,
        recent_form="WWDLW",
    )
    base.update(kw)
    return DivisionStandingEntry(**base)


def test_differential_positive():
    norm = DivisionTableNormalizer()
    rows = norm.normalize([make_entry(goals_for=40, goals_against=20)])
    assert rows[0].differential_text == "+20"


def test_differential_negative():
    norm = DivisionTableNormalizer()
    rows = norm.normalize([make_entry(goals_for=10, goals_against=25)])
    assert rows[0].differential_text == "-15"


def test_differential_zero():
    norm = DivisionTableNormalizer()
    rows = norm.normalize([make_entry(goals_for=10, goals_against=10)])
    assert rows[0].differential_text == "0"


def test_form_trim_uppercase():
    norm = DivisionTableNormalizer(form_window=5)
    rows = norm.normalize([make_entry(recent_form="w w d l w w l")])
    # sanitize -> WWWDLWWL -> last 5 -> LWWL (wait length). Let's compute precisely.
    # Input after upper and removing spaces: WWD LWWL? Actually: "w w d l w w l" -> remove spaces -> WWDLWWL (7 chars)
    # last 5 = DLWWL
    assert rows[0].form == "DLWWL"


def test_form_none():
    norm = DivisionTableNormalizer()
    rows = norm.normalize([make_entry(recent_form=None)])
    assert rows[0].form is None
