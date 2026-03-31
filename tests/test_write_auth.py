"""!Unit tests for optional write-token enforcement."""

from fastapi import HTTPException

from apps.api import main


def test_require_write_token_allows_when_unset(monkeypatch) -> None:
    """!If WRITE_API_TOKEN is empty, writes remain open."""
    monkeypatch.setattr(main, "WRITE_API_TOKEN", "")
    main._require_write_token(None)
    main._require_write_token("anything")


def test_require_write_token_rejects_bad_token(monkeypatch) -> None:
    """!Configured token should block missing or incorrect values."""
    monkeypatch.setattr(main, "WRITE_API_TOKEN", "secret")
    try:
        main._require_write_token(None)
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("Expected HTTPException for missing token")

    try:
        main._require_write_token("wrong")
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("Expected HTTPException for invalid token")


def test_require_write_token_accepts_matching_token(monkeypatch) -> None:
    """!Configured token should allow matching requests."""
    monkeypatch.setattr(main, "WRITE_API_TOKEN", "secret")
    main._require_write_token("secret")
