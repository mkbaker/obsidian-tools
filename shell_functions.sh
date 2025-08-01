#!/bin/bash
# Obsidian Tools Shell Functions
# Source this file from your .zshrc

# Weekly notes archiving function
archive-notes() {
    local script_path="/Users/kellen.baker/Code/obsidian_tools/weekly_notes_archiver.py"

    case "$1" in
        "")
            # Default: archive previous week
            python3 "$script_path"
            ;;
        "current"|"this")
            python3 "$script_path" --week current
            ;;
        "previous"|"last")
            python3 "$script_path" --week previous
            ;;
        "dry")
            python3 "$script_path" --dry-run
            ;;
        "current-dry"|"this-dry")
            python3 "$script_path" --week current --dry-run
            ;;
        "previous-dry"|"last-dry")
            python3 "$script_path" --week previous --dry-run
            ;;
        [0-9])
            python3 "$script_path" --week "$1"
            ;;
        [0-9]-dry)
            local week_num="${1%-dry}"
            python3 "$script_path" --week "$week_num" --dry-run
            ;;
        [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9])
            python3 "$script_path" --week "$1"
            ;;
        [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-dry)
            local date="${1%-dry}"
            python3 "$script_path" --week "$date" --dry-run
            ;;
        "help"|"-h"|"--help")
            echo "📝 Weekly Notes Archiver"
            echo "Usage: archive-notes [OPTION]"
            echo ""
            echo "Options:"
            echo "  (none)             Archive previous week (default)"
            echo "  current, this      Archive current week"
            echo "  previous, last     Archive previous week"
            echo "  dry                Dry run for previous week"
            echo "  current-dry        Dry run for current week"
            echo "  previous-dry       Dry run for previous week"
            echo "  NUMBER             Archive N weeks ago (0=current, 1=previous, etc.)"
            echo "  NUMBER-dry         Dry run for N weeks ago"
            echo "  YYYY-MM-DD         Archive week containing this date"
            echo "  YYYY-MM-DD-dry     Dry run for week containing this date"
            echo "  help               Show this help message"
            echo ""
            echo "Examples:"
            echo "  archive-notes              # Archive previous week"
            echo "  archive-notes current      # Archive current week"
            echo "  archive-notes dry          # Preview previous week"
            echo "  archive-notes current-dry  # Preview current week"
            echo "  archive-notes 2            # Archive 2 weeks ago"
            echo "  archive-notes 2-dry        # Preview 2 weeks ago"
            echo "  archive-notes 2025-05-20   # Archive week containing May 20"
            echo ""
            echo "Short aliases: an, anc, anp, and"
            ;;
        *)
            echo "❌ Unknown option: $1"
            echo "Run 'archive-notes help' for usage information."
            return 1
            ;;
    esac
}

# Short aliases for common operations
alias an='archive-notes'
alias anc='archive-notes current'
alias anp='archive-notes previous'
alias and='archive-notes dry'
alias ancd='archive-notes current-dry'
alias anpd='archive-notes previous-dry'

# Auto-completion for archive-notes
_archive_notes_completion() {
    local -a options
    options=(
        'current:Archive current week'
        'this:Archive current week'
        'previous:Archive previous week'
        'last:Archive previous week'
        'dry:Dry run for previous week'
        'current-dry:Dry run for current week'
        'previous-dry:Dry run for previous week'
        'help:Show help message'
        '0:Archive current week'
        '1:Archive previous week'
        '2:Archive 2 weeks ago'
        '3:Archive 3 weeks ago'
    )
    _describe 'archive-notes options' options
}

# Register completion function (only in zsh and if compdef is available)
if [[ -n "$ZSH_VERSION" ]] && command -v compdef >/dev/null 2>&1; then
    compdef _archive_notes_completion archive-notes
fi

# Todo migration function
migrate-todos() {
    local script_path="/Users/kellen.baker/Code/obsidian_tools/todo_migrator.py"

    case "$1" in
        "")
            # Default: migrate yesterday's todos to today
            python3 "$script_path"
            ;;
        "dry")
            python3 "$script_path" --dry-run
            ;;
        "help"|"-h"|"--help")
            echo "📋 Todo Migrator"
            echo "Usage: migrate-todos [OPTION]"
            echo ""
            echo "Options:"
            echo "  (none)         Migrate yesterday's todos to today (default)"
            echo "  dry            Preview migration without making changes"
            echo "  from DATE      Migrate from specific date to today"
            echo "  help           Show this help message"
            echo ""
            echo "Examples:"
            echo "  migrate-todos              # Migrate yesterday -> today"
            echo "  migrate-todos dry          # Preview migration"
            echo "  migrate-todos from 2025-08-01  # Migrate from Aug 1 to today"
            echo ""
            echo "Short aliases: mt, mtd"
            ;;
        "from")
            if [[ -n "$2" ]]; then
                python3 "$script_path" --from "$2"
            else
                echo "❌ Please specify a date: migrate-todos from YYYY-MM-DD"
                return 1
            fi
            ;;
        *)
            echo "❌ Unknown option: $1"
            echo "Run 'migrate-todos help' for usage information."
            return 1
            ;;
    esac
}

# Short aliases for todo migration
alias mt='migrate-todos'
alias mtd='migrate-todos dry'

# Future obsidian tools can be added here...
# obsidian-export() { ... }
# obsidian-backup() { ... }
