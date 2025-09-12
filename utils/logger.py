import logging

def get_logger(name="ghost"):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))
        logger.addHandler(handler)
    return logger

def pause_for_debug():
    input("⏸ Pause debug — appuie sur Entrée pour continuer...")