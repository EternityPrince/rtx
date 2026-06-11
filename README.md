# RTX - Universal Workspace Parser & Context Gatherer

RTX is a lightweight, high-performance terminal utility designed to scan local workspace directories, extract text contents from various file formats (including source code, word documents, presentations, PDFs, and ebooks), and aggregate them for LLMs, context injection, or code review.

It supports both a visual **TUI** (Textual User Interface) and a standard **CLI** mode.

---

## Features

- **Interactive TUI Mode**:
  - Browse workspace directory structure.
  - View real-time folder metrics (file counts, total lines, characters, and bytes).
  - Preview source code (with syntax highlighting support via `bat` or plain-text fallback).
  - Detect binary formats and display warnings with the option to open the file via the system application.
  - Multi-select files and folders using checkboxes (toggled with the `X` key) for selective parsing.
- **Dual Execution Modes**:
  - **Mode A (Stream Mode)**: Merges all parsed files into a single markdown stream. Output is printed to `stdout`, copied to the clipboard, or saved to a designated output file (`--output`).
  - **Mode B (Mirror Mode)**: Replicates the original workspace directory structure inside a hidden folder `.rtx/` as `.md` files containing the formatted context.
- **Rich File Format Support**:
  - **Source Code / Plain Text**: Wraps contents in markdown codeblocks (auto-detects extension and avoids fence collisions using quadrupled backticks when necessary).
  - **Microsoft Word (.docx)**: Extracts headers, paragraph lists, and converts tables into markdown tables.
  - **Microsoft PowerPoint (.pptx)**: Parses text from slide shapes.
  - **PDF Documents (.pdf)**: Parses text using high-fidelity `marker-pdf` if available, falling back to `PyMuPDF` (fitz) or `pypdf`.
  - **Ebooks (.epub, .fb2)**: Extracts structural chapters and contents.

---

## Installation

This project is packaged with Python dependencies. You can install it using `uv` (recommended) or standard Python package managers.

```bash
# Clone the repository
git clone <repository-url>
cd rtx

# Install dependencies using uv
uv sync
```

---

## Usage

### Interactive TUI Mode

Run the interactive Textual interface:

```bash
uv run rtx --tui
```

#### TUI Keyboard Shortcuts

- `X` - Toggle selection for current file/directory (recurses through subfolders).
- `Enter` - Expand / Collapse directory.
- `M` - Toggle mode (Switch between Mode A: Single File and Mode B: Mirroring).
- `P` / `Ctrl+P` - Start parsing selected files.
- `O` - Open the currently highlighted file in the OS default application.
- `Q` - Quit the application.

---

### Command Line Interface (CLI)

#### Mode A: Stream output to stdout / clipboard
By default, RTX scans the directory, prints parsing summary statistics, and copies the aggregated markdown context to your clipboard:

```bash
uv run rtx .
```

#### Mode A: Write to a specific output file
Save the combined markdown contents to a file:

```bash
uv run rtx . --output output.md
```

#### Mode B: Mirror directory structure
Generate `.md` context files inside `.rtx/` mirroring your scanned project directory:

```bash
uv run rtx . --mirror
```

---

## Development & Testing

Tests are written using `pytest`. You can run the test suite and check code coverage using `uv`:

```bash
uv run pytest
```
