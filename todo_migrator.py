#!/usr/bin/env python3
"""
Todo Migrator for Obsidian Daily Notes
Automatically migrates unfinished to-dos from previous daily notes to today's note.
"""

import os
import re
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import sys

class TodoMigrator:
    def __init__(self, vault_path="Desktop/obsidian_vault"):
        self.vault_path = Path.home() / vault_path
        self.daily_notes_path = self.vault_path / "Daily notes"

    def get_daily_note_path(self, date):
        """Get the path for a daily note on a specific date."""
        date_str = date.strftime("%Y-%m-%d")

        # Try different possible file extensions/formats
        possible_paths = [
            self.daily_notes_path / date_str,
            self.daily_notes_path / f"{date_str}.md",
        ]

        for path in possible_paths:
            if path.exists():
                return path

        # Return the .md version for creation
        return self.daily_notes_path / f"{date_str}.md"

    def parse_todo_section(self, content):
        """Parse the To do section from daily note content."""
        lines = content.split('\n')
        todos = []
        in_todo_section = False
        current_indent = 0

        for i, line in enumerate(lines):
            # Check if we're entering the To do section
            if re.match(r'^##\s+To\s+do\s*$', line, re.IGNORECASE):
                in_todo_section = True
                continue

            # Check if we're leaving the To do section (next ## section)
            if in_todo_section and re.match(r'^##\s+', line):
                break

            if in_todo_section and line.strip():
                # Parse todo items
                todo_match = re.match(r'^(\s*)- \[([ x])\] (.+)$', line)
                if todo_match:
                    indent = len(todo_match.group(1))
                    is_completed = todo_match.group(2).lower() == 'x'
                    text = todo_match.group(3)

                    todos.append({
                        'line_num': i,
                        'indent': indent,
                        'completed': is_completed,
                        'text': text,
                        'original_line': line
                    })

        return todos

    def group_todos_by_hierarchy(self, todos):
        """Group todos into hierarchical structures."""
        groups = []
        current_group = []

        for todo in todos:
            if todo['indent'] == 0:  # Top-level todo
                if current_group:
                    groups.append(current_group)
                current_group = [todo]
            else:  # Sub-todo
                current_group.append(todo)

        if current_group:
            groups.append(current_group)

        return groups

    def should_migrate_group(self, group):
        """Determine if a todo group should be migrated."""
        if not group:
            return False

        # If any item in the group is incomplete, migrate the whole group
        return any(not todo['completed'] for todo in group)

    def format_migrated_todo(self, todo, original_date):
        """Format a todo item for migration with date tracking."""
        # Add original date tracking if not already present
        text = todo['text']
        date_str = original_date.strftime("%Y-%m-%d")

        # Check if it already has a date tag
        if not re.search(r'\(from \d{4}-\d{2}-\d{2}\)', text):
            text = f"{text} (from {date_str})"

        # Preserve original completion status
        checkbox = "[x]" if todo['completed'] else "[ ]"
        indent = " " * todo['indent']

        return f"{indent}- {checkbox} {text}"

    def extract_todos_from_note(self, note_path):
        """Extract todos from a daily note file."""
        if not note_path.exists():
            return []

        try:
            with open(note_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (UnicodeDecodeError, IOError) as e:
            print(f"Warning: Could not read {note_path}: {e}")
            return []

        todos = self.parse_todo_section(content)
        groups = self.group_todos_by_hierarchy(todos)

        # Filter groups that need migration
        incomplete_groups = [group for group in groups if self.should_migrate_group(group)]

        return incomplete_groups

    def create_today_note_if_missing(self, today_path):
        """Create today's daily note if it doesn't exist."""
        if today_path.exists():
            return True

        # Create the daily notes directory if it doesn't exist
        self.daily_notes_path.mkdir(parents=True, exist_ok=True)

        # Basic template for new daily note
        template = f"""# {datetime.now().strftime('%Y-%m-%d')}

## To do


## Notes

"""

        try:
            with open(today_path, 'w', encoding='utf-8') as f:
                f.write(template)
            print(f"📄 Created new daily note: {today_path.name}")
            return True
        except IOError as e:
            print(f"Error creating daily note: {e}")
            return False

    def add_todos_to_note(self, note_path, todo_groups, original_date):
        """Add migrated todos to a daily note."""
        try:
            with open(note_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (UnicodeDecodeError, IOError) as e:
            print(f"Error reading {note_path}: {e}")
            return False

        lines = content.split('\n')

        # Find the To do section
        todo_section_line = None
        for i, line in enumerate(lines):
            if re.match(r'^##\s+To\s+do\s*$', line, re.IGNORECASE):
                todo_section_line = i
                break

        if todo_section_line is None:
            print(f"Warning: No 'To do' section found in {note_path.name}")
            return False

        # Find where to insert (after the ## To do line and any existing todos)
        insert_line = todo_section_line + 1

        # Skip empty lines after the section header
        while insert_line < len(lines) and not lines[insert_line].strip():
            insert_line += 1

        # Skip existing todos to find the insertion point
        while insert_line < len(lines):
            line = lines[insert_line]
            # Stop if we hit another section or non-todo content
            if re.match(r'^##\s+', line) or (line.strip() and not re.match(r'^\s*- \[', line)):
                break
            if line.strip():  # Non-empty line
                insert_line += 1
            else:
                break

        # Format the migrated todos
        migrated_lines = []
        for group in todo_groups:
            for todo in group:
                migrated_line = self.format_migrated_todo(todo, original_date)
                migrated_lines.append(migrated_line)

        # Insert the migrated todos
        if migrated_lines:
            # Add a blank line before if there are existing todos
            if insert_line > todo_section_line + 1 and lines[insert_line - 1].strip():
                migrated_lines.insert(0, "")

            # Insert the new todos
            for i, todo_line in enumerate(migrated_lines):
                lines.insert(insert_line + i, todo_line)

        # Write back to file
        try:
            with open(note_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            return True
        except IOError as e:
            print(f"Error writing to {note_path}: {e}")
            return False

    def migrate_todos(self, source_date=None, target_date=None, dry_run=False):
        """Main function to migrate todos."""
        print("📋 Todo Migrator")
        print("=" * 30)

        # Default to yesterday -> today
        if source_date is None:
            source_date = datetime.now() - timedelta(days=1)
        if target_date is None:
            target_date = datetime.now()

        source_path = self.get_daily_note_path(source_date)
        target_path = self.get_daily_note_path(target_date)

        print(f"📅 Source: {source_date.strftime('%Y-%m-%d')} ({source_path.name})")
        print(f"📅 Target: {target_date.strftime('%Y-%m-%d')} ({target_path.name})")

        # Check if source note exists
        if not source_path.exists():
            print(f"ℹ️  Source note not found: {source_path}")
            return True

        # Extract incomplete todos from source
        incomplete_groups = self.extract_todos_from_note(source_path)

        if not incomplete_groups:
            print("✅ No incomplete todos found to migrate")
            return True

        # Count total todos to migrate
        total_todos = sum(len(group) for group in incomplete_groups)
        print(f"📝 Found {total_todos} todos to migrate ({len(incomplete_groups)} groups)")

        # Show what will be migrated
        for i, group in enumerate(incomplete_groups, 1):
            print(f"\nGroup {i}:")
            for todo in group:
                status = "✓" if todo['completed'] else "○"
                print(f"  {status} {todo['text']}")

        if dry_run:
            print("\n🔍 DRY RUN - No files will be modified")
            return True

        # Create target note if it doesn't exist
        if not self.create_today_note_if_missing(target_path):
            return False

        # Add todos to target note
        success = self.add_todos_to_note(target_path, incomplete_groups, source_date)

        if success:
            print(f"\n✅ Successfully migrated {total_todos} todos to {target_path.name}")
        else:
            print(f"\n❌ Failed to migrate todos to {target_path.name}")

        return success

def parse_date(date_str):
    """Parse a date string in YYYY-MM-DD format."""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")

def main():
    parser = argparse.ArgumentParser(
        description="Migrate incomplete todos between Obsidian daily notes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 todo_migrator.py                    # Migrate yesterday's todos to today
  python3 todo_migrator.py --dry-run          # Preview migration
  python3 todo_migrator.py --from 2025-08-01  # Migrate from specific date to today
  python3 todo_migrator.py --from 2025-08-01 --to 2025-08-02  # Migrate between specific dates
        """
    )

    parser.add_argument("--vault-path",
                       default="Desktop/obsidian_vault",
                       help="Path to Obsidian vault (relative to home directory)")
    parser.add_argument("--from",
                       dest="source_date",
                       type=parse_date,
                       help="Source date (YYYY-MM-DD, default: yesterday)")
    parser.add_argument("--to",
                       dest="target_date",
                       type=parse_date,
                       help="Target date (YYYY-MM-DD, default: today)")
    parser.add_argument("--dry-run",
                       action="store_true",
                       help="Show what would be migrated without making changes")

    args = parser.parse_args()

    try:
        migrator = TodoMigrator(args.vault_path)
        success = migrator.migrate_todos(
            source_date=args.source_date,
            target_date=args.target_date,
            dry_run=args.dry_run
        )
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
