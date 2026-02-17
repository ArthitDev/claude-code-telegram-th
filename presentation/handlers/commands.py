import logging
import os
from aiogram import Router, F, types
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.enums import ParseMode
from application.services.bot_service import BotService
from domain.value_objects.project_path import ProjectPath
from infrastructure.claude_code.proxy_service import ClaudeCodeProxyService
from infrastructure.claude_code.diagnostics import run_diagnostics, format_diagnostics_for_telegram
from presentation.keyboards.keyboards import Keyboards

logger = logging.getLogger(__name__)

# Claude Code plugin commands that should be passed through to SDK/CLI
# These are NOT Telegram bot commands - they are Claude Code slash commands
CLAUDE_SLASH_COMMANDS = {
    "ralph-loop", "cancel-ralph",  # ralph-loop plugin
    "commit", "commit-push-pr", "clean_gone",  # commit-commands plugin
    "code-review", "review-pr",  # code-review plugin
    "feature-dev",  # feature-dev plugin
    "frontend-design",  # frontend-design plugin
    "plan", "explore",  # built-in agent commands
}
router = Router()


class CommandHandlers:
    """Bot command handlers for Claude Code proxy"""

    def __init__(
        self,
        bot_service: BotService,
        claude_proxy: ClaudeCodeProxyService,
        message_handlers=None,  # Optional, set after initialization
        project_service=None,   # ProjectService for /change
        context_service=None,   # ContextService for /context
        file_browser_service=None,  # FileBrowserService for /cd
        account_service=None  # AccountService for language
    ):
        self.bot_service = bot_service
        self.claude_proxy = claude_proxy
        self.message_handlers = message_handlers
        self.project_service = project_service
        self.context_service = context_service
        self.file_browser_service = file_browser_service
        self.account_service = account_service

    async def start(self, message: Message) -> None:
        """Handle /start command - show main inline menu"""
        user = await self.bot_service.get_or_create_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )

        # Access denied - user not in ALLOWED_USER_ID whitelist
        if user is None:
            await message.answer(
                "🚫 <b>Access Denied</b>\n\n"
                "You are not authorized to use this bot.\n"
                f"Your Telegram ID: <code>{message.from_user.id}</code>\n\n"
                "<i>Contact the bot administrator to request access.</i>",
                parse_mode="HTML"
            )
            logger.warning(f"Access denied for user {message.from_user.id} (@{message.from_user.username})")
            return

        user_id = message.from_user.id

        # Check if user has language set (first launch detection)
        user_lang = None
        if self.account_service:
            user_lang = await self.account_service.get_user_language(user_id)

        # If no language set, show language selection first
        if not user_lang or user_lang == "":
            await message.answer(
                "🌐 <b>Select language / Выберите язык / 选择语言 / เลือกภาษา</b>",
                parse_mode="HTML",
                reply_markup=Keyboards.language_select()
            )
            return

        # Check if user has OS type set (first launch detection)
        os_type = None
        if self.account_service:
            settings = await self.account_service.get_account_settings(user_id)
            if settings:
                os_type = getattr(settings, 'os_type', None)
            # If no settings at all, we also need to show OS selection

        # If no OS set (including no settings), show OS selection
        if not os_type or os_type == "":
            await message.answer(
                "🖥️ <b>Select your Operating System / เลือกระบบปฏิบัติการ</b>\n\n"
                "This helps the bot use correct file paths for your system.",
                parse_mode="HTML",
                reply_markup=Keyboards.os_select()
            )
            return

        # Calculate working directory based on OS type
        detected_dir = None
        import os as os_module
        import getpass

        if os_type == "auto":
            detected_dir = ProjectPath.ROOT
        elif os_type == "windows":
            username = getpass.getuser()
            detected_dir = f"C:\\Users\\{username}\\projects"
        elif os_type == "linux":
            detected_dir = "/root/projects"
        elif os_type == "linux_user":
            username = getpass.getuser()
            detected_dir = f"/home/{username}/projects"
        elif os_type == "macos":
            username = getpass.getuser()
            detected_dir = f"/Users/{username}/projects"

        # Update working directory if we have a detected path
        if detected_dir:
            if self.message_handlers:
                self.message_handlers.set_working_dir(user_id, detected_dir)
                logger.info(f"[{user_id}] OS={os_type}, working_dir: {detected_dir}")

            # Update project in database if exists
            if self.project_service:
                try:
                    from domain.value_objects.user_id import UserId
                    uid = UserId.from_int(user_id)
                    project = await self.project_service.get_current(uid)
                    if project and project.working_dir != detected_dir:
                        await self.project_service.update_working_dir(uid, detected_dir)
                        logger.info(f"[{user_id}] Updated project working_dir to: {detected_dir}")
                except Exception as e:
                    logger.warning(f"[{user_id}] Could not update project working_dir: {e}")

        # Load translator for user's language
        from shared.i18n import get_translator
        t = get_translator(user_lang)

        # Get working directory and project info
        # Use auto-detected directory if available, otherwise fall back to message_handlers
        if detected_dir:
            working_dir = detected_dir
        else:
            working_dir = "/root"
            if self.message_handlers:
                working_dir = self.message_handlers.get_working_dir(user_id)

        project_name = None

        # Get current project name (always get it for display)
        # Only override working_dir if we didn't just auto-detect it
        if self.project_service:
            try:
                from domain.value_objects.user_id import UserId
                uid = UserId.from_int(user_id)
                project = await self.project_service.get_current(uid)
                if project:
                    project_name = project.name
                    if not detected_dir:
                        working_dir = project.working_dir
            except Exception:
                pass

        # Get YOLO status
        yolo_enabled = False
        if self.message_handlers:
            yolo_enabled = self.message_handlers.is_yolo_mode(user_id)

        # Check if task running
        has_task = False
        if self.message_handlers and hasattr(self.message_handlers, 'sdk_service'):
            if self.message_handlers.sdk_service:
                has_task = self.message_handlers.sdk_service.is_task_running(user_id)
        if not has_task:
            has_task = self.claude_proxy.is_task_running(user_id)

        # Build status text using translations
        project_info = t("start.project", name=project_name) if project_name else t("start.no_project")
        path_info = f"📁 <code>{working_dir}</code>"

        status_parts = [project_info, path_info]
        if yolo_enabled:
            status_parts.append(t("start.yolo_on"))
        if has_task:
            status_parts.append(t("start.task_running"))

        text = (
            f"🤖 <b>Claude Code Telegram</b>\n\n"
            f"{t('start.greeting', name=user.first_name)}\n\n"
            f"{chr(10).join(status_parts)}\n\n"
            f"<i>{t('start.ready')}</i>"
        )

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=Keyboards.main_menu_inline(
                working_dir=working_dir,
                project_name=project_name,
                yolo_enabled=yolo_enabled,
                has_active_task=has_task,
                lang=user_lang
            )
        )

    async def help(self, message: Message) -> None:
        """Handle /help command"""
        help_text = """
🤖 <b>Claude Code Telegram Proxy - วิธีใช้</b>

<b>การนำทางและโปรเจกต์:</b>
/cd - นำทางระหว่างโฟลเดอร์
/change - เปลี่ยนโปรเจกต์
/fresh - ล้างบริบท (Context) เริ่มคุยเรื่องใหม่

<b>การจัดการบริบท:</b>
/context new - สร้างบริบทใหม่
/context list - รายการบริบททั้งหมด
/context clear - ล้างบริบทปัจจุบัน
/vars - จัดการตัวแปรในบริบท

<b>Claude Code:</b>
/yolo - โหมด YOLO (อนุมัติอัตโนมัติ)
/plugins - แสดงรายการปลั๊กอิน
/cancel - ยกเลิกงานที่กำลังทำ
/status - สถานะระบบ Claude Code

<b>การตรวจสอบระบบ:</b>
/metrics - ดูเมตริกของระบบ (CPU, RAM, Disk)
/docker - รายการ Docker Containers

<b>คำสั่งพื้นฐาน:</b>
/start - เริ่มต้นใช้งานบอท
/help - แสดงหน้านี้
/stats - ดูสถิติการใช้งานของคุณ
/clear - ล้างประวัติแชทบนหน้าจอ
/session - เริ่มเซสชันและการสนทนาใหม่

<b>หลักการทำงาน:</b>
1. พิมพ์สิ่งที่ต้องการให้ทำเป็นข้อความ
2. Claude Code จะเริ่มทำงาน
3. คุณจะเห็นผลลัพธ์แบบ Real-time
4. กดปุ่มยืนยัน/ปฏิเสธ เมื่อบอทถาม
5. ตอบคำถามเพิ่มเติมถ้า Claude ต้องการข้อมูล

<b>HITL (Human-in-the-Loop):</b>
🔐 <b>การอนุญาต</b> - ต้องกดยืนยันสำหรับคำสั่งที่อาจมีผลกระทบ
❓ <b>คำถาม</b> - ตอบคำถามเมื่อ Claude ไม่แน่ใจ
🛑 <b>ยกเลิก</b> - สั่งหยุดงานได้ทุกเมื่อ

<b>ตัวอย่างการใช้งาน:</b>
• "เขียน Python script เพื่อแสดง hello world"
• "อ่านไฟล์ README.md แล้วสรุปให้หน่อย"
• "รันคำสั่ง npm install ในโปรเจกต์นี้"
• "ช่วยแก้บั๊กในไฟล์ main.py หน่อย"

พิมพ์สิ่งที่คุณต้องการได้เลย!
        """
        await message.answer(help_text, parse_mode="HTML")

    async def clear(self, message: Message) -> None:
        """Handle /clear command"""
        await self.bot_service.clear_session(message.from_user.id)
        await message.answer("🧹 ล้างประวัติแชทเรียบร้อย!")

    async def session(self, message: Message) -> None:
        """Handle /session command - start new session and clear context"""
        user_id = message.from_user.id

        # Cancel any running task first
        if self.message_handlers and hasattr(self.message_handlers, 'sdk_service'):
            if self.message_handlers.sdk_service.is_task_running(user_id):
                await self.message_handlers.sdk_service.cancel_task(user_id)

        # Clear project context if available
        if self.project_service and self.context_service:
            try:
                from domain.value_objects.user_id import UserId
                uid = UserId.from_int(user_id)
                project = await self.project_service.get_current(uid)
                if project:
                    context = await self.context_service.get_current(project.id)
                    if context:
                        await self.context_service.clear(context.id)
            except Exception as e:
                logger.warning(f"[{user_id}] Could not clear context: {e}")

        # Clear legacy session
        await self.bot_service.clear_session(user_id)

        await message.answer(
            "🆕 <b>เริ่มเซสชันใหม่เรียบร้อย!</b>\n\n"
            "บริบทการสนทนาได้รับการล้างแล้ว\n"
            "พร้อมเริ่มต้นใหม่กับ Claude Code",
            parse_mode="HTML"
        )

    async def stats(self, message: Message) -> None:
        """Handle /stats command"""
        stats = await self.bot_service.get_user_stats(message.from_user.id)

        # Build command stats safely
        by_status = stats.get('commands', {}).get('by_status', {})
        stat_text_lines = [f"  • {k}: {v}" for k, v in by_status.items() if k != 'total']
        status_text = "\n".join(stat_text_lines) if stat_text_lines else "  ไม่มีข้อมูล"

        text = f"""📊 <b>สถิติของคุณ</b>

<b>ผู้ใช้:</b> {stats.get('user', {}).get('username', 'ไม่ระบุ')}
<b>บทบาท:</b> {stats.get('user', {}).get('role', 'user')}
<b>สถานะ:</b> {'✅ ใช้งานอยู่' if stats.get('user', {}).get('is_active') else '❌ ไม่ใช้งาน'}

<b>คำสั่ง:</b>
• ทั้งหมด: {stats.get('commands', {}).get('total', 0)}
{status_text}

<b>เซสชัน:</b>
• ทั้งหมด: {stats.get('sessions', {}).get('total', 0)}
• กำลังใช้งาน: {stats.get('sessions', {}).get('active', 0)}"""
        await message.answer(text, parse_mode="HTML")

    async def metrics(self, message: Message) -> None:
        """Handle /metrics command and 📊 Метрики button"""
        info = await self.bot_service.get_system_info()

        metrics = info["metrics"]
        lines = [
            "📊 <b>เมตริกของระบบ</b>",
            "",
            f"💻 <b>CPU:</b> {metrics['cpu_percent']:.1f}%",
            f"🧠 <b>RAM:</b> {metrics['memory_percent']:.1f}% ({metrics['memory_used_gb']}GB / {metrics['memory_total_gb']}GB)",
            f"💾 <b>Disk:</b> {metrics['disk_percent']:.1f}% ({metrics['disk_used_gb']}GB / {metrics['disk_total_gb']}GB)",
        ]

        if metrics.get('load_average', [0])[0] > 0:
            lines.append(f"📈 <b>Load Avg:</b> {metrics['load_average'][0]:.2f}")

        # Show alerts
        if info.get("alerts"):
            lines.append("\n⚠️ <b>การแจ้งเตือน:</b>")
            lines.extend(info["alerts"])

        await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=Keyboards.system_metrics(show_back=True, back_to="menu:system"))

    async def docker(self, message: Message) -> None:
        """Handle /docker command and 🐳 Docker button"""
        try:
            from infrastructure.monitoring.system_monitor import create_system_monitor
            monitor = create_system_monitor()
            containers = await monitor.get_docker_containers()

            if not containers:
                await message.answer(
                    "🐳 <b>Docker Containers</b>\n\n"
                    "ไม่พบ Container ที่กำลังทำงาน\n\n"
                    "ใช้ Claude Code เพื่อจัดการ Docker:\n"
                    "• 'docker ps -a'\n"
                    "• 'docker run ...'",
                    parse_mode="HTML"
                )
                return

            # Build container list with action buttons
            lines = ["🐳 <b>Docker Containers:</b>\n"]
            for c in containers:
                status_emoji = "🟢" if c["status"] == "running" else "🔴"
                lines.append(f"\n{status_emoji} <b>{c['name']}</b>")
                lines.append(f"   สถานะ: {c['status']}")
                lines.append(f"   Image: <code>{c['image'][:30]}</code>")

            text = "\n".join(lines)
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=Keyboards.docker_list(containers, show_back=True, back_to="menu:system")
            )

        except Exception as e:
            logger.error(f"Error getting docker containers: {e}")
            await message.answer(
                f"🐳 Docker\n\n❌ Ошибка: {e}",
                parse_mode=None
            )

    async def project(self, message: Message, command: CommandObject) -> None:
        """Handle /project command - set working directory"""
        user_id = message.from_user.id

        if command.args:
            # Set working directory directly
            path = command.args.strip()

            # Validate path exists (basic check)
            if not os.path.isabs(path):
                path = os.path.abspath(path)

            if self.message_handlers:
                self.message_handlers.set_working_dir(user_id, path)
                await message.answer(
                    f"📁 <b>ตั้งค่าโฟลเดอร์ทำงานเรียบร้อย:</b>\n<code>{path}</code>",
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    "⚠️ ระบบข้อความยังไม่พร้อมใช้งาน",
                    parse_mode=None
                )
        else:
            # Show current working directory and prompt for input
            current_dir = "/root"
            if self.message_handlers:
                current_dir = self.message_handlers.get_working_dir(user_id)

            # List some common project directories
            projects = []
            for dir_path in ["/root", "/home", "/var/www", "/opt"]:
                if os.path.exists(dir_path):
                    projects.append({"name": os.path.basename(dir_path) or dir_path, "path": dir_path})

            await message.answer(
                f"📁 <b>โฟลเดอร์ทำงานปัจจุบัน:</b>\n<code>{current_dir}</code>\n\n"
                f"ใช้คำสั่ง `/project <path>` เพื่อเปลี่ยน\n\n"
                f"ตัวอย่าง:\n<code>/project /home/myproject</code>",
                parse_mode="HTML",
                reply_markup=Keyboards.project_selection(projects) if projects else None
            )

    async def change(self, message: Message) -> None:
        """Handle /change command - show project list for switching"""
        user_id = message.from_user.id

        if not self.project_service:
            await message.answer("⚠️ Project Service ยังไม่พร้อมใช้งาน")
            return

        from domain.value_objects.user_id import UserId
        uid = UserId.from_int(user_id)

        # Get user's projects
        projects = await self.project_service.list_projects(uid)
        current = await self.project_service.get_current(uid)

        current_name = current.name if current else "ไม่มี"
        current_id = current.id if current else None

        # Get user language
        user_lang = "ru"
        if self.account_service:
            user_lang = await self.account_service.get_user_language(message.from_user.id)

        if projects:
            text = (
                f"📂 <b>เปลี่ยนโปรเจกต์</b>\n\n"
                f"ปัจจุบัน: <b>{current_name}</b>\n\n"
                f"เลือกโปรเจกต์:"
            )
            keyboard = Keyboards.project_list(projects, current_id, show_back=True, back_to="menu:projects", lang=user_lang)
        else:
            text = (
                f"📂 <b>ไม่พบโปรเจกต์</b>\n\n"
                f"คุณยังไม่มีโปรเจกต์\n"
                f"สร้างใหม่หรือเปิด `{ProjectPath.ROOT}`"
            )
            keyboard = Keyboards.project_list([], None, show_create=True, show_back=True, back_to="menu:projects", lang=user_lang)

        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

    async def context(self, message: Message, command: CommandObject) -> None:
        """Handle /context command - show interactive context menu"""
        user_id = message.from_user.id

        if not self.project_service or not self.context_service:
            await message.answer("⚠️ Services ยังไม่พร้อมใช้งาน")
            return

        from domain.value_objects.user_id import UserId
        uid = UserId.from_int(user_id)

        # Get current project
        project = await self.project_service.get_current(uid)
        if not project:
            await message.answer(
                "❌ ไม่พบโปรเจกต์ที่ใช้งานอยู่\n\n"
                "ใช้ /change เพื่อเลือกโปรเจกต์",
                parse_mode=None
            )
            return

        # Get current context
        current_ctx = await self.context_service.get_current(project.id)
        ctx_name = current_ctx.name if current_ctx else "ไม่ระบุ"
        msg_count = current_ctx.message_count if current_ctx else 0
        has_session = current_ctx.has_session if current_ctx else False

        # Build status text
        session_status = "📜 มีเซสชัน" if has_session else "✨ ว่าง"
        text = (
            f"💬 จัดการบริบท (Context)\n\n"
            f"📂 โปรเจกต์: {project.name}\n"
            f"💬 Context: {ctx_name}\n"
            f"📝 ข้อความ: {msg_count}\n"
            f"📌 สถานะ: {session_status}"
        )

        keyboard = Keyboards.context_menu(ctx_name, project.name, msg_count, show_back=True, back_to="menu:context")
        await message.answer(text, parse_mode=None, reply_markup=keyboard)

    async def fresh(self, message: Message) -> None:
        """
        Handle /fresh command - create new context for fresh conversation.

        Creates a new context and switches to it, ensuring:
        - New Claude session (no memory of previous conversation)
        - Clean message history
        - Old contexts remain available for switching back
        """
        user_id = message.from_user.id

        # Clear internal session cache
        if self.message_handlers:
            self.message_handlers.clear_session_cache(user_id)

        # Create new context in project
        if self.project_service and self.context_service:
            from domain.value_objects.user_id import UserId
            uid = UserId.from_int(user_id)

            project = await self.project_service.get_current(uid)
            if project:
                # Create new context (auto-generated name, set as current)
                new_context = await self.context_service.create_new(
                    project_id=project.id,
                    user_id=uid,
                    name=None,  # Auto-generate name
                    set_as_current=True
                )

                await message.answer(
                    f"✅ บริบทใหม่ถูกสร้างแล้ว!\n\n"
                    f"📂 โปรเจกต์: {project.name}\n"
                    f"💬 Context: {new_context.name}\n\n"
                    f"เริ่มการสนทนาใหม่ได้เลย",
                    parse_mode=None
                )
                return

        # No project/context - just clear bot service session
        await self.bot_service.clear_session(user_id)
        await message.answer(
            "🧹 ล้างเซสชันแล้ว!\n\n"
            "ข้อความถัดไปจะเป็นการเริ่มบทสนทนาใหม่",
            parse_mode=None
        )

    async def yolo(self, message: Message) -> None:
        """
        Handle /yolo command - toggle YOLO mode.

        YOLO mode auto-approves all operations without waiting for confirmation.
        Use with caution!
        """
        import asyncio

        user_id = message.from_user.id

        if not self.message_handlers:
            # Get user language
            user_lang = "ru"  # default
            if self.account_service:
                user_lang = await self.account_service.get_user_language(user_id) or "ru"
            
            from shared.i18n import get_translator
            t = get_translator(user_lang)
            await message.answer(t("service.not_initialized"))
            return

        # Get user language
        user_lang = "ru"  # default
        if self.account_service:
            user_lang = await self.account_service.get_user_language(user_id) or "ru"
        
        from shared.i18n import get_translator
        t = get_translator(user_lang)

        current = self.message_handlers.is_yolo_mode(user_id)
        new_state = not current
        self.message_handlers.set_yolo_mode(user_id, new_state)

        if new_state:
            response = await message.answer(
                f"🚀 <b>YOLO Mode: ON</b> ⚡",
                parse_mode="HTML"
            )
        else:
            response = await message.answer(
                f"🛡️ <b>YOLO Mode: OFF</b>",
                parse_mode="HTML"
            )

        # Delete command and response after 2 seconds
        async def delete_messages():
            await asyncio.sleep(2)
            try:
                await message.delete()
            except Exception:
                pass
            try:
                await response.delete()
            except Exception:
                pass

        asyncio.create_task(delete_messages())

    async def cd(self, message: Message, command: CommandObject) -> None:
        """
        Handle /cd command - interactive folder navigation.

        Usage:
            /cd           - Show current directory with navigation
            /cd ..        - Go to parent directory
            /cd <folder>  - Navigate to folder
            /cd ~         - Go to root
        """
        user_id = message.from_user.id

        if not self.file_browser_service:
            # Fallback: create service on demand
            from application.services.file_browser_service import FileBrowserService
            self.file_browser_service = FileBrowserService()

        # Get current working directory
        current_dir = ProjectPath.ROOT
        if self.message_handlers:
            current_dir = self.message_handlers.get_working_dir(user_id)

        # Ensure current_dir is within root
        if not self.file_browser_service.is_within_root(current_dir):
            current_dir = self.file_browser_service.ROOT_PATH

        # Resolve target path
        if command.args:
            target = command.args.strip()
            target_path = self.file_browser_service.resolve_path(current_dir, target)
        else:
            target_path = current_dir

        # Ensure directory exists
        if not os.path.isdir(target_path):
            # Try creating if it's a subdir of root
            if self.file_browser_service.is_within_root(target_path):
                try:
                    os.makedirs(target_path, exist_ok=True)
                except OSError:
                    target_path = self.file_browser_service.ROOT_PATH
            else:
                target_path = self.file_browser_service.ROOT_PATH

        # Get directory content and tree view
        content = await self.file_browser_service.list_directory(target_path)
        tree_view = await self.file_browser_service.get_tree_view(target_path)

        # Send with HTML formatting
        await message.answer(
            tree_view,
            parse_mode=ParseMode.HTML,
            reply_markup=Keyboards.file_browser(content)
        )

    async def cancel(self, message: Message) -> None:
        """Handle /cancel command - cancel running Claude Code task"""
        user_id = message.from_user.id
        cancelled = False

        # Get user language
        user_lang = "ru"  # default
        if self.account_service:
            user_lang = await self.account_service.get_user_language(user_id) or "ru"
        
        from shared.i18n import get_translator
        t = get_translator(user_lang)

        # Try SDK first (preferred) - it handles full cleanup including status reset
        if self.message_handlers and hasattr(self.message_handlers, 'sdk_service'):
            sdk_service = self.message_handlers.sdk_service
            if sdk_service:
                cancelled = await sdk_service.cancel_task(user_id)
                if cancelled:
                    await message.answer(t("claude.task_cancelled"), parse_mode="HTML")
                    return

        # Try CLI fallback
        if self.claude_proxy:
            cli_cancelled = await self.claude_proxy.cancel_task(user_id)
            if cli_cancelled:
                await message.answer(t("claude.task_cancelled"), parse_mode="HTML")
                return

        if not cancelled:
            await message.answer(t("cancel.no_task"))

    async def status(self, message: Message) -> None:
        """Handle /status command - show Claude Code status"""
        user_id = message.from_user.id

        # Check if Claude Code CLI is installed
        installed, version_info = await self.claude_proxy.check_claude_installed()

        # Check SDK availability
        sdk_status = "❌ Недоступен"
        sdk_running = False
        if self.message_handlers and hasattr(self.message_handlers, 'sdk_service'):
            sdk_service = self.message_handlers.sdk_service
            if sdk_service:
                sdk_ok, sdk_msg = await sdk_service.check_sdk_available()
                sdk_status = "🟢 พร้อมใช้งาน (HITL)" if sdk_ok else f"🔴 {sdk_msg}"
                sdk_running = sdk_service.is_task_running(user_id)

        # Check if task is running (either backend)
        cli_running = self.claude_proxy.is_task_running(user_id)
        is_running = sdk_running or cli_running

        # Get working directory
        working_dir = "/root"
        if self.message_handlers:
            working_dir = self.message_handlers.get_working_dir(user_id)

        cli_emoji = "🟢" if installed else "🔴"
        task_status = "🔄 กำลังทำงาน" if is_running else "⏸️ ว่าง"

        # Determine backend in use
        backend = "SDK" if sdk_running else ("CLI" if cli_running else "ว่าง")

        text = f"""
📊 <b>สถานะ Claude Code</b>

<b>CLI:</b> {cli_emoji} {version_info}
<b>SDK:</b> {sdk_status}
<b>ภารกิจ:</b> {task_status} ({backend})
<b>โฟลเดอร์ทำงาน:</b> <code>{working_dir}</code>
"""

        if is_running:
            text += "\n\nใช้ /cancel เพื่อหยุดภารกิจปัจจุบัน"

        text += "\n\nใช้ /diagnose เพื่อตรวจสอบระบบแบบละเอียด"

        await message.answer(text, parse_mode="HTML")

    async def diagnose(self, message: Message) -> None:
        """Handle /diagnose command - run full Claude Code diagnostics"""
        await message.answer("🔍 เริ่มการตรวจสอบระบบ... (อาจใช้เวลาถึง 30 วินาที)")

        try:
            results = await run_diagnostics(self.claude_proxy.claude_path)
            text = format_diagnostics_for_telegram(results)
            await message.answer(text, parse_mode=None)
        except Exception as e:
            await message.answer(f"❌ การตรวจสอบล้มเหลว: {e}")

    async def claude_command_passthrough(self, message: Message, command: CommandObject) -> None:
        """
        Handle Claude Code slash commands by passing them to SDK/CLI.

        Commands like /ralph-loop, /commit, /code-review are Claude Code commands
        that should be executed by Claude, not by the Telegram bot.

        IMPORTANT: We send the command as "run /<command>" instead of just "/<command>"
        because the slash prefix alone is interpreted as a local CLI macro that expands
        but doesn't trigger an API call. By saying "run", we instruct Claude to invoke
        the Skill tool which actually executes the skill/plugin.

        Supports reply to file - file content will be added to the command context.
        """
        user_id = message.from_user.id
        command_name = command.command  # e.g., "ralph-loop"

        logger.info(f"[{user_id}] Claude Code command passthrough: /{command_name}")

        # Build the prompt to invoke the skill via Claude's Skill tool
        # We say "run /command" so Claude knows to invoke the Skill tool,
        # rather than treating it as a local CLI macro
        skill_command = f"/{command_name}"
        if command.args:
            skill_command += f" {command.args}"

        # Instruct Claude to run the skill
        prompt = f"run {skill_command}"

        # Check if message handlers are available
        if not self.message_handlers:
            await message.answer(
                "⚠️ ระบบข้อความไม่พร้อมใช้งาน\n"
                "ไม่สามารถส่งคำสั่งไปยัง Claude Code ได้",
                parse_mode=None
            )
            return

        # Check for reply to file - add file context to command
        reply = message.reply_to_message
        file_info = ""
        if reply and self.message_handlers.file_processor_service:
            # Check if reply message has a cached file
            if reply.message_id in self.message_handlers._file_cache:
                processed_file = self.message_handlers._file_cache.pop(reply.message_id)
                prompt = self.message_handlers.file_processor_service.format_for_prompt(
                    processed_file, prompt
                )
                file_info = f"\n📎 Файл: {processed_file.filename}"
                logger.info(f"[{user_id}] Added cached file to command: {processed_file.filename}")

            # Check if reply message has document/photo
            elif reply.document or reply.photo:
                file_context = await self.message_handlers._extract_reply_file_context(
reply, message.bot
                )
                if file_context:
                    processed_file, _ = file_context
                    prompt = self.message_handlers.file_processor_service.format_for_prompt(
                        processed_file, prompt
                    )
                    file_info = f"\n📎 {processed_file.filename}"
                    logger.info(f"[{user_id}] Added reply file to command: {processed_file.filename}")

        # Get user language for response
        user_lang = "ru"  # default
        if self.account_service:
            user_lang = await self.account_service.get_user_language(user_id) or "ru"
        
        from shared.i18n import get_translator
        t = get_translator(user_lang)

        # Inform user that command is being passed through
        await message.answer(
            f"{t('plugins.plugin_command', command=skill_command)}{file_info}\n\n"
            f"{t('plugins.passing_to_claude')}",
            parse_mode="HTML"
        )

        # Pass the command to handle_text with prompt_override and force_new_session
        # Plugin commands need a fresh session, not resume of previous conversation
        await self.message_handlers.handle_text(
            message,
            prompt_override=prompt,
            force_new_session=True
        )

    async def plugins(self, message: Message) -> None:
        """
        Handle /plugins command - show and manage Claude Code plugins.

        Displays list of enabled plugins with ability to:
        - View plugin info
        - Enable/disable plugins
        - Browse marketplace for new plugins
        """
        user_id = message.from_user.id
        
        # Get user language
        user_lang = "ru"  # default
        if self.account_service:
            user_lang = await self.account_service.get_user_language(user_id) or "ru"
        
        from shared.i18n import get_translator
        t = get_translator(user_lang)
        
        if not self.message_handlers or not hasattr(self.message_handlers, 'sdk_service'):
            await message.answer(t("plugins.sdk_not_initialized"))
            return

        sdk_service = self.message_handlers.sdk_service
        if not sdk_service:
            await message.answer(t("plugins.sdk_not_available"))
            return

        # Get enabled plugins info
        plugins = sdk_service.get_enabled_plugins_info()

        if not plugins:
            text = (
                f"{t('plugins.claude_code_title')}\n\n"
                f"{t('plugins.no_active')}\n\n"
                f"{t('plugins.click_marketplace')}"
            )
        else:
            text = f"{t('plugins.claude_code_title')}\n\n"
            for p in plugins:
                name = p.get("name", "unknown")
                desc = p.get("description", "")
                source = p.get("source", "official")
                available = p.get("available", True)

                status = "✅" if available else "⚠️"
                source_icon = "🌐" if source == "official" else "📁"
                
                # Try translation first
                trans_key = f"plugins.desc.{name}"
                translated = t(trans_key)
                if translated != trans_key:
                    desc_text = translated
                else:
                    desc_text = desc

                text += f"{status} {source_icon} <b>{name}</b>\n"
                if desc_text:
                    text += f"   <i>{desc_text}</i>\n"
                text += "\n"  # Empty line

            text += f"<i>{t('plugins.total', count=len(plugins))}</i>"

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=Keyboards.plugins_menu(plugins, lang=user_lang)
        )

    async def vars(self, message: Message, command: CommandObject) -> None:
        """
        Handle /vars command - manage context variables with interactive menu.

        Usage:
            /vars                          - show interactive menu
            /vars set NAME value [desc]    - set a variable (legacy)
            /vars del NAME                 - delete a variable (legacy)

        Variables are automatically included in Claude's context.
        Description helps Claude understand how to use the variable.
        """
        user_id = message.from_user.id

        if not self.project_service or not self.context_service:
            await message.answer("⚠️ Сервисы не инициализированы")
            return

        from domain.value_objects.user_id import UserId
        from presentation.keyboards.keyboards import Keyboards
        uid = UserId.from_int(user_id)

        # Get current project and context
        project = await self.project_service.get_current(uid)
        if not project:
            await message.answer(
                "❌ Нет активного проекта\n\n"
                "Используйте /change для выбора проекта.",
                parse_mode=None
            )
            return

        context = await self.context_service.get_current(project.id)
        if not context:
            await message.answer(
                "❌ Нет активного контекста\n\n"
                "Используйте /context для создания контекста.",
                parse_mode=None
            )
            return

        args = command.args.strip() if command.args else ""

        # No args - show interactive menu
        if not args:
            variables = await self.context_service.get_variables(context.id)

            if variables:
                lines = [f"📋 Переменные контекста\n"]
                lines.append(f"📂 {project.name} / {context.name}\n")
                for name in sorted(variables.keys()):
                    var = variables[name]
                    # Mask long values
                    display = var.value[:8] + "***" if len(var.value) > 8 else var.value
                    lines.append(f"• {name} = {display}")
                    if var.description:
                        lines.append(f"  ↳ {var.description[:50]}")
                text = "\n".join(lines)
            else:
                text = (
                    f"📋 Переменные контекста\n\n"
                    f"📂 {project.name} / {context.name}\n\n"
                    f"Переменных пока нет.\n"
                    f"Нажмите ➕ Добавить для создания."
                )

            keyboard = Keyboards.variables_menu(variables, project.name, context.name, show_back=True, back_to="menu:context")
            await message.answer(text, parse_mode=None, reply_markup=keyboard)
            return

        # Parse action (legacy text commands)
        parts = args.split(maxsplit=3)
        action = parts[0].lower()

        if action == "set":
            if len(parts) < 3:
                await message.answer(
                    "❌ Использование: /vars set NAME value [description]",
                    parse_mode=None
                )
                return

            name = parts[1].upper()  # Variable names are uppercase
            value = parts[2]
            description = parts[3] if len(parts) > 3 else ""

            await self.context_service.set_variable(context.id, name, value, description)
            resp = f"✅ Установлена переменная: {name}\n"
            if description:
                resp += f"Описание: {description}\n"
            resp += f"\nClaude будет использовать её автоматически."
            await message.answer(resp, parse_mode=None)
            return

        if action == "del" or action == "delete":
            if len(parts) < 2:
                await message.answer(
                    "❌ Использование: /vars del NAME",
                    parse_mode=None
                )
                return

            name = parts[1].upper()
            deleted = await self.context_service.delete_variable(context.id, name)

            if deleted:
                await message.answer(
                    f"🗑 Удалена переменная: {name}",
                    parse_mode=None
                )
            else:
                await message.answer(
                    f"⚠️ Переменная {name} не найдена",
                    parse_mode=None
                )
            return

        # Unknown action
        await message.answer(
            "❌ Неизвестная команда\n\n"
            "Используйте /vars для интерактивного меню\n"
            "или legacy команды:\n"
            "/vars set NAME value [desc] - установить\n"
            "/vars del NAME - удалить",
            parse_mode=None
        )


    async def test_question(self, message: Message) -> None:
        """Test AskUserQuestion keyboard - shows sample question with inline buttons"""
        user_id = message.from_user.id

        # Sample options like Claude would send
        options = [
            "Python + FastAPI",
            "Node.js + Express",
            "Go + Gin",
            "Rust + Actix"
        ]

        request_id = "test123"

        await message.answer(
            "<b>❓ Тестовый вопрос от Claude</b>\n\n"
            "Какой стек технологий использовать для API?\n\n"
            "<i>Выберите вариант или введите свой:</i>",
            parse_mode="HTML",
            reply_markup=Keyboards.claude_question(user_id, options, request_id)
        )


def register_handlers(router: Router, handlers: CommandHandlers) -> None:
    """
    Register command handlers.

    Only /start and /cancel are registered as Telegram commands.
    All other functionality is accessed via the inline menu system.
    """
    # Main command - shows the inline menu
    router.message.register(handlers.start, Command("start"))

    # Emergency cancel command (always available)
    router.message.register(handlers.cancel, Command("cancel"))

    # YOLO mode toggle
    router.message.register(handlers.yolo, Command("yolo"))

    # Session management - start new session
    router.message.register(handlers.session, Command("session"))

    # Test command for AskUserQuestion keyboard
    router.message.register(handlers.test_question, Command("test_question"))

    # Claude Code plugin commands passthrough
    # These are forwarded to Claude Code SDK/CLI instead of being handled by bot
    for cmd in CLAUDE_SLASH_COMMANDS:
        router.message.register(
            handlers.claude_command_passthrough,
            Command(cmd)
        )
