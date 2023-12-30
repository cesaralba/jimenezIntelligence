import logging

DEFULTLEVEL = logging.WARNING
DEFAULTLOGFORMAT = ('%(asctime)s [%(process)d:%(threadName)10s@%(name)s %(levelname)s %(relativeCreated)14dms]: %('
                    'message)s')


def prepareLogger(logger: logging.Logger, level=DEFULTLEVEL, logformat=DEFAULTLOGFORMAT, handler=None):
    logger.setLevel(level)
    formatter = logging.Formatter(logformat)
    ch = handler or logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
