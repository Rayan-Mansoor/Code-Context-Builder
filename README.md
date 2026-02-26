# Code Context Builder

A sleek desktop GUI tool that merges multiple code files into a single, clean text block — ready to paste into LLM chats like ChatGPT, Claude, or Gemini.

![Code Context Builder Screenshot](screenshots/app.png)

## Why?

When working with LLMs on coding tasks, you often need to share multiple files as context. Manually copying and pasting each file is tedious and error-prone. Code Context Builder lets you select files, arrange them, and generate a single formatted output in seconds.

## Features

- **Project Folders** — Save and switch between frequently used project directories
- **Multi-file Selection** — Add files from anywhere, reorder with drag controls
- **Smart Formatting** — Auto-detects 60+ languages and wraps content in appropriate markdown code blocks
- **Two Divider Modes** — Fenced code blocks (``` syntax) or custom line dividers
- **Live Preview** — Editable output panel lets you tweak before copying
- **One-Click Copy** — Send merged content straight to your clipboard
- **Export to .txt** — Save the output as a text file
- **Persistent Config** — Remembers your project folders, settings, and window size between sessions
- **Dark UI** — Modern dark theme designed for comfortable use

## Supported Languages

Python, JavaScript, TypeScript, JSX/TSX, HTML, CSS, SCSS, JSON, YAML, TOML, Java, Kotlin, Swift, C/C++, C#, Go, Rust, Ruby, PHP, Bash, SQL, Dart, Elixir, Haskell, Vue, Svelte, GraphQL, Protobuf, HCL, Dockerfile, and many more.

## Installation

### Prerequisites

- Python 3.8+
- Tkinter (included with most Python installations)

### Setup

```bash
git clone https://github.com/YOUR_USERNAME/code-context-builder.git
cd code-context-builder
python main.py
```

No external dependencies required — runs on the Python standard library.

## Usage

1. **Add a Project Folder** — Click `+ Add` under Project Folders and select your project root
2. **Select Files** — Click `+ Add Files` to pick the code files you want to include
3. **Arrange Order** — Use the ▲/▼ buttons to reorder files as needed
4. **Configure Output** — Toggle filename headers, choose divider mode, customize the divider string
5. **Copy or Save** — Hit `Copy` to clipboard or `Download .txt` to save

### Keyboard Shortcuts

| Shortcut       | Action             |
| -------------- | ------------------ |
| `Ctrl+R`       | Regenerate preview |
| `Ctrl+S`       | Save as .txt       |
| `Ctrl+Shift+C` | Copy to clipboard  |

## Configuration

Settings are saved automatically to `config.json` in the app directory. This includes:

- Saved project folders
- Divider mode and custom divider string
- Filename header toggle
- Last used directory
- Window size and position

## License

MIT