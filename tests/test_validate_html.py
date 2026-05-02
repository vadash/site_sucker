"""Tests for HTML validation functionality."""

import pytest

from site_sucker.validate_html import print_validation_results, validate_html_files


def test_validate_html_valid_page(tmp_path: Path):
    """Test validation of a structurally complete HTML file."""
    html_file = tmp_path / "test.html"
    html_content = '''<!DOCTYPE html>
<html>
<head>
    <title>Test</title>
</head>
<body>
    <h1>Content</h1>
    <p>This is a test page with substantial content.</p>
</body>
</html>'''
    html_file.write_text(html_content)

    results = validate_html_files(tmp_path)

    assert results["all_valid"]
    assert len(results["missing_head"]) == 0
    assert len(results["missing_body"]) == 0
    assert len(results["empty_body"]) == 0


def test_validate_html_missing_head(tmp_path: Path):
    """Test detection of missing head element."""
    html_file = tmp_path / "test.html"
    html_content = '''<!DOCTYPE html>
<html>
<body>
    <h1>Content</h1>
</body>
</html>'''
    html_file.write_text(html_content)

    results = validate_html_files(tmp_path)

    assert not results["all_valid"]
    assert "test.html" in results["missing_head"]


def test_validate_html_missing_body(tmp_path: Path):
    """Test detection of missing body element."""
    html_file = tmp_path / "test.html"
    html_content = '''<!DOCTYPE html>
<html>
<head>
    <title>Test</title>
</head>
    <h1>Content</h1>
</html>'''
    html_file.write_text(html_content)

    results = validate_html_files(tmp_path)

    assert not results["all_valid"]
    assert "test.html" in results["missing_body"]


def test_validate_html_empty_body(tmp_path: Path):
    """Test detection of empty body content."""
    html_file = tmp_path / "test.html"
    html_content = '''<!DOCTYPE html>
<html>
<head>
    <title>Test</title>
</head>
<body>
    <script>console.log("test");</script>
</body>
</html>'''
    html_file.write_text(html_content)

    results = validate_html_files(tmp_path)

    assert not results["all_valid"]
    assert "test.html" in results["empty_body"]


def test_validate_html_body_with_only_whitespace(tmp_path: Path):
    """Test detection of body with only whitespace content."""
    html_file = tmp_path / "test.html"
    html_content = '''<!DOCTYPE html>
<html>
<head>
    <title>Test</title>
</head>
<body>
    \n\t
</body>
</html>'''
    html_file.write_text(html_content)

    results = validate_html_files(tmp_path)

    assert not results["all_valid"]
    assert "test.html" in results["empty_body"]


def test_validate_html_multiple_issues(tmp_path: Path):
    """Test detection of multiple issues in one file."""
    html_file = tmp_path / "test.html"
    html_content = '''<!DOCTYPE html>
<html>
<body>
    <script>console.log("test");</script>
</body>
</html>'''
    html_file.write_text(html_content)

    results = validate_html_files(tmp_path)

    assert not results["all_valid"]
    assert "test.html" in results["missing_head"]
    # Has body tag
    assert "test.html" not in results["missing_body"]
    assert "test.html" in results["empty_body"]


def test_validate_html_multiple_files(tmp_path: Path):
    """Test validation across multiple HTML files."""
    # Valid file
    (tmp_path / "valid.html").write_text('''<!DOCTYPE html>
<html>
<head><title>Valid</title></head>
<body><h1>Substantial content here</h1></body>
</html>''')

    # Invalid file - missing head
    (tmp_path / "invalid.html").write_text('''<!DOCTYPE html>
<html>
<body><h1>Content</h1>
</html>''')

    # Empty body file
    (tmp_path / "empty.html").write_text('''<!DOCTYPE html>
<html>
<head><title>Empty</title></head>
<body>
</body>
</html>''')

    results = validate_html_files(tmp_path)

    assert not results["all_valid"]
    assert len(results["missing_head"]) == 1
    assert "invalid.html" in results["missing_head"]
    assert len(results["empty_body"]) == 1
    assert "empty.html" in results["empty_body"]


def test_validate_html_case_insensitive(tmp_path: Path):
    """Test that HTML tag detection is case-insensitive."""
    html_file = tmp_path / "test.html"
    html_content = '''<!DOCTYPE html>
<HTML>
<HEAD>
    <title>Test</title>
</HEAD>
<BODY>
    <h1>Welcome to the Test Page</h1>
    <p>This page has enough content to pass validation.</p>
</BODY>
</HTML>'''
    html_file.write_text(html_content)

    results = validate_html_files(tmp_path)

    assert results["all_valid"]


def test_validate_html_body_with_scripts_and_styles(tmp_path: Path):
    """Test that body content detection ignores scripts and styles."""
    html_file = tmp_path / "test.html"
    html_content = '''<!DOCTYPE html>
<html>
<head>
    <title>Test</title>
</head>
<body>
    <script>
        var x = "some long script content here";
    </script>
    <style>
        .class { color: red; }
    </style>
    <!-- This is a comment -->
</body>
</html>'''
    html_file.write_text(html_content)

    results = validate_html_files(tmp_path)

    assert not results["all_valid"]
    assert "test.html" in results["empty_body"]


def test_validate_html_minimal_valid_content(tmp_path: Path):
    """Test that minimal but meaningful content passes validation."""
    html_file = tmp_path / "test.html"
    html_content = '''<!DOCTYPE html>
<html>
<head>
    <title>Test</title>
</head>
<body>
    <h1>Hi</h1>
</body>
</html>'''
    html_file.write_text(html_content)

    results = validate_html_files(tmp_path)

    # "Hi" is less than 20 chars, so it should fail
    assert not results["all_valid"]
    assert "test.html" in results["empty_body"]


def test_validate_html_substantial_content(tmp_path: Path):
    """Test that substantial content passes validation."""
    html_file = tmp_path / "test.html"
    html_content = '''<!DOCTYPE html>
<html>
<head>
    <title>Test</title>
</head>
<body>
    <h1>Welcome to the Test Page</h1>
    <p>This page has enough content to be considered valid.</p>
</body>
</html>'''
    html_file.write_text(html_content)

    results = validate_html_files(tmp_path)

    assert results["all_valid"]


def test_print_validation_results_valid(capsys: pytest.CaptureFixture[str]):
    """Test print output for valid results."""
    results = {
        "missing_head": [],
        "missing_body": [],
        "empty_body": [],
        "all_valid": True,
    }

    print_validation_results(results)

    captured = capsys.readouterr()
    assert "✓ HTML validation passed" in captured.out
    assert "⚠" not in captured.out


def test_print_validation_results_invalid(capsys: pytest.CaptureFixture[str], tmp_path: Path):
    """Test print output for invalid results."""
    # Create files to report
    (tmp_path / "broken1.html").write_text('<html><body></body></html>')
    (tmp_path / "broken2.html").write_text('<html><body></body></html>')

    results = {
        "missing_head": ["broken1.html", "broken2.html"],
        "missing_body": [],
        "empty_body": ["broken1.html"],
        "all_valid": False,
    }

    print_validation_results(results)

    captured = capsys.readouterr()
    assert "⚠ HTML validation detected issues" in captured.out
    assert "Missing head element" in captured.out
    assert "Empty body content" in captured.out
    assert "broken1.html" in captured.out
    assert "incomplete download" in captured.out.lower()
