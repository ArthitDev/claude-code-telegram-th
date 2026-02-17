"""
Docker Callback Handlers

Handles all Docker-related callbacks: list, start, stop, restart, logs, info, rm.
"""

import logging
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from presentation.handlers.callbacks.base import BaseCallbackHandler
from shared.constants import DOCKER_LOGS_PAGE_SIZE, DOCKER_LOGS_MAX_LINES, TEXT_TRUNCATE_LIMIT

logger = logging.getLogger(__name__)


class DockerCallbackHandler(BaseCallbackHandler):
    """Handles Docker container management callbacks."""

    async def handle_metrics_refresh(self, callback: CallbackQuery) -> None:
        """Handle metrics refresh callback"""
        try:
            info = await self.bot_service.get_system_info()
            metrics = info["metrics"]

            text = (
                f"📊 <b>Метрики системы</b>\n\n"
                f"💻 <b>CPU:</b> {metrics['cpu_percent']:.1f}%\n"
                f"🧠 <b>Память:</b> {metrics['memory_percent']:.1f}% "
                f"({metrics['memory_used_gb']}GB / {metrics['memory_total_gb']}GB)\n"
                f"💾 <b>Диск:</b> {metrics['disk_percent']:.1f}% "
                f"({metrics['disk_used_gb']}GB / {metrics['disk_total_gb']}GB)\n"
            )

            if metrics.get('load_average', [0])[0] > 0:
                text += f"📈 <b>Нагрузка:</b> {metrics['load_average'][0]:.2f}\n"

            if info.get("alerts"):
                text += "\n⚠️ <b>Предупреждения:</b>\n"
                text += "\n".join(info["alerts"])

            await callback.message.edit_text(text, parse_mode="HTML")

        except Exception as e:
            logger.error(f"Error refreshing metrics: {e}")
            await safe_callback_answer(callback, f"❌ Ошибка: {e}")

        await safe_callback_answer(callback)

    async def handle_docker_list(self, callback: CallbackQuery) -> None:
        """Handle docker list callback"""
        try:
            from infrastructure.monitoring.system_monitor import SystemMonitor
            from presentation.keyboards.keyboards import Keyboards

            monitor = SystemMonitor()
            containers = await monitor.get_docker_containers()

            if not containers:
                text = "🐳 Контейнеры не найдены"
                await callback.message.edit_text(text, parse_mode=None)
            else:
                lines = ["🐳 <b>Docker контейнеры:</b>\n"]
                for c in containers:
                    status_emoji = "🟢" if c["status"] == "running" else "🔴"
                    lines.append(f"\n{status_emoji} <b>{c['name']}</b>")
                    lines.append(f"   Статус: {c['status']}")
                    lines.append(f"   Образ: <code>{c['image'][:30]}</code>")

                text = "\n".join(lines)
                await callback.message.edit_text(
                    text,
                    parse_mode="HTML",
                    reply_markup=Keyboards.docker_list(containers, show_back=True, back_to="menu:system")
                )

        except Exception as e:
            logger.error(f"Error listing containers: {e}")
            await safe_callback_answer(callback, f"❌ Ошибка: {e}")

        await safe_callback_answer(callback)

    async def _docker_action(
        self,
        callback: CallbackQuery,
        action: str,
        action_method: str
    ) -> None:
        """
        Generic docker action handler.

        Reduces duplication between stop/start/restart/rm handlers.
        """
        container_id = callback.data.split(":")[-1]
        try:
            from infrastructure.monitoring.system_monitor import create_system_monitor
            monitor = create_system_monitor()

            method = getattr(monitor, action_method)
            if action_method == "docker_remove":
                success, message = await method(container_id, force=True)
            else:
                success, message = await method(container_id)

            if success:
                await safe_callback_answer(callback, f"✅ {message}")
                await self.handle_docker_list(callback)
            else:
                await safe_callback_answer(callback, f"❌ {message}")

        except Exception as e:
            logger.error(f"Error {action} container: {e}")
            await safe_callback_answer(callback, f"❌ Ошибка: {e}")

    async def handle_docker_stop(self, callback: CallbackQuery) -> None:
        """Handle docker stop container"""
        await self._docker_action(callback, "stopping", "docker_stop")

    async def handle_docker_start(self, callback: CallbackQuery) -> None:
        """Handle docker start container"""
        await self._docker_action(callback, "starting", "docker_start")

    async def handle_docker_restart(self, callback: CallbackQuery) -> None:
        """Handle docker restart container"""
        await self._docker_action(callback, "restarting", "docker_restart")

    async def handle_docker_rm(self, callback: CallbackQuery) -> None:
        """Handle docker remove container"""
        await self._docker_action(callback, "removing", "docker_remove")

    async def handle_docker_logs(self, callback: CallbackQuery) -> None:
        """Handle docker logs with pagination"""
        # Parse callback: docker:logs:container_id or docker:logs:container_id:offset
        parts = callback.data.split(":")
        container_id = parts[2] if len(parts) > 2 else ""
        offset = int(parts[3]) if len(parts) > 3 and parts[3].lstrip('-').isdigit() else 0

        try:
            from infrastructure.monitoring.system_monitor import create_system_monitor
            monitor = create_system_monitor()

            success, all_logs = await monitor.docker_logs(container_id, lines=DOCKER_LOGS_MAX_LINES)

            if not success:
                await safe_callback_answer(callback, f"❌ {all_logs}")
                return

            log_lines = all_logs.strip().split("\n") if all_logs.strip() else []
            total = len(log_lines)

            if total == 0:
                text = f"📋 <b>Логи</b> ({container_id})\n\n<i>(пусто)</i>"
                buttons = [[InlineKeyboardButton(text="🔙 К контейнерам", callback_data="menu:system:docker:0")]]
                await callback.message.edit_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                    parse_mode="HTML"
                )
                await callback.answer()
                return

            # Calculate pagination
            offset = max(0, min(offset, total - DOCKER_LOGS_PAGE_SIZE))
            start_idx = max(0, total - DOCKER_LOGS_PAGE_SIZE - offset)
            end_idx = total - offset

            page_logs = log_lines[start_idx:end_idx]
            current_page = offset // DOCKER_LOGS_PAGE_SIZE + 1
            total_pages = (total + DOCKER_LOGS_PAGE_SIZE - 1) // DOCKER_LOGS_PAGE_SIZE

            logs_text = "\n".join(page_logs)
            if len(logs_text) > TEXT_TRUNCATE_LIMIT:
                logs_text = logs_text[-TEXT_TRUNCATE_LIMIT:]

            text = f"📋 <b>Логи</b> ({container_id}) — {current_page}/{total_pages}\n\n<pre>{logs_text}</pre>"

            # Navigation buttons
            buttons = []
            nav_row = []

            if offset + DOCKER_LOGS_PAGE_SIZE < total:
                nav_row.append(InlineKeyboardButton(
                    text="⬅️ Старше",
                    callback_data=f"docker:logs:{container_id}:{offset + DOCKER_LOGS_PAGE_SIZE}"
                ))

            if offset > 0:
                new_offset = max(0, offset - DOCKER_LOGS_PAGE_SIZE)
                nav_row.append(InlineKeyboardButton(
                    text="Новее ➡️",
                    callback_data=f"docker:logs:{container_id}:{new_offset}"
                ))

            if nav_row:
                buttons.append(nav_row)

            buttons.append([
                InlineKeyboardButton(text="🔄 Обновить", callback_data=f"docker:logs:{container_id}:{offset}"),
                InlineKeyboardButton(text="🔙 Назад", callback_data="menu:system:docker:0")
            ])

            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

        except Exception as e:
            logger.error(f"Error getting logs: {e}")
            await safe_callback_answer(callback, f"❌ Ошибка: {e}")

        await safe_callback_answer(callback)

    async def handle_docker_info(self, callback: CallbackQuery) -> None:
        """Handle docker container info - show detailed view with actions"""
        container_id = callback.data.split(":")[-1]
        try:
            from infrastructure.monitoring.system_monitor import SystemMonitor
            from presentation.keyboards.keyboards import Keyboards

            monitor = SystemMonitor()
            containers = await monitor.get_docker_containers()

            container = next((c for c in containers if c["id"] == container_id), None)
            if container:
                text = (
                    f"🐳 <b>Контейнер: {container['name']}</b>\n\n"
                    f"<b>ID:</b> <code>{container['id']}</code>\n"
                    f"<b>Статус:</b> {container['status']}\n"
                    f"<b>Образ:</b> <code>{container['image']}</code>\n"
                )
                if container.get("ports"):
                    text += f"<b>Порты:</b> {', '.join(str(p) for p in container['ports'])}\n"

                await callback.message.edit_text(
                    text,
                    parse_mode="HTML",
                    reply_markup=Keyboards.container_actions(
                        container_id, container["status"],
                        show_back=True, back_to="docker:list"
                    )
                )
            else:
                await safe_callback_answer(callback, "Контейнер не найден")

        except Exception as e:
            logger.error(f"Error getting container info: {e}")
            await safe_callback_answer(callback, f"❌ Ошибка: {e}")

    async def handle_metrics_top(self, callback: CallbackQuery) -> None:
        """Handle metrics top callback - show top processes"""
        try:
            from infrastructure.monitoring.system_monitor import create_system_monitor
            monitor = create_system_monitor()

            processes = await monitor.get_top_processes(limit=10)

            if not processes:
                text = "📊 Нет данных о процессах"
            else:
                lines = ["📊 <b>Top процессы:</b>\n"]
                for p in processes:
                    lines.append(
                        f"<code>{p['pid']:>6}</code> "
                        f"{p['cpu']:>5.1f}% "
                        f"{p['memory']:>5.1f}% "
                        f"{p['name'][:20]}"
                    )
                text = "\n".join(lines)

            from presentation.keyboards.keyboards import Keyboards
            await callback.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=Keyboards.metrics_actions()
            )

        except Exception as e:
            logger.error(f"Error getting top processes: {e}")
            await safe_callback_answer(callback, f"❌ Ошибка: {e}")

        await safe_callback_answer(callback)
