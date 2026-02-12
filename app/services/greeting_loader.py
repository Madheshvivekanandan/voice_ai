import logging
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
GREETING_FILE: Path = BASE_DIR / "app" / "data" / "greeting.txt"


class GreetingNotFoundError(FileNotFoundError):
    """Raised when the greeting file does not exist."""


def get_greeting(filepath: Path = GREETING_FILE) -> str:
    if not filepath.exists():
        logger.error("Greeting file not found: %s", filepath)
        raise GreetingNotFoundError(f"Greeting file not found: {filepath}")

    text = filepath.read_text(encoding="utf-8").strip()

    if not text:
        logger.error("Greeting file is empty: %s", filepath)
        raise ValueError(f"Greeting file is empty: {filepath}")

    logger.info("Greeting loaded successfully from %s", filepath)
    return text


async def get_greeting_from_api() -> str:
    raise NotImplementedError("API-based greeting provider is not yet implemented")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    try:
        greeting = get_greeting()
        print(f"Greeting: {greeting}")
    except (GreetingNotFoundError, ValueError) as e:
        print(f"Error: {e}")
