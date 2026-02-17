#!/bin/bash
# Bot Monitor Script

BOT_PID=9172
LOG_FILE="logs/bot.log"

check_bot() {
    if ps -p $BOT_PID > /dev/null 2>&1; then
        echo "✅ Bot is running (PID: $BOT_PID)"
        echo "📊 Recent activity:"
        tail -10 "$LOG_FILE"
        return 0
    else
        echo "❌ Bot is NOT running"
        echo "📝 Last logs:"
        tail -20 "$LOG_FILE"
        return 1
    fi
}

restart_bot() {
    echo "🔄 Restarting bot..."
    pkill -f "python main.py" 2>/dev/null
    sleep 1
    python main.py > "$LOG_FILE" 2>&1 &
    NEW_PID=$!
    echo "✅ Bot restarted (PID: $NEW_PID)"
    echo "Update BOT_PID in this script to: $NEW_PID"
}

case "${1:-status}" in
    status)
        check_bot
        ;;
    logs)
        tail -f "$LOG_FILE"
        ;;
    restart)
        restart_bot
        ;;
    *)
        echo "Usage: $0 {status|logs|restart}"
        ;;
esac
