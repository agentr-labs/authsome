"""Tests for library logging behaviour."""

import io


def test_import_authsome_produces_no_log_output():
    """Importing authsome must not emit any log output — library best practice."""
    from loguru import logger

    sink = io.StringIO()
    sink_id = logger.add(sink, level="DEBUG")
    try:
        import authsome  # noqa: F401

        output = sink.getvalue()
        assert output == "", f"Expected no log output on import, got: {output!r}"
    finally:
        logger.remove(sink_id)


def test_user_can_enable_authsome_logs():
    """Users should be able to opt-in and out of library logs without errors."""
    from loguru import logger

    logger.enable("authsome")
    logger.disable("authsome")  # restore default — must not raise
