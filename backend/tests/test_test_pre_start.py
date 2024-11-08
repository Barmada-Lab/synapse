from unittest.mock import MagicMock, patch

from tests.tests_pre_start import init


def test_init_successful_connection() -> None:
    engine_mock = MagicMock()
    session_mock = MagicMock()

    with (
        patch("tests.tests_pre_start.Session.__enter__", return_value=session_mock),
        patch("tests.tests_pre_start.select") as select_mock,
    ):
        try:
            init(engine_mock)
            connection_successful = True
        except Exception:
            connection_successful = False

        assert (
            connection_successful
        ), "The database connection should be successful and not raise an exception."

        session_mock.exec.assert_called_once_with(select_mock(1))
