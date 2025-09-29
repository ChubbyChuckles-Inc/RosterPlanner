from gui.ingestion.selector_optimizer import (
    FieldSelectorContext,
    compute_selector_optimizations,
)


def test_compute_selector_optimizations_prefers_shorter_selector():
    html = """
    <html>
      <body>
        <div class="wrapper">
          <table class="stats">
            <tbody>
              <tr>
                <td class="name">Alice</td>
                <td class="score">10</td>
              </tr>
            </tbody>
          </table>
        </div>
      </body>
    </html>
    """
    contexts = [
        FieldSelectorContext(
            field_id="field1",
            field_label="Player",
            resource_label="Roster",
            selector="div.wrapper > table.stats > tbody > tr > td.name",
        )
    ]

    suggestions = compute_selector_optimizations(html, contexts)

    assert suggestions, "Expected a selector optimization suggestion"
    suggestion = suggestions[0]
    assert suggestion.optimized_selector.endswith("td.name")
    assert len(suggestion.optimized_selector) < len(suggestion.original_selector)
    assert suggestion.match_count == 1
    assert suggestion.character_reduction > 0


def test_compute_selector_optimizations_requires_identical_matches():
    html = """
    <html>
      <body>
        <div class="detail">
          <span class="value">A</span>
        </div>
        <div class="other">
          <span class="value">B</span>
        </div>
      </body>
    </html>
    """
    contexts = [
        FieldSelectorContext(
            field_id="field2",
            field_label="ScopedValue",
            resource_label="Details",
            selector="div.detail span.value",
        )
    ]

    suggestions = compute_selector_optimizations(html, contexts)

    assert suggestions == [], "Selector optimization should not relax matches"
