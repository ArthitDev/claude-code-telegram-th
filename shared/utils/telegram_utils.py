"""
Telegram utility functions for safe API interactions.

Provides helper functions to handle common Telegram API edge cases
like callback query timeouts and rate limiting.
"""

import logging
from typing import Optional

from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)


async def safe_callback_answer(
    callback: CallbackQuery,
    text: Optional[str] = None,
    show_alert: Optional[bool] = None,
    cache_time: Optional[int] = None,
) -> bool:
    """
    Safely answer a callback query, ignoring timeout errors.

    Telegram requires callback queries to be answered within ~10 seconds.
    If the bot takes longer (e.g., slow operations), the query expires
    and raises "query is too old and response timeout expired" error.

    This function catches that error and returns False instead of crashing.

    Args:
        callback: The CallbackQuery to answer
        text: Optional text to show to the user
        show_alert: If True, show as alert popup instead of toast
        cache_time: Cache time in seconds

    Returns:
        True if answer succeeded, False if query expired or other error
    """
    try:
        await callback.answer(
            text=text,
            show_alert=show_alert,
            cache_time=cache_time,
        )
        return True
    except TelegramBadRequest as e:
        error_msg = str(e).lower()
        if any(phrase in error_msg for phrase in [
            "query is too old",
            "timeout expired",
            "query id is invalid",
        ]):
            logger.debug(
                f"Callback query expired for user {callback.from_user.id}, "
                f"ignoring (this is normal if operation took >10s)"
            )
            return False
        # Re-raise other TelegramBadRequest errors
        raise
    except Exception as e:
        logger.warning(f"Unexpected error answering callback: {e}")
        return False


async def safe_callback_edit_text(
    callback: CallbackQuery,
    text: str,
    **kwargs
) -> bool:
    """
    Safely edit message text from a callback, handling common errors.

    Handles:
    - Message not modified (content is the same)
    - Message to edit not found
    - Query timeout (indirectly, since edit usually follows answer)

    Args:
        callback: The CallbackQuery
        text: New text content
        **kwargs: Additional arguments for edit_text

    Returns:
        True if edit succeeded, False otherwise
    """
    try:
        await callback.message.edit_text(text, **kwargs)
        return True
    except TelegramBadRequest as e:
        error_msg = str(e).lower()
        if "message is not modified" in error_msg:
            # Not an error, just no change needed
            return True
        if "message to edit not found" in error_msg:
            logger.debug(f"Message to edit not found for user {callback.from_user.id}")
            return False
        if any(phrase in error_msg for phrase in [
            "query is too old",
            "timeout expired",
        ]):
            logger.debug(f"Callback expired for user {callback.from_user.id}")
            return False
        raise
    except Exception as e:
        logger.warning(f"Error editing message: {e}")
        return False
