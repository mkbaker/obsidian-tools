#!/usr/bin/env python3
"""
Weekly Notes Archiver for Obsidian
Automatically archives the previous week's daily notes and screenshots.
"""

import os
import shutil
import re
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import sys

class WeeklyNotesArchiver:
    def __init__(self, vault_path="Desktop/obsidian_vault"):
        self.vault_path = Path.home() / vault_path
        self.daily_notes_path = self.vault_path / "Daily notes"
        self.archive_path = self.vault_path / "4 ARCHIVE" / "Weekly Notes"

    def get_week_range(self, week_spec=None):
        """Get the date range for the specified week (Monday to Sunday).

        Args:
            week_spec: Can be:
                - None: Previous week (default)
                - 'current' or 'this': Current week
                - 'last' or 'previous': Previous week
                - A date string in YYYY-MM-DD format: Week containing that date
                - An integer: Number of weeks ago (0=current, 1=previous, etc.)
        """
        today = datetime.now()

        if week_spec is None or week_spec in ['last', 'previous']:
            # Default: previous week
            target_date = today - timedelta(days=7)
        elif week_spec in ['current', 'this']:
            # Current week
            target_date = today
        elif isinstance(week_spec, int):
            # N weeks ago
            target_date = today - timedelta(days=7 * week_spec)
        elif isinstance(week_spec, str):
            try:
                # Try to parse as date
                target_date = datetime.strptime(week_spec, '%Y-%m-%d')
            except ValueError:
                raise ValueError(f"Invalid date format: {week_spec}. Use YYYY-MM-DD format.")
        else:
            raise ValueError(f"Invalid week specification: {week_spec}")

        # Find the Monday of the target week
        days_since_monday = target_date.weekday()
        week_monday = target_date - timedelta(days=days_since_monday)
        week_sunday = week_monday + timedelta(days=6)

        return week_monday, week_sunday

    def find_daily_notes_for_week(self, start_date, end_date):
        """Find all daily notes files for the given week."""
        daily_notes = []
        current_date = start_date

        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            note_file = self.daily_notes_path / date_str

            # Check for file with or without extension
            if note_file.exists():
                daily_notes.append(note_file)
            elif (note_file.with_suffix('.md')).exists():
                daily_notes.append(note_file.with_suffix('.md'))

            current_date += timedelta(days=1)

        return daily_notes

    def find_screenshots_in_notes(self, note_files):
        """Find screenshot references in the notes and locate the actual files."""
        screenshot_files = []
        screenshot_pattern = re.compile(r'!\[\[([^]]*\.(png|jpg|jpeg|gif|bmp|tiff|webp))\]\]', re.IGNORECASE)

        for note_file in note_files:
            if note_file.exists() and note_file.is_file():
                try:
                    with open(note_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        matches = screenshot_pattern.findall(content)

                        for match in matches:
                            screenshot_name = match[0]
                            # Look for the screenshot in common locations
                            possible_paths = [
                                self.vault_path / screenshot_name,
                                self.vault_path / "attachments" / screenshot_name,
                                self.vault_path / "assets" / screenshot_name,
                                self.daily_notes_path / screenshot_name,
                            ]

                            for path in possible_paths:
                                if path.exists():
                                    screenshot_files.append(path)
                                    break
                except (UnicodeDecodeError, IOError) as e:
                    print(f"Warning: Could not read {note_file}: {e}")

        return list(set(screenshot_files))  # Remove duplicates

    def create_weekly_folder(self, start_date):
        """Create the weekly archive folder."""
        week_folder_name = f"Week of {start_date.strftime('%Y-%m-%d')}"
        week_folder_path = self.archive_path / week_folder_name

        # Create the archive directory structure if it doesn't exist
        self.archive_path.mkdir(parents=True, exist_ok=True)
        week_folder_path.mkdir(exist_ok=True)

        return week_folder_path

    def move_files_to_archive(self, files, destination_folder):
        """Move files to the archive folder."""
        moved_files = []

        for file_path in files:
            if file_path.exists():
                try:
                    destination = destination_folder / file_path.name
                    # Handle file name conflicts
                    counter = 1
                    while destination.exists():
                        stem = file_path.stem
                        suffix = file_path.suffix
                        destination = destination_folder / f"{stem}_{counter}{suffix}"
                        counter += 1

                    shutil.move(str(file_path), str(destination))
                    moved_files.append((file_path, destination))
                    print(f"Moved: {file_path.name} -> {destination}")
                except Exception as e:
                    print(f"Error moving {file_path}: {e}")

        return moved_files

    def archive_week(self, week_spec=None, dry_run=False):
        """Main function to archive the specified week's notes.

        Args:
            week_spec: Week specification (see get_week_range for options)
            dry_run: If True, show what would be done without moving files
        """
        print("🗂️  Weekly Notes Archiver")
        print("=" * 40)

        # Check if vault exists
        if not self.vault_path.exists():
            print(f"Error: Obsidian vault not found at {self.vault_path}")
            return False

        if not self.daily_notes_path.exists():
            print(f"Error: Daily notes folder not found at {self.daily_notes_path}")
            return False

        # Get week range
        try:
            start_date, end_date = self.get_week_range(week_spec)
        except ValueError as e:
            print(f"Error: {e}")
            return False

        # Determine week description for display
        today = datetime.now()
        if week_spec is None or week_spec in ['last', 'previous']:
            week_desc = "previous week"
        elif week_spec in ['current', 'this']:
            week_desc = "current week"
        elif isinstance(week_spec, int):
            if week_spec == 0:
                week_desc = "current week"
            elif week_spec == 1:
                week_desc = "previous week"
            else:
                week_desc = f"{week_spec} weeks ago"
        else:
            week_desc = f"week containing {week_spec}"

        print(f"📅 Archiving {week_desc}: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

        # Find daily notes for the week
        daily_notes = self.find_daily_notes_for_week(start_date, end_date)
        if not daily_notes:
            print("ℹ️  No daily notes found for the specified week.")
            return True

        print(f"📝 Found {len(daily_notes)} daily notes:")
        for note in daily_notes:
            print(f"   • {note.name}")

        # Find screenshots referenced in the notes
        screenshots = self.find_screenshots_in_notes(daily_notes)
        if screenshots:
            print(f"📸 Found {len(screenshots)} screenshots:")
            for screenshot in screenshots:
                print(f"   • {screenshot.name}")
        else:
            print("📸 No screenshots found in the notes.")

        if dry_run:
            print("\n🔍 DRY RUN - No files will be moved")
            week_folder_name = f"Week of {start_date.strftime('%Y-%m-%d')}"
            print(f"Would create folder: {self.archive_path / week_folder_name}")
            return True

        # Create weekly archive folder
        week_folder = self.create_weekly_folder(start_date)
        print(f"📁 Created archive folder: {week_folder}")

        # Move files
        all_files = daily_notes + screenshots
        moved_files = self.move_files_to_archive(all_files, week_folder)

        print(f"\n✅ Successfully archived {len(moved_files)} files to {week_folder.name}")
        return True

def main():
    parser = argparse.ArgumentParser(
        description="Archive Obsidian daily notes by week",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Week specification examples:
  (no option)           Archive previous week (default)
  --week current        Archive current week
  --week this           Archive current week
  --week previous       Archive previous week
  --week last           Archive previous week
  --week 2025-05-23     Archive week containing May 23, 2025
  --week 0              Archive current week (0 weeks ago)
  --week 1              Archive previous week (1 week ago)
  --week 2              Archive 2 weeks ago
        """
    )
    parser.add_argument("--vault-path",
                       default="Desktop/obsidian_vault",
                       help="Path to Obsidian vault (relative to home directory)")
    parser.add_argument("--week",
                       help="Week to archive (default: previous week)")
    parser.add_argument("--dry-run",
                       action="store_true",
                       help="Show what would be archived without moving files")

    args = parser.parse_args()

    # Parse week specification
    week_spec = args.week
    if week_spec and week_spec.isdigit():
        week_spec = int(week_spec)

    try:
        archiver = WeeklyNotesArchiver(args.vault_path)
        success = archiver.archive_week(week_spec, dry_run=args.dry_run)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
