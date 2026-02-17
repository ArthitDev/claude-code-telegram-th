<p align="center">
  <img src="https://img.shields.io/badge/Claude-Code-blueviolet?style=for-the-badge&logo=anthropic" alt="Claude Code"/>
  <img src="https://img.shields.io/badge/Telegram-Bot-blue?style=for-the-badge&logo=telegram" alt="Telegram"/>
</p>

<h1 align="center">📱 Claude Code Telegram</h1>

<p align="center">
  <b>Control Claude Code AI directly from Telegram — code, review, and deploy from anywhere</b>
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-one-command-deploy">Deploy</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-configuration">Configuration</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white" alt="Docker"/>
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License"/>
  <img src="https://img.shields.io/badge/Architecture-DDD-orange" alt="DDD"/>
  <img src="https://img.shields.io/badge/Tests-143+-success" alt="Tests"/>
</p>

---

## 🎯 What is This?

**Claude Code Telegram** transforms your Telegram into a powerful AI coding assistant. It's a bridge between [Claude Code](https://github.com/anthropics/claude-code) (Anthropic's official CLI for Claude) and Telegram, allowing you to:

- 💻 **Write code** using natural language from your phone
- 🔍 **Review and debug** code on the go
- 📁 **Manage projects** across multiple repositories
- ✅ **Approve AI actions** with Human-in-the-Loop (HITL) controls
- 🚀 **Deploy changes** without touching your computer

> Think of it as having Claude Code in your pocket, accessible anywhere via Telegram.

---

## ✨ Features

### 🤖 AI-Powered Coding
| Feature | Description |
|---------|-------------|
| 💬 **Natural Language** | Just describe what you want — Claude writes the code |
| 🔄 **Streaming Responses** | See AI responses in real-time as they're generated |
| 📝 **Context Awareness** | Maintains conversation history per project |
| 🎯 **Multi-Model Support** | Works with Claude Sonnet, Opus, and Haiku |

### 🛡️ Human-in-the-Loop (HITL)
| Feature | Description |
|---------|-------------|
| ✅ **Tool Approval** | Approve or deny file changes, commands before execution |
| ⚡ **YOLO Mode** | Auto-approve all actions when you trust the AI |
| 📋 **Plan Review** | Review implementation plans before Claude executes them |
| 🔐 **Secure by Default** | Nothing happens without your explicit consent |

### 📁 Project Management
| Feature | Description |
|---------|-------------|
| 🗂️ **Multi-Project** | Switch between different codebases seamlessly |
| 🔍 **File Browser** | Navigate and select projects via Telegram UI |
| 💾 **Persistent Context** | Each project maintains its own conversation history |
| 📤 **File Uploads** | Send files directly to your project via Telegram |

### 🔌 Extensibility
| Feature | Description |
|---------|-------------|
| 🧩 **Official Plugins** | Supports Claude Code plugins (commit, review, etc.) |
| 📡 **MCP Integration** | Telegram MCP server for Claude-initiated messages |
| 🐳 **Docker Management** | Control containers on your server |
| 📊 **System Monitoring** | CPU, memory, disk metrics at a glance |

---

## 🚀 Quick Start

### Prerequisites

- 🐳 Docker & Docker Compose installed
- 🤖 Telegram bot token from [@BotFather](https://t.me/BotFather)
- 🔑 Claude Code credentials (see below)
- 🆔 Your Telegram user ID (get it from [@userinfobot](https://t.me/userinfobot))

### 🔐 Claude Code Authentication

Claude Code supports two authentication methods:

#### Option A: Claude Account (Recommended)

Uses your claude.ai subscription. **No API costs** — uses your existing Claude Pro/Team plan.

1. Install Claude Code CLI locally:
   ```bash
   npm install -g @anthropic-ai/claude-code
   ```

2. Run and authenticate via browser:
   ```bash
   claude
   # Opens browser for OAuth login to claude.ai
   ```

3. Copy the credentials file to your project:
   ```bash
   cp ~/.config/claude/config.json ./claude_config.json
   ```

4. Mount it in `docker-compose.yml`:
   ```yaml
   volumes:
     - ./claude_config.json:/root/.config/claude/config.json:ro
   ```

#### Option B: API Key

Uses Anthropic API directly. **Pay-per-use** pricing.

```ini
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
```

Get your API key from [console.anthropic.com](https://console.anthropic.com)

#### Option C: ZhipuAI (China)

Claude-compatible API with no regional restrictions.

```ini
ANTHROPIC_BASE_URL=https://open.bigmodel.cn/api/anthropic
ANTHROPIC_AUTH_TOKEN=your_zhipuai_token
```

Get your token from [open.bigmodel.cn](https://open.bigmodel.cn)

---

## ⚡ One-Command Deploy

### Option 1: Interactive Deploy Script (Recommended)

```bash
# Download and run the interactive deploy script
git clone https://github.com/Angusstone7/claude-code-telegram.git && \
cd claude-code-telegram && \
chmod +x deploy.sh && \
./deploy.sh
```

The script will:
- ✅ Check Docker installation
- ✅ Prompt for your credentials interactively
- ✅ Create the `.env` file automatically
- ✅ Build and start the container
- ✅ Show you next steps

### Option 2: Quick Deploy (Manual Config)

```bash
# Clone, configure, and run — all in one command!
git clone https://github.com/Angusstone7/claude-code-telegram.git && \
cd claude-code-telegram && \
cp .env.example .env && \
echo "Now edit .env with your credentials, then run: docker-compose up -d --build"
```

### Option 3: Full One-Liner (if you know your credentials)

```bash
git clone https://github.com/Angusstone7/claude-code-telegram.git && cd claude-code-telegram && \
cat > .env << 'EOF'
TELEGRAM_TOKEN=your_bot_token_here
ANTHROPIC_API_KEY=sk-ant-your-key-here
ALLOWED_USER_ID=your_telegram_id_here
EOF
docker-compose up -d --build
```

Just replace:
- `your_bot_token_here` → Your Telegram bot token
- `sk-ant-your-key-here` → Your Anthropic API key
- `your_telegram_id_here` → Your Telegram user ID

### Option 4: Step-by-Step Deploy

<details>
<summary>📖 Click to expand detailed instructions</summary>

#### 1️⃣ Clone the Repository

```bash
git clone https://github.com/Angusstone7/claude-code-telegram.git
cd claude-code-telegram
```

#### 2️⃣ Create Configuration

```bash
cp .env.example .env
```

#### 3️⃣ Edit `.env` File

```ini
# Required settings
TELEGRAM_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
ALLOWED_USER_ID=123456789

# Optional: Multiple users (comma-separated)
# ALLOWED_USER_ID=123456789,987654321

# Optional: Use Claude Sonnet 4 (default) or other models
# ANTHROPIC_MODEL=claude-sonnet-4-20250514
```

#### 4️⃣ Launch with Docker

```bash
docker-compose up -d --build
```

#### 5️⃣ Check Logs

```bash
docker-compose logs -f claude-bot
```

#### 6️⃣ Open Telegram

Find your bot and send `/start` 🎉

</details>

---

## 📱 Usage

### Basic Commands

| Command | Description |
|---------|-------------|
| `/start` | 📱 Open main menu |
| `/yolo` | ⚡ Toggle auto-approve mode |
| `/cancel` | 🛑 Cancel current AI task |

### Main Menu

After `/start`, you'll see an inline keyboard with options:

```
┌─────────────────────────────────┐
│  💬 Chat with Claude Code       │  ← Start coding session
├─────────────────────────────────┤
│  📁 Projects                    │  ← Browse & switch projects
├─────────────────────────────────┤
│  👤 Account                     │  ← Manage API credentials
├─────────────────────────────────┤
│  ⚙️ Settings                    │  ← Configure bot behavior
└─────────────────────────────────┘
```

### Workflow Example

```
You: Create a Python function that validates email addresses

Claude: I'll create an email validation function for you.

📄 Creating file: utils/validators.py
┌────────────────────────────────────┐
│ [✅ Approve] [❌ Deny] [👁️ View]  │
└────────────────────────────────────┘

You: [Clicks ✅ Approve]

Claude: ✅ Created utils/validators.py with email validation function.
        The function uses regex pattern matching and handles edge cases...
```

### HITL (Human-in-the-Loop) Controls

When Claude wants to perform an action, you'll see approval buttons:

| Button | Action |
|--------|--------|
| ✅ **Approve** | Allow Claude to proceed |
| ❌ **Deny** | Block the action |
| 👁️ **View** | See what Claude wants to do |
| ⚡ **YOLO** | Approve all future actions |

---

## 🏗️ Architecture

This project follows **Domain-Driven Design (DDD)** with clean architecture:

```
claude-code-telegram/
├── 🎯 domain/                    # Core business logic
│   ├── entities/                 # User, Session, Project, Message
│   ├── value_objects/            # UserId, Role, AIProviderConfig
│   ├── repositories/             # Repository interfaces
│   └── services/                 # Domain service contracts
│
├── 📦 application/               # Use cases & orchestration
│   └── services/
│       ├── bot_service.py        # Main orchestration
│       ├── project_service.py    # Project management
│       ├── context_service.py    # Conversation context
│       └── account_service.py    # Auth mode switching
│
├── 🔧 infrastructure/            # External integrations
│   ├── claude_code/
│   │   ├── sdk_service.py        # Claude SDK (preferred)
│   │   └── proxy_service.py      # CLI fallback
│   ├── persistence/              # SQLite repositories
│   └── messaging/                # AI service adapters
│
├── 🎨 presentation/              # Telegram interface
│   ├── handlers/                 # Message, callback, command handlers
│   ├── keyboards/                # Inline keyboard builders
│   └── middleware/               # Auth middleware
│
├── 🔌 telegram-mcp/              # MCP server (TypeScript)
│   └── src/index.ts              # Telegram tools for Claude
│
└── 🧪 tests/                     # Test suite (143+ tests)
```

### Backend Modes

| Mode | Description | When Used |
|------|-------------|-----------|
| **SDK** | Direct Python integration via `claude-agent-sdk` | Primary (preferred) |
| **CLI** | Subprocess calls to `claude` CLI | Fallback |

---

## ⚙️ Configuration

### Environment Variables

<details>
<summary>🔧 Click to see all configuration options</summary>

#### Required

| Variable | Description |
|----------|-------------|
| `TELEGRAM_TOKEN` | Bot token from @BotFather |
| `ANTHROPIC_API_KEY` | API key (Anthropic or ZhipuAI) |
| `ALLOWED_USER_ID` | Telegram user ID(s), comma-separated |

#### AI Provider

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Default model |
| `ANTHROPIC_BASE_URL` | — | Custom API endpoint |

#### Claude Code

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_WORKING_DIR` | `/root/projects` | Default working directory |
| `CLAUDE_MAX_TURNS` | `50` | Max conversation turns |
| `CLAUDE_TIMEOUT` | `600` | Command timeout (seconds) |
| `CLAUDE_PERMISSION_MODE` | `default` | `default`, `auto`, or `never` |

#### Optional Features

| Variable | Default | Description |
|----------|---------|-------------|
| `SSH_HOST` | `host.docker.internal` | Host for SSH commands |
| `SSH_PORT` | `22` | SSH port |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `DEBUG` | `false` | Enable debug mode |

</details>

---

## 🐳 Docker Details

### Volumes

| Host Path | Container Path | Purpose |
|-----------|----------------|---------|
| `./data` | `/app/data` | SQLite database |
| `./logs` | `/app/logs` | Application logs |
| `./projects` | `/root/projects` | Your code projects |
| `./claude_sessions` | `/root/.claude` | Claude Code sessions |
| `./claude_config.json` | `/root/.config/claude/config.json` | Claude Account credentials (optional) |

### Useful Commands

```bash
# Start the bot
docker-compose up -d --build

# View logs
docker-compose logs -f claude-bot

# Restart
docker-compose restart

# Stop
docker-compose down

# Update to latest version
git pull && docker-compose up -d --build
```

---

## 🔌 MCP Integration

The bot includes a Telegram MCP server that allows Claude to proactively send messages:

| Tool | Description |
|------|-------------|
| `send_message` | Send text notifications to Telegram |
| `send_file` | Send files with optional captions |
| `send_plan` | Create and send plan documents |

To rebuild after changes:

```bash
cd telegram-mcp && npm install && npm run build
```

---

## 🧪 Development

### Local Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run locally
python main.py
```

### Running Tests

```bash
# All tests
pytest tests/

# With coverage
pytest tests/ --cov=. --cov-report=html

# Specific test file
pytest tests/unit/domain/test_ai_provider_config.py -v
```

### Code Quality

```bash
# Format code
black application/ domain/ infrastructure/ presentation/ shared/

# Type checking
mypy application/ domain/ infrastructure/ presentation/ shared/
```

---

## 📊 Project Stats

| Metric | Value |
|--------|-------|
| 📝 Python LOC | ~28,100 |
| 📄 Python Files | 112 |
| 🧪 Unit Tests | 143+ |
| 🎛️ Handlers LOC | ~9,000 |
| 🔌 MCP Server LOC | ~10,000 |

---

## 🛡️ Security

### User Authorization (Whitelist)

Access to the bot is controlled via `ALLOWED_USER_ID` environment variable:

```ini
# Single user (this user becomes admin)
ALLOWED_USER_ID=123456789

# Multiple users (first user is admin, others are regular users)
ALLOWED_USER_ID=123456789,987654321,555555555
```

| Feature | Description |
|---------|-------------|
| 🔐 **Whitelist** | Only users in `ALLOWED_USER_ID` can access the bot |
| 👑 **Auto Admin** | First user in the list automatically gets admin role |
| 🚫 **Access Denied** | Unauthorized users see their Telegram ID (for requesting access) |
| ⚠️ **Open Mode** | If `ALLOWED_USER_ID` is empty, bot is open to everyone (warning logged) |

### Other Security Features

- ✅ **HITL Controls** — Every AI action requires explicit approval
- ✅ **No Credentials in Code** — All secrets via environment variables
- ✅ **SSH Key Auth** — Secure server access (optional feature)
- ✅ **Role-Based Access** — Admin, DevOps, User, ReadOnly roles

---

## 🐛 Troubleshooting

<details>
<summary>Bot doesn't respond</summary>

1. Check logs: `docker-compose logs -f claude-bot`
2. Verify `TELEGRAM_TOKEN` is correct
3. Ensure your user ID is in `ALLOWED_USER_ID`

</details>

<details>
<summary>Claude Code not working</summary>

1. Check if API key is valid
2. Verify `ANTHROPIC_API_KEY` is set
3. Look for SDK/CLI status in startup logs

</details>

<details>
<summary>Permission denied errors</summary>

```bash
chmod -R 755 ./data ./logs ./projects
```

</details>

---

## 🤝 Contributing

Contributions are welcome! Please:

1. 🍴 Fork the repository
2. 🌿 Create a feature branch (`git checkout -b feature/amazing-feature`)
3. 💾 Commit your changes (`git commit -m 'Add amazing feature'`)
4. 📤 Push to the branch (`git push origin feature/amazing-feature`)
5. 🔃 Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 👏 Credits

This project is a fork of [claude-code-telegram](https://github.com/Angusstone7/claude-code-telegram) by [Angusstone7](https://github.com/Angusstone7).
Huge thanks to the original author for the amazing work!

---

## 🙏 Acknowledgments

Built with these amazing tools:

- [Aiogram](https://aiogram.dev/) — Modern Telegram bot framework
- [Claude Code](https://github.com/anthropics/claude-code) — Anthropic's AI coding CLI
- [Anthropic SDK](https://github.com/anthropics/anthropic-sdk-python) — Claude API client

---

<p align="center">
  <b>Made with ❤️ for developers who code on the go</b>
</p>

<p align="center">
  <a href="https://github.com/Angusstone7/claude-code-telegram/issues">Report Bug</a> •
  <a href="https://github.com/Angusstone7/claude-code-telegram/issues">Request Feature</a>
</p>
