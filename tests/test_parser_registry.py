from gui.services.parser_registry import ParserRegistry


def test_register_and_run_all_success():
    r = ParserRegistry()

    def p1(x):
        return x + 1

    def p2(x):
        return x * 2

    r.register("inc", p1)
    r.register("dbl", p2)
    out = r.run_all(3)
    assert out["inc"]["success"] is True
    assert out["inc"]["result"] == 4
    assert out["dbl"]["result"] == 6


def test_run_all_isolates_exceptions():
    r = ParserRegistry()

    def ok(x):
        return x

    def bad(x):
        raise RuntimeError("boom")

    r.register("ok", ok)
    r.register("bad", bad)
    out = r.run_all(1)
    assert out["ok"]["success"] is True
    assert out["bad"]["success"] is False
    assert "boom" in out["bad"]["exception"]
