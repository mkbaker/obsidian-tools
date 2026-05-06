#!/usr/bin/env python3
"""
Wrap-up workflow for Obsidian daily notes.
Summarizes edited notes and GitHub activity, appends to daily note.
Triggers weekly summary on Fridays (or --weekly flag).
"""

import json
import subprocess
import sys
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from todo_migrator import TodoMigrator
from llm_utils import call_llm


class WrapUp:
    def __init__(self, vault_path="Desktop/obsidian_vault", use_claude=False, use_sonnet=False,
                 ollama_model=None, dry_run=False, weekly=False, no_weekly=False):
        self.vault_path_arg = vault_path
        self.vault_path = Path.home() / vault_path
        self.use_claude = use_claude
        self.use_sonnet = use_sonnet
        self.ollama_model = ollama_model
        self.dry_run = dry_run
        self.weekly = weekly
        self.no_weekly = no_weekly
        self.migrator = TodoMigrator(vault_path)
        self.today = datetime.now()

    def find_edited_notes(self):
        today_date = self.today.date()
        daily_note = self.migrator.get_daily_note_path(self.today).resolve()
        edited = []
        for p in self.vault_path.rglob("*.md"):
            if "4 ARCHIVE" in str(p):
                continue
            if p.resolve() == daily_note:
                continue
            if datetime.fromtimestamp(p.stat().st_mtime).date() == today_date:
                edited.append(p)
        return sorted(edited)

    def summarize_notes(self, note_paths):
        results = []
        for path in note_paths:
            stem = path.stem
            print(f"  Summarizing [[{stem}]]...")
            try:
                content = path.read_text(encoding='utf-8')
            except IOError as e:
                print(f"  Warning: could not read {stem}: {e}")
                continue
            prompt = (
                f"Here is an Obsidian note titled '{stem}':\n\n{content}\n\n"
                "In 1-2 sentences, describe what this note is about. Be specific and concise."
            )
            summary, model = call_llm(prompt, self.use_claude, self.use_sonnet, self.ollama_model)
            results.append((stem, summary, model))
        return results

    def fetch_github_activity(self):
        date_str = self.today.strftime("%Y-%m-%d")
        from_dt = f"{date_str}T00:00:00Z"
        to_dt = f"{date_str}T23:59:59Z"

        try:
            username_result = subprocess.run(
                ["gh", "api", "user", "--jq", ".login"],
                capture_output=True, text=True, timeout=10
            )
            if username_result.returncode != 0:
                print(f"  Warning: could not get gh username: {username_result.stderr.strip()}")
                return None
            username = username_result.stdout.strip()

            query = f"""
query {{
  user(login: "{username}") {{
    contributionsCollection(from: "{from_dt}", to: "{to_dt}") {{
      commitContributionsByRepository(maxRepositories: 25) {{
        repository {{ nameWithOwner }}
        contributions {{ totalCount }}
      }}
      pullRequestContributions(first: 20) {{
        nodes {{
          pullRequest {{ title number repository {{ nameWithOwner }} state }}
        }}
      }}
      pullRequestReviewContributions(first: 20) {{
        nodes {{
          pullRequest {{ title number repository {{ nameWithOwner }} }}
        }}
      }}
    }}
  }}
}}
"""
            result = subprocess.run(
                ["gh", "api", "graphql", "-f", f"query={query}"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                print(f"  Warning: gh GraphQL query failed: {result.stderr.strip()}")
                return None

            data = json.loads(result.stdout)
            return data['data']['user']['contributionsCollection']
        except Exception as e:
            print(f"  Warning: GitHub activity fetch failed: {e}")
            return None

    def format_github_context(self, activity):
        lines = []

        commits = activity.get('commitContributionsByRepository', [])
        if commits:
            lines.append("Commits:")
            for entry in commits:
                repo = entry['repository']['nameWithOwner']
                count = entry['contributions']['totalCount']
                lines.append(f"  - {count} commit(s) to {repo}")

        prs = activity.get('pullRequestContributions', {}).get('nodes', [])
        if prs:
            lines.append("Pull requests:")
            for node in prs:
                pr = node['pullRequest']
                lines.append(
                    f"  - [{pr['state']}] {pr['repository']['nameWithOwner']}"
                    f"#{pr['number']}: {pr['title']}"
                )

        reviews = activity.get('pullRequestReviewContributions', {}).get('nodes', [])
        if reviews:
            lines.append("Reviews:")
            for node in reviews:
                pr = node['pullRequest']
                lines.append(
                    f"  - Reviewed {pr['repository']['nameWithOwner']}"
                    f"#{pr['number']}: {pr['title']}"
                )

        return '\n'.join(lines) if lines else None

    def summarize_github(self, activity_text):
        prompt = (
            f"Here is my GitHub activity for today:\n\n{activity_text}\n\n"
            "Summarize in 3-5 sentences what I worked on. Be concise and specific."
        )
        return call_llm(prompt, self.use_claude, self.use_sonnet, self.ollama_model)

    def append_wrapup(self, today_path, note_summaries, github_summary, github_model):
        content = today_path.read_text(encoding='utf-8')
        if '## Wrap-up' in content:
            print("  ## Wrap-up already exists in today's note, skipping")
            return

        section = "\n## Wrap-up\n"

        if note_summaries:
            section += "\n**Notes edited today:**\n"
            for stem, summary, _ in note_summaries:
                section += f"- [[{stem}]] — {summary}\n"

        if github_summary:
            section += f"\n**GitHub activity:** {github_summary}\n"

        all_models = list(dict.fromkeys(
            [m for _, _, m in note_summaries] + ([github_model] if github_model else [])
        ))
        if all_models:
            section += f"\n*Generated by: {', '.join(all_models)}*\n"

        today_path.write_text(content + section, encoding='utf-8')

    def trigger_weekly_summary(self):
        script = Path(__file__).parent / "weekly_summary.py"
        cmd = [sys.executable, str(script), "--vault-path", self.vault_path_arg]
        if self.use_claude:
            cmd.append("--use-claude")
        if self.use_sonnet:
            cmd.append("--use-sonnet")
        if self.ollama_model:
            cmd += ["--ollama-model", self.ollama_model]
        if self.dry_run:
            cmd.append("--dry-run")
        subprocess.run(cmd)

    def run(self):
        print("=" * 60)
        print(f" Wrap-up! {self.today.strftime('%A, %B %d')}")
        print("=" * 60)

        # Find and summarize edited notes
        print("\n📝 Finding edited notes...")
        edited_notes = self.find_edited_notes()
        note_summaries = []

        if edited_notes:
            print(f"  Found: {', '.join(p.stem for p in edited_notes)}")
            if self.dry_run:
                print(f"  [dry-run] Would summarize {len(edited_notes)} notes")
            else:
                note_summaries = self.summarize_notes(edited_notes)
        else:
            print("  None found")

        # GitHub activity
        print("\n🐙 Fetching GitHub activity...")
        github_summary = github_model = None

        if self.dry_run:
            print("  [dry-run] Would fetch GitHub activity")
        else:
            activity = self.fetch_github_activity()
            if activity:
                activity_text = self.format_github_context(activity)
                if activity_text:
                    print("  Summarizing activity...")
                    github_summary, github_model = self.summarize_github(activity_text)
                else:
                    print("  No GitHub activity found today")
            else:
                print("  GitHub activity unavailable, skipping")

        # Append wrap-up to daily note
        today_path = self.migrator.get_daily_note_path(self.today)
        if self.dry_run:
            print(f"\n  [dry-run] Would append ## Wrap-up to today's note")
        elif note_summaries or github_summary:
            if today_path.exists():
                print(f"\n✅ Writing Wrap-up to {today_path.name}...")
                self.append_wrapup(today_path, note_summaries, github_summary, github_model)
            else:
                print(f"\n⚠️  Today's note not found at {today_path.name}, skipping write")

        # Weekly summary (Friday or --weekly flag)
        is_friday = self.today.weekday() == 4
        if (is_friday or self.weekly) and not self.no_weekly:
            print(f"\n📅 Running weekly summary...")
            self.trigger_weekly_summary()

        print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Wrap-up workflow for Obsidian daily notes")
    parser.add_argument("--vault-path", default="Desktop/obsidian_vault",
                        help="Path to Obsidian vault (relative to home)")
    parser.add_argument("--weekly", action="store_true",
                        help="Force weekly summary regardless of day")
    parser.add_argument("--no-weekly", action="store_true",
                        help="Skip weekly summary even on Friday")
    parser.add_argument("--use-claude", action="store_true",
                        help="Force Claude Haiku instead of ollama")
    parser.add_argument("--use-sonnet", action="store_true",
                        help="Force Claude Sonnet")
    parser.add_argument("--ollama-model", help="Pin a specific ollama model")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show plan without making changes")
    args = parser.parse_args()

    try:
        wu = WrapUp(
            vault_path=args.vault_path,
            use_claude=args.use_claude,
            use_sonnet=args.use_sonnet,
            ollama_model=args.ollama_model,
            dry_run=args.dry_run,
            weekly=args.weekly,
            no_weekly=args.no_weekly,
        )
        wu.run()
    except KeyboardInterrupt:
        print("\n❌ Interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
