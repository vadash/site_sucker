"""Tests for the unified replacement pipeline."""

import re
from pathlib import Path

from site_sucker.replacement_pipeline import ReplacementStep, run_replacement_pipeline


def test_valid_replacement_applied(tmp_path: Path):
    """Test that a valid replacement is applied and content changes."""
    test_file = tmp_path / "test.html"
    original_content = '''<html>
<head></head>
<body>
    <p>Test content</p>
    <script src="https://example.com/tracking.js"></script>
</body>
</html>'''
    test_file.write_text(original_content)

    steps = [
        ReplacementStep(
            name="Remove tracking script",
            pattern=re.compile(r'<script src="https://example\.com/tracking\.js"></script>'),
            replacement='',
        ),
    ]

    result = run_replacement_pipeline(test_file, steps, None)

    assert result == 1  # One step applied

    updated_content = test_file.read_text()
    assert 'tracking.js' not in updated_content
    assert '<body>' in updated_content
    assert '</body>' in updated_content


def test_destructive_replacement_reverted(tmp_path: Path):
    """Test that a destructive replacement (removing </body>) is reverted."""
    test_file = tmp_path / "test.html"
    original_content = '''<html>
<head></head>
<body>
    <p>Test content</p>
    <script>var x = 1;</script>
</body>
</html>'''
    test_file.write_text(original_content)

    # This pattern directly removes the closing </body> tag
    steps = [
        ReplacementStep(
            name="Remove </body> tag directly",
            pattern=re.compile(r'</body>'),
            replacement='',  # This will break the HTML
        ),
    ]

    result = run_replacement_pipeline(test_file, steps, None)

    assert result == 0  # No steps applied (reverted)

    # Content should be unchanged
    updated_content = test_file.read_text()
    assert updated_content == original_content
    assert '</body>' in updated_content


def test_replacement_with_validation_logging(tmp_path: Path):
    """Test that failed replacements are logged."""
    test_file = tmp_path / "test.html"
    original_content = '''<html>
<head></head>
<body>
    <p>Test</p>
    <script>var x = 1;</script>
</body>
</html>'''
    test_file.write_text(original_content)

    # This pattern will break the HTML structure by removing </body>
    steps = [
        ReplacementStep(
            name="Remove </body> tag",
            pattern=re.compile(r'</body>'),
            replacement='',  # Will break HTML
        ),
    ]

    log_dir = tmp_path / "logs"
    result = run_replacement_pipeline(test_file, steps, log_dir)

    assert result == 0  # No steps applied

    # Check log directory was created
    assert log_dir.exists()
    log_subdirs = [d for d in log_dir.iterdir() if d.is_dir()]
    assert len(log_subdirs) == 1

    failure_dir = log_subdirs[0]
    assert (failure_dir / "test.html").exists()
    assert (failure_dir / "pattern.txt").exists()

    # Check log file contents
    pattern_content = (failure_dir / "pattern.txt").read_text()
    assert "Remove </body> tag" in pattern_content
    assert "HTML validation failed" in pattern_content


def test_css_validation_non_empty(tmp_path: Path):
    """Test that CSS validation checks for non-empty content."""
    test_file = tmp_path / "style.css"
    original_content = "body { color: red; }"
    test_file.write_text(original_content)

    # This replacement would result in empty CSS
    steps = [
        ReplacementStep(
            name="Remove all CSS",
            pattern=re.compile(r'.*'),
            replacement='',
        ),
    ]

    log_dir = tmp_path / "logs"
    result = run_replacement_pipeline(test_file, steps, log_dir)

    assert result == 0  # Should be reverted

    # Content should be unchanged
    assert test_file.read_text() == original_content

    # Check logging
    assert log_dir.exists()
    failure_dir = list(log_dir.iterdir())[0]
    pattern_content = (failure_dir / "pattern.txt").read_text()
    assert "CSS content is empty" in pattern_content


def test_multiple_valid_replacements(tmp_path: Path):
    """Test that multiple valid replacements are all applied."""
    test_file = tmp_path / "test.html"
    original_content = '''<html>
<head>
    <link rel="stylesheet" href="https://cdn.example.com/style.css">
</head>
<body>
    <script src="https://example.com/analytics.js"></script>
    <p>Content</p>
</body>
</html>'''
    test_file.write_text(original_content)

    steps = [
        ReplacementStep(
            name="Remove stylesheet",
            pattern=re.compile(r'<link[^>]*href="https://cdn\.example\.com/[^"]*"[^>]*/?>'),
            replacement='',
        ),
        ReplacementStep(
            name="Remove analytics script",
            pattern=re.compile(r'<script[^>]*src="https://example\.com/analytics\.js"[^>]*></script>'),
            replacement='',
        ),
    ]

    result = run_replacement_pipeline(test_file, steps, None)

    assert result == 2  # Both steps applied

    updated_content = test_file.read_text()
    assert 'stylesheet' not in updated_content
    assert 'analytics.js' not in updated_content
    assert '<body>' in updated_content
    assert '</body>' in updated_content


def test_no_change_no_validation(tmp_path: Path):
    """Test that if no change occurs, validation is not run."""
    test_file = tmp_path / "test.html"
    original_content = '''<html>
<head></head>
<body><p>Test</p></body>
</html>'''
    test_file.write_text(original_content)

    steps = [
        ReplacementStep(
            name="Remove non-existent element",
            pattern=re.compile(r'<div class="missing">'),
            replacement='',
        ),
    ]

    result = run_replacement_pipeline(test_file, steps, None)

    assert result == 0  # No changes

    # File content should be identical (not even rewritten)
    updated_content = test_file.read_text()
    assert updated_content == original_content


def test_callable_replacement(tmp_path: Path):
    """Test that callable replacements work correctly."""
    test_file = tmp_path / "test.html"
    original_content = '''<html>
<head></head>
<body><p>Test</p></body>
</html>'''
    test_file.write_text(original_content)

    def add_meta_tag(content: str) -> str:
        return content.replace('<head>', '<head>\n    <meta name="test" content="value">')

    steps = [
        ReplacementStep(
            name="Add meta tag",
            pattern=add_meta_tag,
        ),
    ]

    result = run_replacement_pipeline(test_file, steps, None)

    assert result == 1

    updated_content = test_file.read_text()
    assert '<meta name="test"' in updated_content
    assert '</head>' in updated_content  # Still valid


def test_css_absolute_path_conversion(tmp_path: Path):
    """Test CSS absolute path conversion (a real-world case)."""
    test_file = tmp_path / "style.css"
    original_content = "body { background: url('/images/bg.png'); }"
    test_file.write_text(original_content)

    # Convert absolute paths to relative
    steps = [
        ReplacementStep(
            name="Convert absolute paths to relative",
            pattern=re.compile(r'url\(\s*(["\']?)/([^"\'\)]*)\1\s*\)'),
            replacement=r'url(\1../\2\1)',
        ),
    ]

    result = run_replacement_pipeline(test_file, steps, None)

    assert result == 1

    updated_content = test_file.read_text()
    assert "url('../images/bg.png')" in updated_content
    assert "url('/images/" not in updated_content


def test_log_counter_padding(tmp_path: Path):
    """Test that log directories use zero-padded counter."""
    test_files = []
    log_dir = tmp_path / "logs"

    content = '''<html>
<head></head>
<body><p>Test content here</p></body>
</html>'''

    # Run multiple replacements that fail on DIFFERENT files
    for i in range(5):
        test_file = tmp_path / f"test{i}.html"
        test_file.write_text(content)
        test_files.append(test_file)

        steps = [
            ReplacementStep(
                name=f"Bad replacement {i}",
                pattern=re.compile(r'</body>'),
                replacement='',  # Breaks HTML
            ),
        ]

        run_replacement_pipeline(test_file, steps, log_dir)

    # Check we have 5 log directories with proper padding
    log_subdirs = sorted([d for d in log_dir.iterdir() if d.is_dir()], key=lambda x: x.name)
    assert len(log_subdirs) == 5

    # Check naming: 00001, 00002, ..., 00005
    assert log_subdirs[0].name == "00001"
    assert log_subdirs[4].name == "00005"


def test_regex_with_flags(tmp_path: Path):
    """Test that regex flags are properly handled."""
    test_file = tmp_path / "test.html"
    original_content = '''<html>
<head></head>
<body>
    <p>Some content</p>
    <SCRIPT src="https://example.com/script.js"></SCRIPT>
</body>
</html>'''
    test_file.write_text(original_content)

    steps = [
        ReplacementStep(
            name="Remove script (case insensitive)",
            pattern=re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
            replacement='',
        ),
    ]

    log_dir = tmp_path / "logs"
    result = run_replacement_pipeline(test_file, steps, log_dir)

    # This should work because </body> is still present
    # The pattern removes only the script tag, not the body
    assert result == 1

    updated_content = test_file.read_text()
    assert 'SCRIPT' not in updated_content.upper()
    assert '</body>' in updated_content


def test_preserve_newline_style(tmp_path: Path):
    """Test that file is written with proper newline handling."""
    test_file = tmp_path / "test.html"
    original_content = "<html>\n<head></head>\n<body><p>Test content here</p> <p>More content</p></body>\n</html>"
    test_file.write_text(original_content)

    steps = [
        ReplacementStep(
            name="Remove first paragraph",
            pattern=re.compile(r'<p>Test content here</p>'),
            replacement='',
        ),
    ]

    run_replacement_pipeline(test_file, steps, None)

    updated_content = test_file.read_text()
    assert '<p>More content</p>' in updated_content
    assert 'Test content here' not in updated_content
    # Should preserve structure
    assert '<html>' in updated_content
    assert '</html>' in updated_content
