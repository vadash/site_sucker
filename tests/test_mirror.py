"""Tests for mirror module."""

from pathlib import Path

import pytest

from site_sucker import mirror


def test_pass2_includes_nc_flag(sample_settings: dict, tmp_path: Path):
    """Test that Pass 2 (media download) includes -nc flag for resume support."""
    # We can't easily test the full invoke_site_mirror without mocking subprocess,
    # but we can verify that the pass2_args include -nc by checking the mirror.py code
    # This is more of an integration test to ensure -nc is present in Pass 2

    # Read the mirror.py source to verify -nc is in pass2_args
    mirror_path = Path(__file__).parent.parent / "src" / "site_sucker" / "mirror.py"
    mirror_source = mirror_path.read_text(encoding="utf-8")

    # Verify -nc is present in pass2_args section
    assert '"-nc"' in mirror_source or "'-nc'" in mirror_source

    # Verify it's in the pass2_args block (after "pass2_args")
    pass2_section = mirror_source.split("pass2_args")[1].split(")")[0]
    assert '"-nc"' in pass2_section or "'-nc'" in pass2_section
