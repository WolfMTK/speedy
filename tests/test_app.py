import logging

from speedy import Speedy


def test_set_debug_updates_logging_level() -> None:
    app = Speedy()

    assert app.logger is not None
    assert app.logger.level == logging.INFO

    app.debug = True
    assert app.logger.level == logging.DEBUG

    app.debug = False
    assert app.logger.level == logging.INFO
