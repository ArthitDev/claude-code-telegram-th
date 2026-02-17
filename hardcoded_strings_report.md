# Hardcoded Russian Strings Report

**Generated**: C:\Users\EPIT-Dev\claude-code-telegram

**Total Files**: 19
**Total Occurrences**: 137

## Summary by Pattern

- **Ошибка**: 73 occurrences
- **Проект**: 21 occurrences
- **Сервис**: 11 occurrences
- **Контекст**: 7 occurrences
- **Удалить**: 6 occurrences
- **Отмена**: 4 occurrences
- **Готово**: 4 occurrences
- **Пользователь**: 3 occurrences
- **Настройки**: 3 occurrences
- **Создать**: 2 occurrences
- **Сохранить**: 2 occurrences
- **Загрузка**: 1 occurrences

## Detailed Findings


### presentation\handlers\callbacks\project.py (28 occurrences)

**Line 71** - Pattern: `Проект`
```python
await callback.answer(f"Проект: {path}")
```

**Line 86** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 117** - Pattern: `Проект`
```python
await callback.answer("❌ Проект не найден")
```

**Line 121** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 182** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 194** - Pattern: `Сервис`
```python
await callback.answer("⚠️ Сервис проектов недоступен")
```

**Line 222** - Pattern: `Проект`
```python
f"✅ <b>Проект создан:</b>\n\n"
```

**Line 225** - Pattern: `Готово`
```python
f"✨ Готово к работе! Отправьте первое сообщение.\n\n"
```

**Line 234** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 304** - Pattern: `Проект`
```python
f"✅ <b>Проект создан:</b>\n\n"
```

**Line 307** - Pattern: `Готово`
```python
f"✨ Готово к работе! Отправьте первое сообщение.\n\n"
```

**Line 319** - Pattern: `Ошибка`
```python
await message.reply(f"❌ Ошибка создания папки: {e}")
```

**Line 340** - Pattern: `Проект`
```python
await callback.answer("❌ Проект не найден")
```

**Line 349** - Pattern: `Проект`
```python
f"Проект: {project.name}\n"
```

**Line 363** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 384** - Pattern: `Проект`
```python
await callback.answer("❌ Проект не найден")
```

**Line 414** - Pattern: `Проект`
```python
f"✅ Проект удален полностью\n\n"
```

**Line 415** - Pattern: `Проект`
```python
f"Проект: {project_name}\n"
```

**Line 420** - Pattern: `Проект`
```python
f"✅ Проект удален из базы\n\n"
```

**Line 421** - Pattern: `Проект`
```python
f"Проект: {project_name}\n"
```

**Line 435** - Pattern: `Проект`
```python
await callback.answer(f"✅ Проект {project_name} удален")
```

**Line 439** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 462** - Pattern: `Проект`
```python
text = "📁 Проекты не найдены\n\nСоздайте первый проект:"
```

**Line 473** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 512** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 540** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 589** - Pattern: `Проект`
```python
f"<b>Проект:</b> {html.escape(project_name)}\n\n"
```

**Line 598** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```


### presentation\handlers\callbacks\variables.py (19 occurrences)

**Line 30** - Pattern: `Сервис`
```python
await callback.answer("⚠️ Сервисы недоступны")
```

**Line 87** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 112** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 140** - Pattern: `Удалить`
```python
InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"var:d:{var_name[:20]}")
```

**Line 149** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 181** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 198** - Pattern: `Удалить`
```python
f"🗑️ Удалить переменную?\n\n"
```

**Line 209** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 231** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 270** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 308** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}", show_alert=True)
```

**Line 329** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}", show_alert=True)
```

**Line 359** - Pattern: `Удалить`
```python
InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"gvar:d:{var_name[:20]}")
```

**Line 370** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}", show_alert=True)
```

**Line 407** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}", show_alert=True)
```

**Line 425** - Pattern: `Удалить`
```python
f"🗑️ <b>Удалить глобальную переменную?</b>\n\n"
```

**Line 436** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}", show_alert=True)
```

**Line 458** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}", show_alert=True)
```

**Line 500** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}", show_alert=True)
```


### presentation\handlers\callbacks\context.py (15 occurrences)

**Line 27** - Pattern: `Сервис`
```python
await callback.answer("⚠️ Сервисы недоступны")
```

**Line 57** - Pattern: `Проект`
```python
f"📂 Проект: {project.name}\n"
```

**Line 58** - Pattern: `Контекст`
```python
f"💬 Контекст: {ctx_name}\n"
```

**Line 72** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 87** - Pattern: `Контекст`
```python
text = f"💬 Контексты проекта {project.name}\n\nВыберите контекст:"
```

**Line 103** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 124** - Pattern: `Проект`
```python
f"📂 Проект: {project.name}\n"
```

**Line 132** - Pattern: `Контекст`
```python
await callback.answer(f"Контекст: {context.name}")
```

**Line 134** - Pattern: `Контекст`
```python
await callback.answer("❌ Контекст не найден")
```

**Line 138** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 154** - Pattern: `Проект`
```python
f"📂 Проект: {project.name}\n\n"
```

**Line 167** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 194** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 223** - Pattern: `Проект`
```python
f"📂 Проект: {project.name}\n\n"
```

**Line 235** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```


### find_hardcoded_strings.py (12 occurrences)

**Line 16** - Pattern: `Ошибка`
```python
"Ошибка",  # Error
```

**Line 17** - Pattern: `Сервис`
```python
"Сервис",  # Service
```

**Line 18** - Pattern: `Проект`
```python
"Проект",  # Project
```

**Line 19** - Pattern: `Контекст`
```python
"Контекст",  # Context
```

**Line 20** - Pattern: `Пользователь`
```python
"Пользователь",  # User
```

**Line 21** - Pattern: `Настройки`
```python
"Настройки",  # Settings
```

**Line 22** - Pattern: `Создать`
```python
"Создать",  # Create
```

**Line 23** - Pattern: `Удалить`
```python
"Удалить",  # Delete
```

**Line 24** - Pattern: `Отмена`
```python
"Отмена",  # Cancel
```

**Line 25** - Pattern: `Готово`
```python
"Готово",  # Done
```

**Line 26** - Pattern: `Загрузка`
```python
"Загрузка",  # Loading
```

**Line 27** - Pattern: `Сохранить`
```python
"Сохранить",  # Save
```


### presentation\handlers\commands.py (11 occurrences)

**Line 160** - Pattern: `Создать`
```python
/context new - Создать новый контекст
```

**Line 191** - Pattern: `Отмена`
```python
🛑 <b>Отмена</b> - Остановить задачу в любой момент
```

**Line 219** - Pattern: `Пользователь`
```python
<b>Пользователь:</b> {stats.get('user', {}).get('username', 'Неизвестно')}
```

**Line 291** - Pattern: `Ошибка`
```python
f"🐳 Docker\n\n❌ Ошибка: {e}",
```

**Line 343** - Pattern: `Сервис`
```python
await message.answer("⚠️ Сервис проектов не инициализирован")
```

**Line 378** - Pattern: `Сервис`
```python
await message.answer("⚠️ Сервисы не инициализированы")
```

**Line 404** - Pattern: `Проект`
```python
f"📂 Проект: {project.name}\n"
```

**Line 405** - Pattern: `Контекст`
```python
f"💬 Контекст: {ctx_name}\n"
```

**Line 445** - Pattern: `Проект`
```python
f"📂 Проект: {project.name}\n"
```

**Line 446** - Pattern: `Контекст`
```python
f"💬 Контекст: {new_context.name}\n\n"
```

**Line 785** - Pattern: `Сервис`
```python
await message.answer("⚠️ Сервисы не инициализированы")
```


### presentation\handlers\callbacks\claude.py (11 occurrences)

**Line 68** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 93** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 120** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 157** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 179** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 208** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 233** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 265** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 287** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 312** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 339** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```


### presentation\handlers\menu_handlers.py (8 occurrences)

**Line 680** - Pattern: `Сервис`
```python
"❌ Сервис аккаунтов не инициализирован",
```

**Line 690** - Pattern: `Настройки`
```python
f"🔧 <b>Настройки аккаунта</b>\n\n"
```

**Line 713** - Pattern: `Ошибка`
```python
f"❌ Ошибка: {str(e)}",
```

**Line 881** - Pattern: `Ошибка`
```python
f"❌ Ошибка: {str(e)}",
```

**Line 1090** - Pattern: `Удалить`
```python
InlineKeyboardButton(text="🗑 Удалить", callback_data=f"docker:rm:{cid}"),
```

**Line 1112** - Pattern: `Ошибка`
```python
f"🐳 Docker\n\n❌ Ошибка: {str(e)[:300]}",
```

**Line 1201** - Pattern: `Отмена`
```python
🛑 <b>Отмена</b> - Можно отменить задачу в любой момент
```

**Line 1231** - Pattern: `Отмена`
```python
• Отмена: /cancel-ralph
```


### presentation\handlers\callbacks\docker.py (6 occurrences)

**Line 45** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 78** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 112** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 206** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 244** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```

**Line 276** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```


### application\services\file_processor_service.py (5 occurrences)

**Line 45** - Pattern: `Сервис`
```python
Сервис обработки файлов для добавления в контекст Claude.
```

**Line 247** - Pattern: `Ошибка`
```python
error=f"Ошибка обработки: {str(e)}"
```

**Line 300** - Pattern: `Сохранить`
```python
Сохранить файл в рабочую директорию проекта.
```

**Line 352** - Pattern: `Ошибка`
```python
error_block = f"[Ошибка обработки файла {processed_file.filename}: {processed_file.error}]"
```

**Line 441** - Pattern: `Ошибка`
```python
file_blocks.append(f"📎 **Файл {i}: {pf.filename}** - Ошибка: {pf.error}")
```


### presentation\handlers\messages.py (4 occurrences)

**Line 387** - Pattern: `Ошибка`
```python
await message.answer(f"Ошибка скачивания: {e}")
```

**Line 396** - Pattern: `Ошибка`
```python
await message.answer(f"Ошибка обработки: {processed.error}")
```

**Line 1571** - Pattern: `Сервис`
```python
await message.answer("Сервисы не инициализированы")
```

**Line 1614** - Pattern: `Ошибка`
```python
await message.answer(f"Ошибка: {e}")
```


### application\services\account_service.py (3 occurrences)

**Line 522** - Pattern: `Ошибка`
```python
return False, f"❌ Ошибка API: {response.status_code}\n{error_text}"
```

**Line 530** - Pattern: `Ошибка`
```python
return False, f"❌ Ошибка проверки: {str(e)}"
```

**Line 798** - Pattern: `Ошибка`
```python
return False, f"❌ Ошибка удаления: {str(e)}"
```


### application\services\proxy_service.py (3 occurrences)

**Line 200** - Pattern: `Ошибка`
```python
return False, f"Ошибка HTTP {response.status}"
```

**Line 203** - Pattern: `Ошибка`
```python
return False, f"Ошибка подключения к прокси: {str(e)}"
```

**Line 205** - Pattern: `Ошибка`
```python
return False, f"Ошибка сети: {str(e)}"
```


### presentation\handlers\callbacks\legacy.py (3 occurrences)

**Line 143** - Pattern: `Ошибка`
```python
await callback.message.edit_text(f"❌ Ошибка: {str(e)}", parse_mode=None)
```

**Line 159** - Pattern: `Ошибка`
```python
await callback.message.edit_text(f"❌ Ошибка: {str(e)}")
```

**Line 224** - Pattern: `Ошибка`
```python
await callback.answer(f"❌ Ошибка: {e}")
```


### presentation\handlers\proxy_handlers.py (2 occurrences)

**Line 363** - Pattern: `Ошибка`
```python
f"❌ Ошибка настройки прокси:\n{str(e)}"
```

**Line 421** - Pattern: `Настройки`
```python
await callback.message.edit_text("✅ Настройки сохранены")
```


### presentation\handlers\message\file_handler.py (2 occurrences)

**Line 104** - Pattern: `Ошибка`
```python
await message.answer(f"Ошибка скачивания: {e}")
```

**Line 113** - Pattern: `Ошибка`
```python
await message.answer(f"Ошибка обработки: {processed.error}")
```


### presentation\handlers\message\text_handler.py (2 occurrences)

**Line 617** - Pattern: `Сервис`
```python
await message.answer("Сервисы не инициализированы")
```

**Line 660** - Pattern: `Ошибка`
```python
await message.answer(f"Ошибка: {e}")
```


### domain\validators\input_validator.py (1 occurrences)

**Line 265** - Pattern: `Пользователь`
```python
user_input: Пользовательский ввод
```


### infrastructure\claude_api\usage_service.py (1 occurrences)

**Line 196** - Pattern: `Ошибка`
```python
return f"❌ <b>Ошибка:</b> {limits.error}"
```


### presentation\handlers\streaming_ui.py (1 occurrences)

**Line 258** - Pattern: `Готово`
```python
6. Completion status (✅ Готово) - AT THE VERY BOTTOM
```
