from gui.services.html_diff import HtmlDiffService
from gui.views.html_source_view import HtmlSourceView
from gui.services.html_diff import HtmlSource


def test_clean_html_reduces_content(tmp_path, qtbot):  # type: ignore
    svc = HtmlDiffService(str(tmp_path))
    raw = """<html><head><style>.x{color:red}</style><script>var x=1;</script><!--c--></head><body><div> Text  \n More</div></body></html>"""
    cleaned = svc.clean_html(raw)
    # Should remove script/style/comment and collapse whitespace
    assert "script" not in cleaned.lower()
    assert "style" not in cleaned.lower()
    assert "<!--" not in cleaned
    assert "  " not in cleaned


def test_toggle_mode_updates_view(tmp_path, qtbot):  # type: ignore
    svc = HtmlDiffService(str(tmp_path))
    src = HtmlSource(
        label="f.html",
        current_path=tmp_path / "f.html",
        previous_path=None,
        current_text="<html>   <body> X  </body></html>",
        previous_text=None,
    )
    view = HtmlSourceView(svc)
    qtbot.addWidget(view)
    view.set_html_source(src)
    raw_len = len(view.txt_source.toPlainText())
    view.chk_clean.setChecked(True)
    clean_len = len(view.txt_source.toPlainText())
    assert clean_len <= raw_len
