# Obsidian Tools

A collection of automation tools for managing Obsidian vaults, including weekly notes archiving and todo migration.

## Features

### Weekly Notes Archiver
- **Flexible Week Selection**: Archive current week, previous week, specific dates, or N weeks ago
- **Screenshot Detection**: Automatically finds and moves embedded images from notes
- **Dry Run Mode**: Preview what will be archived without moving files

### Todo Migrator
- **Automatic Migration**: Migrate unfinished todos from previous daily notes to today's note
- **Smart Hierarchical Handling**: Preserves indentation and sub-todo relationships
- **Date Tracking**: Adds origin date tags to migrated todos (e.g., "(from 2025-08-01)")
- **Group Migration**: Migrates entire todo groups if any item is incomplete
- **Note Creation**: Automatically creates today's daily note if it doesn't exist

### CLI Integration
- **Shell Aliases**: Convenient short commands for common operations
- **Tab Completion**: Auto-completion for command options in Zsh
- **Dry Run Support**: Preview operations before executing

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
- Daily notes should have a `## To do` section for todo migration to work
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
   ├── todo_migrator.py
   ├── shell_functions.sh
   └── README.md
   ```

3. **Make the Python scripts executable:**
   ```bash
   chmod +x weekly_notes_archiver.py
   chmod +x todo_migrator.py
   ```

4. **Update the vault path in scripts if needed:**
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

### Weekly Notes Archiver

#### Direct Python Script
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

#### Shell Aliases (After Integration Setup)
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

### Todo Migrator

#### Direct Python Script
```bash
# Migrate yesterday's todos to today (default)
python3 todo_migrator.py

# Preview migration without making changes
python3 todo_migrator.py --dry-run

# Migrate from specific date to today
python3 todo_migrator.py --from 2025-08-01

# Migrate between specific dates
python3 todo_migrator.py --from 2025-08-01 --to 2025-08-02

# Custom vault path
python3 todo_migrator.py --vault-path "path/to/vault"

# See all options
python3 todo_migrator.py --help
```

#### Shell Aliases (After Integration Setup)
```bash
# Main command
migrate-todos              # Migrate yesterday's todos to today
migrate-todos dry          # Preview migration
migrate-todos from 2025-08-01  # Migrate from specific date
migrate-todos help         # Show help

# Short aliases
mt      # migrate-todos (yesterday -> today)
mtd     # migrate-todos dry
```

## Week Selection Options

The `--week` parameter accepts:

- **Keywords**: `current`, `this`, `previous`, `last`
- **Numbers**: `0` (current), `1` (previous), `2` (2 weeks ago), etc.
- **Dates**: `2025-05-20` (week containing this date)
- **Dry run variants**: Add `-dry` to any option (`current-dry`, `2-dry`, etc.)

## Common Use Cases

### Daily Workflow - Morning Todo Migration
```bash
migrate-todos              # Migrate yesterday's unfinished todos
mtd                        # Preview what would be migrated
```

### Daily Workflow - Monday Morning Cleanup
```bash
migrate-todos              # Migrate weekend todos
archive-notes              # Archive last week's notes
```

### Weekly Workflow - Friday End-of-Week
```bash
archive-notes current      # Archive current week's notes
archive-notes current-dry  # Preview before archiving
```

### Todo Management Examples
```bash
# Basic migration workflow
migrate-todos dry          # See what would be migrated
migrate-todos              # Actually migrate the todos

# Migrate from specific dates
migrate-todos from 2025-08-01  # Migrate todos from Aug 1 to today
```

## Todo Migration Details

### How It Works
1. **Scans source note** for `## To do` section
2. **Identifies incomplete todos** (unchecked items: `- [ ] task`)
3. **Groups hierarchical todos** (preserves parent-child relationships)
4. **Migrates entire groups** if any item in the group is incomplete
5. **Adds date tracking** to migrated items: `- [ ] task (from 2025-08-01)`
6. **Creates target note** if it doesn't exist
7. **Inserts todos** into the target note's `## To do` section

### Todo Format Requirements
Your daily notes should have todos formatted like this:

```markdown
## To do

- [ ] Main task
  - [ ] Sub-task 1
  - [x] Sub-task 2 (completed)
- [x] Completed task
- [ ] Another main task
```

## Troubleshooting

### Weekly Notes Archiver
- **Vault Not Found**: Check the vault path in the script or use `--vault-path`
- **Daily Notes Not Found**: Verify daily notes are named `YYYY-MM-DD` (with or without `.md`)
- **Screenshots Not Moving**: Screenshots must be referenced in notes as `![[image.png]]`

### Todo Migrator
- **No Todos Found**: Ensure your daily notes have a `## To do` section
- **Todos Not Migrating**: Check that todos are formatted as `- [ ] task` or `- [x] task`
- **Target Note Issues**: Script will create today's note if it doesn't exist
- **Date Format Issues**: Source and target notes must be named `YYYY-MM-DD`

### Shell Functions
- **Commands Not Found**: Ensure you've sourced the functions: `source ~/.zshrc`
- **Wrong Script Path**: Check the script paths in `shell_functions.sh` are correct
- **Not Using Zsh**: These functions are designed for Zsh, not Bash

## Extending the Tools

To add new obsidian tools:

1. Create new Python scripts in the `obsidian_tools/` directory
2. Add corresponding functions to `shell_functions.sh`
3. Update this README with new features

## File Structure Reference

```
/your/path/to/obsidian_tools/
├── README.md                    # This file
├── weekly_notes_archiver.py     # Weekly notes archiving tool
├── todo_migrator.py             # Todo migration tool
└── shell_functions.sh           # Zsh functions and aliases
```

## License

MIT License - Feel free to modify and distribute.
