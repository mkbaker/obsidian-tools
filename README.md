# Obsidian Tools

A collection of automation tools for managing Obsidian vaults, starting with a weekly notes archiver.

## Features

- **Weekly Notes Archiver**: Automatically archive daily notes and their screenshots to weekly folders
- **Flexible Week Selection**: Archive current week, previous week, specific dates, or N weeks ago
- **Screenshot Detection**: Automatically finds and moves embedded images from notes
- **Dry Run Mode**: Preview what will be archived without moving files
- **CLI Integration**: Convenient shell aliases and tab completion

## Prerequisites

- Python 3.6+
- Zsh shell (for shell integration)
- Obsidian vault with the expected folder structure

## Required Folder Structure

Your Obsidian vault must be organized as follows:

```
obsidian_vault/
├── Daily notes/
│   ├── 2025-05-19
│   ├── 2025-05-20.md
│   └── ...
└── 4 ARCHIVE/
    └── Weekly Notes/
        ├── Week of 2025-05-12/
        ├── Week of 2025-05-19/
        └── ...
```

**Important Notes:**
- Daily notes can have `.md` extension or no extension
- Daily notes must be named with date format: `YYYY-MM-DD`
- Archive folder structure will be created automatically if it doesn't exist
- Screenshots can be stored anywhere in the vault (script will find them)

## Installation

1. **Clone or download the tools to your preferred location:**
   ```bash
   mkdir -p ~/your/path/to/obsidian_tools
   cd ~/your/path/to/obsidian_tools
   ```

2. **Place the files in the directory:**
   ```
   obsidian_tools/
   ├── weekly_notes_archiver.py
   ├── shell_functions.sh
   └── README.md
   ```

3. **Make the Python script executable:**
   ```bash
   chmod +x weekly_notes_archiver.py
   ```

4. **Update the vault path in `weekly_notes_archiver.py` if needed:**
   - Default path: `Desktop/obsidian_vault`
   - Or use `--vault-path` flag when running

## Shell Integration Setup

1. **Set the OBSIDIAN_TOOLS_PATH environment variable in your `~/.zshrc` to the directory where you placed the tools:**
   ```bash
   export OBSIDIAN_TOOLS_PATH="/full/path/to/your/obsidian_tools"
   ```

2. **Add this line to your `~/.zshrc` to load the shell functions:**
   ```bash
   # Load Obsidian tools functions
   source "$OBSIDIAN_TOOLS_PATH/shell_functions.sh"
   ```

3. **Reload your shell:**
   ```bash
   source ~/.zshrc
   ```

## Usage

### Direct Python Script

```bash
# Archive previous week (default)
python3 weekly_notes_archiver.py

# Archive current week
python3 weekly_notes_archiver.py --week current

# Dry run preview
python3 weekly_notes_archiver.py --dry-run

# Custom vault path
python3 weekly_notes_archiver.py --vault-path "path/to/vault"

# See all options
python3 weekly_notes_archiver.py --help
```

### Shell Aliases (After Integration Setup)

```bash
# Main command
archive-notes              # Archive previous week
archive-notes current      # Archive current week
archive-notes dry          # Preview previous week
archive-notes current-dry  # Preview current week
archive-notes 2            # Archive 2 weeks ago
archive-notes 2025-05-20   # Archive week containing date
archive-notes help         # Show help

# Short aliases
an      # archive-notes (previous week)
anc     # archive-notes current
anp     # archive-notes previous
and     # archive-notes dry
ancd    # archive-notes current-dry
anpd    # archive-notes previous-dry
```

## Week Selection Options

The `--week` parameter accepts:

- **Keywords**: `current`, `this`, `previous`, `last`
- **Numbers**: `0` (current), `1` (previous), `2` (2 weeks ago), etc.
- **Dates**: `2025-05-20` (week containing this date)
- **Dry run variants**: Add `-dry` to any option (`current-dry`, `2-dry`, etc.)

## Common Use Cases

### Monday Morning Cleanup
```bash
archive-notes  # Archives last week's notes
```

### Friday End-of-Week Cleanup
```bash
archive-notes current  # Archives current week's notes
```

### Preview Before Archiving
```bash
archive-notes current-dry  # See what would be archived
```

## Troubleshooting

### Vault Not Found
- Check the vault path in the script or use `--vault-path`
- Ensure the path is relative to your home directory

### Daily Notes Not Found
- Verify daily notes are named `YYYY-MM-DD` (with or without `.md`)
- Check they're in the `Daily notes/` folder

### Screenshots Not Moving
- Screenshots must be referenced in notes as `![[image.png]]`
- Script searches common locations: vault root, `attachments/`, `assets/`, `Daily notes/`

### Shell Functions Not Working
- Ensure you've sourced the functions: `source ~/.zshrc`
- Check the script path in `shell_functions.sh` is correct
- Verify you're using Zsh (not Bash)

## Extending the Tools

To add new obsidian tools:

1. Create new Python scripts in the `obsidian_tools/` directory
2. Add corresponding functions to `shell_functions.sh`
3. Update this README with new features

## File Structure Reference

```
/your/path/to/obsidian_tools/
├── README.md                    # This file
├── weekly_notes_archiver.py     # Main Python script
└── shell_functions.sh           # Zsh functions and aliases
```

## License

MIT License - Feel free to modify and distribute.
