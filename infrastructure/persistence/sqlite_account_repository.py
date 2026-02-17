"""
SQLite Account Repository

Persists user account settings for auth mode switching.
"""

import aiosqlite
import json
import logging
from datetime import datetime
from typing import Optional

from shared.config.settings import settings

logger = logging.getLogger(__name__)


class SQLiteAccountRepository:
    """SQLite implementation for AccountSettings persistence"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.database.url.replace("sqlite:///", "")

    async def initialize(self):
        """Initialize the account_settings table"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS account_settings (
                    user_id INTEGER PRIMARY KEY,
                    auth_mode TEXT NOT NULL DEFAULT 'zai_api',
                    model TEXT,
                    proxy_url TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            await db.commit()

            # Add model column if it doesn't exist (migration)
            try:
                await db.execute("ALTER TABLE account_settings ADD COLUMN model TEXT")
                await db.commit()
                logger.info("Added model column to account_settings table")
            except Exception:
                # Column already exists, that's fine
                pass

            # Add local_model_config column if it doesn't exist (migration for local models)
            try:
                await db.execute("ALTER TABLE account_settings ADD COLUMN local_model_config TEXT")
                await db.commit()
                logger.info("Added local_model_config column to account_settings table")
            except Exception:
                # Column already exists, that's fine
                pass

            # Add yolo_mode column if it doesn't exist (migration)
            try:
                await db.execute("ALTER TABLE account_settings ADD COLUMN yolo_mode INTEGER DEFAULT 0")
                await db.commit()
                logger.info("Added yolo_mode column to account_settings table")
            except Exception:
                # Column already exists, that's fine
                pass

            # Add zai_api_key column if it doesn't exist (migration for user-provided z.ai API keys)
            try:
                await db.execute("ALTER TABLE account_settings ADD COLUMN zai_api_key TEXT")
                await db.commit()
                logger.info("Added zai_api_key column to account_settings table")
            except Exception:
                # Column already exists, that's fine
                pass

            # Add language column if it doesn't exist (migration for i18n)
            try:
                await db.execute("ALTER TABLE account_settings ADD COLUMN language TEXT DEFAULT 'ru'")
                await db.commit()
                logger.info("Added language column to account_settings table")
            except Exception:
                # Column already exists, that's fine
                pass

            # Add kimi_config column if it doesn't exist (migration for Moonshot Kimi)
            try:
                await db.execute("ALTER TABLE account_settings ADD COLUMN kimi_config TEXT")
                await db.commit()
                logger.info("Added kimi_config column to account_settings table")
            except Exception:
                # Column already exists, that's fine
                pass

            # Add zai_config column if it doesn't exist (migration for z.ai full config)
            try:
                await db.execute("ALTER TABLE account_settings ADD COLUMN zai_config TEXT")
                await db.commit()
                logger.info("Added zai_config column to account_settings table")
            except Exception:
                # Column already exists, that's fine
                pass

            # Migration: Change default auth_mode from zai_api to moonshot_kimi
            try:
                result = await db.execute(
                    "UPDATE account_settings SET auth_mode = 'moonshot_kimi' WHERE auth_mode = 'zai_api'"
                )
                await db.commit()
                if result.rowcount > 0:
                    logger.info(f"Migrated {result.rowcount} users from zai_api to moonshot_kimi")
            except Exception as e:
                logger.warning(f"Migration warning: {e}")

            # Add os_type column if it doesn't exist (migration for OS selection)
            try:
                await db.execute("ALTER TABLE account_settings ADD COLUMN os_type TEXT DEFAULT 'auto'")
                await db.commit()
                logger.info("Added os_type column to account_settings table")
            except Exception:
                # Column already exists, that's fine
                pass

            # Add custom_working_dir column if it doesn't exist
            try:
                await db.execute("ALTER TABLE account_settings ADD COLUMN custom_working_dir TEXT")
                await db.commit()
                logger.info("Added custom_working_dir column to account_settings table")
            except Exception:
                # Column already exists, that's fine
                pass

            logger.info("Account settings table initialized")

    async def find_by_user_id(self, user_id: int) -> Optional["AccountSettings"]:
        """Find account settings by user ID"""
        from application.services.account_service import AccountSettings, AuthMode

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM account_settings WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_settings(row)
        return None

    async def save(self, settings: "AccountSettings") -> None:
        """Save account settings"""
        # Serialize local_model_config to JSON
        local_config_json = None
        if settings.local_model_config:
            local_config_json = json.dumps(settings.local_model_config.to_dict())

        # Serialize kimi_config to JSON
        kimi_config_json = None
        if settings.kimi_config:
            kimi_config_json = json.dumps(settings.kimi_config.to_dict())

        # Serialize zai_config to JSON
        zai_config_json = None
        if settings.zai_config:
            zai_config_json = json.dumps(settings.zai_config.to_dict())

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO account_settings
                (user_id, auth_mode, model, proxy_url, local_model_config, yolo_mode, zai_api_key, language, zai_config, kimi_config, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                settings.user_id,
                settings.auth_mode.value,
                settings.model,
                settings.proxy_url,
                local_config_json,
                1 if getattr(settings, 'yolo_mode', False) else 0,
                getattr(settings, 'zai_api_key', None),
                getattr(settings, 'language', 'ru'),
                zai_config_json,
                kimi_config_json,
                settings.created_at.isoformat() if settings.created_at else None,
                settings.updated_at.isoformat() if settings.updated_at else None,
            ))
            await db.commit()

    async def set_yolo_mode(self, user_id: int, enabled: bool) -> None:
        """Set yolo mode for user (quick update without full save)"""
        async with aiosqlite.connect(self.db_path) as db:
            # First ensure row exists
            await db.execute("""
                INSERT OR IGNORE INTO account_settings (user_id, auth_mode, yolo_mode, created_at)
                VALUES (?, 'zai_api', ?, ?)
            """, (user_id, 1 if enabled else 0, datetime.utcnow().isoformat()))

            # Then update
            await db.execute(
                "UPDATE account_settings SET yolo_mode = ?, updated_at = ? WHERE user_id = ?",
                (1 if enabled else 0, datetime.utcnow().isoformat(), user_id)
            )
            await db.commit()

    async def get_yolo_mode(self, user_id: int) -> bool:
        """Get yolo mode for user"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT yolo_mode FROM account_settings WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return bool(row[0])
        return False

    async def set_language(self, user_id: int, language: str) -> None:
        """Set language preference for user"""
        async with aiosqlite.connect(self.db_path) as db:
            # First ensure row exists
            await db.execute("""
                INSERT OR IGNORE INTO account_settings (user_id, auth_mode, language, created_at)
                VALUES (?, 'zai_api', ?, ?)
            """, (user_id, language, datetime.utcnow().isoformat()))

            # Then update
            await db.execute(
                "UPDATE account_settings SET language = ?, updated_at = ? WHERE user_id = ?",
                (language, datetime.utcnow().isoformat(), user_id)
            )
            await db.commit()

    async def get_language(self, user_id: int) -> Optional[str]:
        """Get language preference for user"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT language FROM account_settings WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    return row[0]
        return None

    async def delete(self, user_id: int) -> None:
        """Delete account settings for user"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM account_settings WHERE user_id = ?",
                (user_id,)
            )
            await db.commit()

    def _row_to_settings(self, row) -> "AccountSettings":
        """Convert database row to AccountSettings"""
        from application.services.account_service import AccountSettings, AuthMode, LocalModelConfig, KimiConfig, ZaiConfig

        # Deserialize local_model_config from JSON
        local_model_config = None
        if "local_model_config" in row.keys() and row["local_model_config"]:
            try:
                local_model_config = LocalModelConfig.from_dict(
                    json.loads(row["local_model_config"])
                )
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                logger.warning(f"Failed to deserialize local_model_config: {e}")

        # Get yolo_mode (may not exist in old rows)
        yolo_mode = False
        if "yolo_mode" in row.keys() and row["yolo_mode"]:
            yolo_mode = bool(row["yolo_mode"])

        # Get zai_api_key (may not exist in old rows)
        zai_api_key = None
        if "zai_api_key" in row.keys() and row["zai_api_key"]:
            zai_api_key = row["zai_api_key"]

        # Get language (may not exist in old rows)
        language = "ru"  # Default to Russian
        if "language" in row.keys() and row["language"]:
            language = row["language"]

        # Deserialize zai_config from JSON
        zai_config = None
        if "zai_config" in row.keys() and row["zai_config"]:
            try:
                zai_config = ZaiConfig.from_dict(
                    json.loads(row["zai_config"])
                )
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                logger.warning(f"Failed to deserialize zai_config: {e}")

        # Deserialize kimi_config from JSON
        kimi_config = None
        if "kimi_config" in row.keys() and row["kimi_config"]:
            try:
                kimi_config = KimiConfig.from_dict(
                    json.loads(row["kimi_config"])
                )
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                logger.warning(f"Failed to deserialize kimi_config: {e}")

        return AccountSettings(
            user_id=row["user_id"],
            auth_mode=AuthMode(row["auth_mode"]),
            model=row["model"] if "model" in row.keys() else None,  # May be None for existing records
            proxy_url=row["proxy_url"],
            local_model_config=local_model_config,
            yolo_mode=yolo_mode,
            zai_api_key=zai_api_key,
            zai_config=zai_config,
            kimi_config=kimi_config,
            language=language,
            created_at=(
                datetime.fromisoformat(row["created_at"])
                if row["created_at"] else None
            ),
            updated_at=(
                datetime.fromisoformat(row["updated_at"])
                if row["updated_at"] else None
            ),
        )
