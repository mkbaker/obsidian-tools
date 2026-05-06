#!/usr/bin/env python3
"""
Good Morning workflow for Obsidian daily notes.
Migrates todos, summarizes yesterday, and on Mondays (or --new-week) recaps the week.
"""

import json
import sys
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from todo_migrator import TodoMigrator
from weekly_notes_archiver import WeeklyNotesArchiver


SONNET_MODEL = "claude-sonnet-4-6"
HAIKU_MODEL = "claude-haiku-4-5-20251001"
TOKEN_THRESHOLD = 60_000
OLLAMA_URL = "http://localhost:11434"


class GoodMorning:
    def __init__(self, vault_path, use_claude=False, use_sonnet=False,
                 ollama_model=None, dry_run=False, new_week=False, no_archive=False):
        self.vault_path = vault_path
        self.use_claude = use_claude
        self.use_sonnet = use_sonnet
        self.ollama_model = ollama_model
        self.dry_run = dry_run
        self.new_week = new_week
        self.no_archive = no_archive
        self.migrator = TodoMigrator(vault_path)
        self.archiver = WeeklyNotesArchiver(vault_path)
        self._ollama_available_cache = None
        self._ollama_models_cache = None

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

    def _check_ollama(self):
        if self._ollama_available_cache is not None:
            return self._ollama_available_cache
        try:
            urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2)
            self._ollama_available_cache = True
        except Exception:
            self._ollama_available_cache = False
        return self._ollama_available_cache

    def _get_ollama_models(self):
        if self._ollama_models_cache is not None:
            return self._ollama_models_cache
        try:
            resp = urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2)
            data = json.loads(resp.read())
            self._ollama_models_cache = [m['name'] for m in data.get('models', [])]
        except Exception:
            self._ollama_models_cache = []
        return self._ollama_models_cache

    def _call_ollama(self, prompt, model):
        payload = json.dumps({'model': model, 'prompt': prompt, 'stream': False}).encode()
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=payload,
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())['response'].strip()

    def _call_claude(self, prompt, model):
        try:
            import anthropic
        except ImportError:
            print("Error: anthropic package not installed. Run: pip install anthropic")
            sys.exit(1)
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text.strip()

    def call_llm(self, prompt):
        """Return (response_text, model_label). Tier: ollama -> haiku -> sonnet."""
        tokens = len(prompt) // 4

        if self.use_sonnet:
            label = f"claude/{SONNET_MODEL}"
            print(f"  Using {label}")
            return self._call_claude(prompt, SONNET_MODEL), label

        if self.use_claude:
            label = f"claude/{HAIKU_MODEL}"
            print(f"  Using {label}")
            return self._call_claude(prompt, HAIKU_MODEL), label

        if self._check_ollama():
            models = self._get_ollama_models()
            if models:
                if tokens > TOKEN_THRESHOLD:
                    print(f"  Content large (~{tokens:,} tokens), escalating to Claude Sonnet")
                    label = f"claude/{SONNET_MODEL}"
                    return self._call_claude(prompt, SONNET_MODEL), label
                model = self.ollama_model or models[0]
                label = f"ollama/{model}"
                print(f"  Using {label}")
                return self._call_ollama(prompt, model), label
            print("  Ollama running but no models found, falling back to Claude Haiku")
        else:
            print("  Ollama unavailable, using Claude Haiku")

        if tokens > TOKEN_THRESHOLD:
            print(f"  Content large (~{tokens:,} tokens), using Claude Sonnet")
            label = f"claude/{SONNET_MODEL}"
            return self._call_claude(prompt, SONNET_MODEL), label

        label = f"claude/{HAIKU_MODEL}"
        print(f"  Using {label}")
        return self._call_claude(prompt, HAIKU_MODEL), label

    def summarize_day(self, date, content):
        prompt = (
            f"Here is my daily note from {date.strftime('%A, %B %d, %Y')}:\n\n"
            f"{content}\n\n"
            "Summarize in 3-5 sentences: what was worked on, what was completed, "
            "and what remains open. Be concise and specific."
        )
        return self.call_llm(prompt)

    def summarize_week(self, notes_by_date):
        combined = ""
        for date in sorted(notes_by_date):
            combined += f"\n\n### {date.strftime('%A, %B %d')}\n{notes_by_date[date]}"
        prompt = (
            f"Here are my daily notes from last week:\n{combined}\n\n"
            "Summarize in 5-8 sentences: main themes, key accomplishments, "
            "and items carried forward. Be concise and specific."
        )
        return self.call_llm(prompt)

    def append_morning_brief(self, today_path, day_summary, day_model,
                              week_summary, week_model, prev_date):
        content = today_path.read_text(encoding='utf-8')
        if '## Morning Brief' in content:
            print("  Morning Brief already exists, skipping write")
            return

        brief = "\n## Morning Brief\n\n"
        if day_summary:
            brief += f"**Yesterday ({prev_date.strftime('%a %b %d')}):** {day_summary}\n"
        if week_summary:
            brief += f"\n**Last week:** {week_summary}\n"

        if day_model and week_model and week_model != day_model:
            models_label = f"{day_model}, {week_model}"
        else:
            models_label = day_model or week_model or "unknown"
        brief += f"\n*Generated by: {models_label}*\n"

        today_path.write_text(content + brief, encoding='utf-8')

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
            if today_path.exists():
                print(f"\n✅ Writing Morning Brief to {today_path.name}...")
                self.append_morning_brief(
                    today_path, day_summary, day_model,
                    week_summary, week_model, prev_day
                )
            else:
                print(f"\n⚠️  Today's note not found at {today_path.name}, skipping Morning Brief")
        elif self.dry_run:
            print(f"\n  [dry-run] Would write Morning Brief to today's note")

        print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Good morning workflow for Obsidian daily notes")
    parser.add_argument("--vault-path", default="Desktop/obsidian_vault",
                        help="Path to Obsidian vault (relative to home)")
    parser.add_argument("--new-week", action="store_true",
                        help="Run weekly recap + archive regardless of day (e.g. after vacation)")
    parser.add_argument("--use-claude", action="store_true",
                        help="Force Claude Haiku instead of ollama")
    parser.add_argument("--use-sonnet", action="store_true",
                        help="Force Claude Sonnet")
    parser.add_argument("--ollama-model", help="Pin a specific ollama model")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show plan without making changes")
    parser.add_argument("--no-archive", action="store_true",
                        help="Skip archiving in new-week mode")
    args = parser.parse_args()

    try:
        gm = GoodMorning(
            vault_path=args.vault_path,
            use_claude=args.use_claude,
            use_sonnet=args.use_sonnet,
            ollama_model=args.ollama_model,
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
