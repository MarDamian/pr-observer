from pathlib import Path

from pr_observer.diff import parse_diff, render_file

SAMPLE = (Path(__file__).parent / "fixtures" / "sample.diff").read_text()


def by_path():
    return {f.path: f for f in parse_diff(SAMPLE)}


def test_parses_every_file():
    assert list(by_path()) == [
        "app/cart.py",
        "pnpm-lock.yaml",
        "app/old.py",
        "logo.png",
        "docs/guide.md",
    ]


def test_new_side_line_numbers():
    cart = by_path()["app/cart.py"]
    assert len(cart.hunks) == 2
    added = {ln.new_no: ln.text for h in cart.hunks for ln in h.lines if ln.kind == "+"}
    assert added == {
        13: "    -- not a header, just odd content",
        14: "    average = subtotal / len(items)",
        15: "    return subtotal, average",
        44: "    cart.save()",
    }
    assert cart.commentable_lines == set(range(10, 18)) | set(range(42, 46))


def test_removed_line_that_looks_like_a_header_stays_in_the_hunk():
    diff = (
        "--- a/q.sql\n+++ b/q.sql\n@@ -1,2 +1,2 @@\n--- old comment\n+-- new comment\n select 1;\n"
    )
    (f,) = parse_diff(diff)
    assert f.path == "q.sql"
    assert [(ln.kind, ln.text) for ln in f.hunks[0].lines] == [
        ("-", "-- old comment"),
        ("+", "-- new comment"),
        (" ", "select 1;"),
    ]


def test_skip_reasons():
    reasons = {path: f.skip_reason for path, f in by_path().items()}
    assert reasons == {
        "app/cart.py": None,
        "pnpm-lock.yaml": "generated or vendored",
        "app/old.py": "deleted",
        "logo.png": "binary",
        "docs/guide.md": "no content changes",
    }


def test_vendored_directories_are_skipped_at_any_depth():
    diff = (
        "diff --git a/web/node_modules/x/i.js b/web/node_modules/x/i.js\n"
        "--- a/web/node_modules/x/i.js\n+++ b/web/node_modules/x/i.js\n@@ -1 +1 @@\n-a\n+b\n"
    )
    assert parse_diff(diff)[0].skip_reason == "generated or vendored"


def test_render_shows_line_numbers_only_on_the_new_side():
    text = render_file(by_path()["app/cart.py"])
    assert text.startswith("### app/cart.py\n@@ -10,6 +10,8 @@")
    assert "+   14 |     average = subtotal / len(items)" in text
    assert "-      |     return subtotal" in text
    assert "    10 |     subtotal = 0" in text
