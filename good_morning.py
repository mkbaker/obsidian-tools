#!/usr/bin/env python3
"""
Good Morning workflow for Obsidian daily notes.
Migrates todos, summarizes yesterday, and on Mondays (or --new-week) recaps the week.
"""

import re
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from todo_migrator import TodoMigrator
from weekly_notes_archiver import WeeklyNotesArchiver
from llm_utils import call_llm


class GoodMorning:
    def __init__(self, vault_path, use_claude=False, use_sonnet=False,
                 ollama_model=None, dry_run=False, new_week=False, no_archive=False):
        self.vault_path = vault_path
        self.dry_run = dry_run
        self.new_week = new_week
        self.no_archive = no_archive
        self.migrator = TodoMigrator(vault_path)
        self.archiver = WeeklyNotesArchiver(vault_path)

    def get_last_working_day(self):
        day = datetime.now() - timedelta(days=1)
        while day.weekday() >= 5:
            day -= timedelta(days=1)
        return day

    def get_previous_week_range(self):
        today = datetime.now()
        last_monday = today - timedelta(days=today.weekday() + 7)
        last_friday = last_monday + timedelta(days=4)
        return last_monday, last_friday

    def is_new_week_mode(self):
        return self.new_week or datetime.now().weekday() == 0

    def read_note(self, date):
        path = self.migrator.get_daily_note_path(date)
        if not path.exists():
            return None
        try:
            return path.read_text(encoding='utf-8')
        except IOError:
            return None

    def strip_morning_brief(self, content):
        """Remove the Morning Brief section so the LLM only sees actual work logged that day."""
        lines = content.split('\n')
        in_brief = False
        result = []
        for line in lines:
            if re.match(r'^##\s+Morning Brief', line):
                in_brief = True
                continue
            if in_brief and re.match(r'^---\s*$', line):
                in_brief = False
                continue
            if not in_brief:
                result.append(line)
        return '\n'.join(result).strip()

    def summarize_day(self, date, content):
        stripped = self.strip_morning_brief(content)
        if not stripped:
            return None, None
        prompt = (
            f"Here is my daily note from {date.strftime('%A, %B %d, %Y')}:\n\n"
            f"{stripped}\n\n"
            "Summarize as 3-5 bullet points what was actually worked on or completed that day. "
            "Focus only on work logged in this note (meeting notes, wrap-up, ideas, etc.) — "
            "do NOT include anything from a Morning Brief or prior-day recap. "
            "If there is nothing substantive logged, say so in one bullet. "
            "Be concise and specific. "
            "Where applicable, use Obsidian wiki-link syntax to reference relevant notes — "
            "for example, ticket IDs like [[FINC-3649]], people, or projects that likely have their own notes."
        )
        return call_llm(prompt)

    def summarize_week(self, notes_by_date):
        combined = ""
        for date in sorted(notes_by_date):
            stripped = self.strip_morning_brief(notes_by_date[date])
            if stripped:
                combined += f"\n\n### {date.strftime('%A, %B %d')}\n{stripped}"
        prompt = (
            f"Here are my daily notes from last week:\n{combined}\n\n"
            "Summarize in 5-8 sentences: main themes, key accomplishments, "
            "and items carried forward. Be concise and specific."
        )
        return call_llm(prompt)

    def create_today_note(self, today_path):
        vault_root = self.migrator.get_daily_note_path(datetime.now()).parent
        template_path = vault_root / "Template.md"
        if template_path.exists():
            content = template_path.read_text(encoding='utf-8')
        else:
            content = "\n### Today's Plan\n\n\n## To do\n- [ ] \n\n\n# Meeting Notes\n\n\n## Ideas and Thoughts\n\n\n## End of day recap\n\n"
        today_path.write_text(content, encoding='utf-8')
        print(f"  Created {today_path.name} from template")

    def prepend_morning_brief(self, today_path, day_summary, day_model,
                               week_summary, week_model, prev_date):
        content = today_path.read_text(encoding='utf-8')
        if '## Morning Brief' in content:
            print("  Morning Brief already exists, skipping write")
            return

        brief = "## Morning Brief\n\n"
        if day_summary:
            brief += f"**Yesterday ([[{prev_date.strftime('%Y-%m-%d')}|{prev_date.strftime('%a %b %d')}]]):**\n{day_summary}\n"
        if week_summary:
            brief += f"\n**Last week:** {week_summary}\n"

        if day_model and week_model and week_model != day_model:
            models_label = f"{day_model}, {week_model}"
        else:
            models_label = day_model or week_model or "unknown"
        brief += f"\n*Generated by: {models_label}*\n\n---\n\n"

        today_path.write_text(brief + content.lstrip('\n'), encoding='utf-8')

    def run(self):
        today = datetime.now()
        new_week = self.is_new_week_mode()

        print("=" * 60)
        header = f" Good morning! {today.strftime('%A, %B %d')}"
        if new_week and today.weekday() != 0:
            header += " (new-week mode)"
        print(header)
        print("=" * 60)

        # Step 1: Migrate todos
        print("\n📋 Migrating todos...")
        self.migrator.migrate_todos(dry_run=self.dry_run)

        # Step 2: Summarize previous day
        prev_day = self.get_last_working_day()
        print(f"\n📖 Summarizing {prev_day.strftime('%A, %B %d')}...")
        prev_content = self.read_note(prev_day)
        day_summary = day_model = None

        if prev_content:
            if self.dry_run:
                print(f"  [dry-run] Would summarize {prev_day.strftime('%Y-%m-%d')}")
            else:
                day_summary, day_model = self.summarize_day(prev_day, prev_content)
        else:
            print(f"  No note found for {prev_day.strftime('%Y-%m-%d')}, skipping")

        # Step 3: New-week mode
        week_summary = week_model = None
        if new_week:
            week_start, week_end = self.get_previous_week_range()
            print(f"\n📅 Recapping last week ({week_start.strftime('%b %d')}–{week_end.strftime('%b %d')})...")

            notes = {}
            d = week_start
            while d <= week_end:
                if d.weekday() < 5:
                    c = self.read_note(d)
                    if c:
                        notes[d] = c
                d += timedelta(days=1)

            if notes:
                print(f"  Found {len(notes)} notes")
                if not self.dry_run:
                    week_summary, week_model = self.summarize_week(notes)
            else:
                print("  No notes found from last week")

            if not self.no_archive:
                print(f"\n🗂️  Archiving last week...")
                self.archiver.archive_week('last', dry_run=self.dry_run)

        # Write morning brief
        if not self.dry_run and (day_summary or week_summary):
            today_path = self.migrator.get_daily_note_path(today)
            if not today_path.exists():
                print(f"\n📄 Creating today's note from template...")
                self.create_today_note(today_path)
            print(f"\n✅ Writing Morning Brief to {today_path.name}...")
            self.prepend_morning_brief(
                today_path, day_summary, day_model,
                week_summary, week_model, prev_day
            )
        elif self.dry_run:
            print(f"\n  [dry-run] Would write Morning Brief to today's note")

        print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Good morning workflow for Obsidian daily notes")
    parser.add_argument("--vault-path", default="Desktop/obsidian_vault",
                        help="Path to Obsidian vault (relative to home)")
    parser.add_argument("--new-week", action="store_true",
                        help="Run weekly recap + archive regardless of day (e.g. after vacation)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show plan without making changes")
    parser.add_argument("--no-archive", action="store_true",
                        help="Skip archiving in new-week mode")
    args = parser.parse_args()

    try:
        gm = GoodMorning(
            vault_path=args.vault_path,
            dry_run=args.dry_run,
            new_week=args.new_week,
            no_archive=args.no_archive,
        )
        gm.run()
    except KeyboardInterrupt:
        print("\n❌ Interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
