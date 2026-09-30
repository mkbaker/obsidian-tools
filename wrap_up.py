#!/usr/bin/env python3
"""
Wrap-up workflow for Obsidian daily notes.
Summarizes edited notes and GitHub activity, appends to daily note.
Triggers weekly summary on Fridays (or --weekly flag).
"""

import json
import re
import shutil
import subprocess
import sys
import argparse
from datetime import datetime
from pathlib import Path

TICKET_RE = re.compile(r'([A-Za-z]{2,}-\d+)')
STORY_DIR_RE = re.compile(r'^[A-Za-z]{2,}-\d+$')
PAPERCUT_LINE_RE = re.compile(r'^-?\s*(\d{4}-\d{2}-\d{2})\s*·\s*(.+)$')
PAPERCUTS_PATH = Path.home() / "code" / "papercuts.md"

sys.path.insert(0, str(Path(__file__).parent))
from todo_migrator import TodoMigrator
from llm_utils import call_llm
import git_utils


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
        changed = git_utils.changed_md_files(self.vault_path)
        if changed is not None:
            return changed
        return self._find_edited_notes_by_mtime()

    def _find_edited_notes_by_mtime(self):
        """Fallback for when the vault isn't a git repo."""
        today_date = self.today.date()
        edited = []
        for p in self.vault_path.rglob("*.md"):
            if datetime.fromtimestamp(p.stat().st_mtime).date() == today_date:
                edited.append(p)
        return sorted(edited)

    def summarize_notes(self, note_paths):
        story_groups, standalone = self._group_by_story(note_paths)

        results = []
        for folder, paths in story_groups.items():
            result = self._summarize_story_group(folder, paths)
            if result:
                results.append(result)
        for path in standalone:
            result = self._summarize_single_note(path)
            if result:
                results.append(result)
        return results

    def _group_by_story(self, note_paths):
        """Split edited notes into ticket-named story folders vs. standalone notes.

        A "story folder" is a directory whose name is exactly a ticket key
        (e.g. `Stories/FINC-3791/`), containing an Overview note plus one note
        per bug/to-do found during agentic review. Those get summarized as a
        single story-level update rather than one bullet per sub-note.
        """
        story_groups = {}
        standalone = []
        for p in note_paths:
            if STORY_DIR_RE.match(p.parent.name):
                story_groups.setdefault(p.parent, []).append(p)
            else:
                standalone.append(p)
        return story_groups, standalone

    def _summarize_single_note(self, path):
        stem = path.stem
        if "4 ARCHIVE" in path.parts:
            print(f"  [[{stem}]] is archived, skipping summary")
            return (stem, "Archived.", None)
        content, is_diff = git_utils.diff_or_content(path, self.vault_path)
        if not content or not content.strip():
            return None
        print(f"  Summarizing [[{stem}]]...")
        if is_diff:
            prompt = (
                f"Here is the git diff for an Obsidian note titled '{stem}' "
                f"(changes since the last commit):\n\n{content}\n\n"
                "In 1-2 sentences, describe what was added or changed. Be specific and concise. "
                "Where applicable, use Obsidian wiki-link syntax [[like this]] to reference "
                "tickets, people, or related notes mentioned in the content."
            )
        else:
            prompt = (
                f"Here is an Obsidian note titled '{stem}':\n\n{content}\n\n"
                "In 1-2 sentences, describe what this note is about. Be specific and concise. "
                "Where applicable, use Obsidian wiki-link syntax [[like this]] to reference "
                "tickets, people, or related notes mentioned in the content."
            )
        summary, model = call_llm(prompt, self.use_claude, self.use_sonnet, self.ollama_model, model="sonnet")
        return (stem, summary, model)

    def _summarize_story_group(self, folder, paths):
        """Summarize all edited notes under one ticket story folder as a single
        story-progress update, instead of one bullet per sub-note/bug file."""
        if "4 ARCHIVE" in folder.parts:
            print(f"  [[{folder.name}]] story is archived, skipping summary")
            return (folder.name, "Archived.", None)

        sections = []
        for path in sorted(paths):
            content, is_diff = git_utils.diff_or_content(path, self.vault_path)
            if not content or not content.strip():
                continue
            label = "diff since last commit" if is_diff else "full content"
            sections.append(f"### {path.stem} ({label})\n{content}")

        if not sections:
            return None

        print(f"  Summarizing story [[{folder.name}]] ({len(sections)} changed note(s))...")

        overview_stem = next((p.stem for p in paths if "overview" in p.stem.lower()), None)
        link_stem = overview_stem or folder.name

        combined = "\n\n".join(sections)
        prompt = (
            f"Here are today's changes across notes in the '{folder.name}' story folder in "
            f"Obsidian (an agentic code-review tracker: one Overview note plus one note per "
            f"bug/to-do found for this ticket):\n\n{combined}\n\n"
            "In 2-4 sentences, give ONE consolidated status update for the story as a whole: "
            "what got fixed/resolved today, what's still open or blocking, and any new "
            "bugs/to-dos found. Do NOT summarize each note individually or go file-by-file. "
            "Be specific and concise. Where applicable, use Obsidian wiki-link syntax "
            "[[like this]] to reference tickets, people, or related notes mentioned in the content."
        )
        summary, model = call_llm(prompt, self.use_claude, self.use_sonnet, self.ollama_model, model="sonnet")
        return (link_stem, summary, model)

    def fetch_todays_papercuts(self):
        """Return today's entries from the global ~/code/papercuts.md log, if any."""
        if not PAPERCUTS_PATH.exists():
            return []

        today_str = self.today.strftime("%Y-%m-%d")
        entries = []
        for line in PAPERCUTS_PATH.read_text(encoding='utf-8').splitlines():
            match = PAPERCUT_LINE_RE.match(line.strip())
            if match and match.group(1) == today_str:
                entries.append(match.group(2).strip())
        return entries

    def fetch_github_activity(self):
        date_str = self.today.strftime("%Y-%m-%d")
        today_date = self.today.date()

        try:
            username_result = subprocess.run(
                ["gh", "api", "user", "--jq", ".login"],
                capture_output=True, text=True, timeout=10
            )
            if username_result.returncode != 0:
                print(f"  Warning: could not get gh username: {username_result.stderr.strip()}")
                return None
            username = username_result.stdout.strip()

            # Events API is real-time; contributionsCollection has cache lag
            events = []
            done = False
            for page in range(1, 4):
                result = subprocess.run(
                    ["gh", "api", f"/users/{username}/events?per_page=100&page={page}"],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode != 0 or not result.stdout.strip():
                    break
                page_events = json.loads(result.stdout)
                if not page_events:
                    break
                for event in page_events:
                    event_date = datetime.fromisoformat(
                        event['created_at'].replace('Z', '+00:00')
                    ).astimezone().date()
                    if event_date == today_date:
                        events.append(event)
                    elif event_date < today_date:
                        done = True
                        break
                if done:
                    break

            # Aggregate pushes by repo. Private repo events omit commits/size, so track push count as fallback.
            pushes_by_repo = {}  # {repo: {'commits': int, 'pushes': int}}
            for event in events:
                if event['type'] == 'PushEvent':
                    repo = event['repo']['name']
                    entry = pushes_by_repo.setdefault(repo, {'commits': 0, 'pushes': 0})
                    entry['pushes'] += 1
                    commit_count = event['payload'].get('size', len(event['payload'].get('commits', [])))
                    entry['commits'] += commit_count

            commit_contributions = [
                {
                    'repository': {'nameWithOwner': repo},
                    'contributions': {
                        'totalCount': data['commits'] if data['commits'] > 0 else data['pushes'],
                        'unit': 'commits' if data['commits'] > 0 else 'pushes',
                    },
                }
                for repo, data in pushes_by_repo.items()
            ]

            # New repositories created today
            created_repos = [
                event['repo']['name']
                for event in events
                if event['type'] == 'CreateEvent'
                and event['payload'].get('ref_type') == 'repository'
            ]

            # PR reviews from events (deduped by repo+number)
            seen_reviews = set()
            review_contributions = []
            for event in events:
                if event['type'] == 'PullRequestReviewEvent':
                    pr = event['payload'].get('pull_request', {})
                    review_body = event['payload'].get('review', {}).get('body', '')
                    key = f"{event['repo']['name']}#{pr.get('number')}"
                    if key not in seen_reviews:
                        seen_reviews.add(key)
                        review_contributions.append({
                            'pullRequest': {
                                'title': pr.get('title', ''),
                                'number': pr.get('number'),
                                'repository': {'nameWithOwner': event['repo']['name']},
                                'author': (pr.get('user') or {}).get('login', ''),
                                'url': pr.get('html_url', ''),
                                'headRefName': (pr.get('head') or {}).get('ref', ''),
                            },
                            'reviewBody': review_body,
                        })

            # Search queries for opened/merged PRs (accurate, not subject to events lag)
            query = f"""
query {{
  mergedPRs: search(query: "author:{username} type:pr merged:{date_str}", type: ISSUE, first: 20) {{
    nodes {{
      ... on PullRequest {{ title number repository {{ nameWithOwner }} state headRefName }}
    }}
  }}
  openedPRs: search(query: "author:{username} type:pr created:{date_str}", type: ISSUE, first: 20) {{
    nodes {{
      ... on PullRequest {{ title number repository {{ nameWithOwner }} state isDraft }}
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
                merged_prs, opened_prs = [], []
            else:
                data = json.loads(result.stdout)
                merged_prs = data['data']['mergedPRs']['nodes']
                opened_prs = data['data']['openedPRs']['nodes']

            for pr in merged_prs + opened_prs:
                detail = self.fetch_pr_detail(pr['repository']['nameWithOwner'], pr['number'])
                if detail:
                    pr.update(detail)

            return {
                'commitContributionsByRepository': commit_contributions,
                'createdRepos': created_repos,
                'pullRequestReviewContributions': {'nodes': review_contributions},
                'mergedPRs': merged_prs,
                'openedPRs': opened_prs,
            }
        except Exception as e:
            print(f"  Warning: GitHub activity fetch failed: {e}")
            return None

    def fetch_pr_detail(self, repo, number):
        """Fetch body, diffstat, author, url for a PR via gh pr view. Returns None on failure."""
        try:
            result = subprocess.run(
                ["gh", "pr", "view", str(number), "--repo", repo,
                 "--json", "body,additions,deletions,changedFiles,author,url,headRefName"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0:
                return None
            data = json.loads(result.stdout)
            return {
                'body': (data.get('body') or '').strip(),
                'additions': data.get('additions', 0),
                'deletions': data.get('deletions', 0),
                'changedFiles': data.get('changedFiles', 0),
                'author': (data.get('author') or {}).get('login', ''),
                'url': data.get('url', ''),
                'headRefName': data.get('headRefName', ''),
            }
        except Exception:
            return None

    def _pr_link(self, pr):
        """Build a markdown link '[TICKET / Title -- Author](url)' for a PR dict."""
        repo = pr['repository']['nameWithOwner']
        number = pr['number']
        url = pr.get('url') or f"https://github.com/{repo}/pull/{number}"

        ticket = None
        for source in (pr.get('headRefName', ''), pr.get('title', '')):
            match = TICKET_RE.search(source or '')
            if match:
                ticket = match.group(1).upper()
                break

        title = pr.get('title', '')
        if ticket:
            title = re.sub(rf'^\[?{re.escape(ticket)}\]?[:\-/ ]*', '', title, flags=re.IGNORECASE).strip()

        label = f"{ticket} / {title}" if ticket else title
        author = pr.get('author')
        if author:
            label += f" -- {author}"

        return f"[{repo}#{number}]({url}): {label}"

    def format_github_context(self, activity):
        lines = []

        created = activity.get('createdRepos', [])
        if created:
            lines.append("Repositories created:")
            for repo in created:
                lines.append(f"  - {repo}")

        commits = activity.get('commitContributionsByRepository', [])
        if commits:
            lines.append("Commits:")
            for entry in commits:
                repo = entry['repository']['nameWithOwner']
                count = entry['contributions']['totalCount']
                unit = entry['contributions'].get('unit', 'commits')
                lines.append(f"  - {count} {unit} to {repo}")

        opened_prs = activity.get('openedPRs', [])
        if opened_prs:
            lines.append("Pull requests opened:")
            for pr in opened_prs:
                draft_tag = " [draft]" if pr.get('isDraft') else ""
                lines.append(f"  - {self._pr_link(pr)}{draft_tag}")
                lines.extend(self._format_pr_detail_lines(pr))

        merged_prs = activity.get('mergedPRs', [])
        if merged_prs:
            lines.append("Pull requests merged:")
            for pr in merged_prs:
                lines.append(f"  - {self._pr_link(pr)}")
                lines.extend(self._format_pr_detail_lines(pr))

        reviews = activity.get('pullRequestReviewContributions', {}).get('nodes', [])
        if reviews:
            lines.append("Reviews:")
            for node in reviews:
                pr = node['pullRequest']
                lines.append(f"  - Reviewed {self._pr_link(pr)}")
                review_body = (node.get('reviewBody') or '').strip()
                if review_body:
                    lines.append(f"      My comment: {review_body}")

        return '\n'.join(lines) if lines else None

    def _format_pr_detail_lines(self, pr):
        """Format optional diffstat/body lines for a PR dict enriched by fetch_pr_detail."""
        lines = []
        if 'changedFiles' in pr:
            lines.append(
                f"      {pr['changedFiles']} files changed, "
                f"+{pr['additions']}/-{pr['deletions']}"
            )
        body = (pr.get('body') or '').strip()
        if body:
            snippet = body if len(body) <= 300 else body[:300] + "..."
            lines.append(f"      Description: {snippet}")
        return lines

    def find_story_notes(self, ticket):
        """Find all story note files/folders for a ticket key, anywhere outside the archive.
        Paths nested inside another match (e.g. notes inside a story folder) are skipped,
        since moving the parent folder carries them along."""
        matches = set()
        for pattern in (ticket, ticket.lower()):
            for p in self.vault_path.rglob(f"{pattern}*"):
                if "4 ARCHIVE" in str(p):
                    continue
                matches.add(p)
        return sorted(p for p in matches if not any(m in p.parents for m in matches))

    def archive_merged_stories(self, merged_prs):
        """Move story notes whose ticket matches a branch merged today into 4 ARCHIVE/Stories."""
        archived = []
        dest_dir = self.vault_path / "4 ARCHIVE" / "Stories"

        for pr in merged_prs:
            branch = pr.get('headRefName', '')
            match = TICKET_RE.search(branch)
            if not match:
                continue
            ticket = match.group(1).upper()

            for note_path in self.find_story_notes(ticket):
                dest = dest_dir / note_path.name
                if dest.exists():
                    continue

                if self.dry_run:
                    print(f"  [dry-run] Would archive [[{note_path.stem}]] ({note_path.name}, branch {branch} merged)")
                else:
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(note_path), str(dest))
                    print(f"  📦 Archived [[{note_path.stem}]] (branch {branch} merged)")

                archived.append((note_path.stem, pr))

        return archived

    def summarize_github(self, activity_text):
        prompt = (
            f"Here is my GitHub activity for today:\n\n{activity_text}\n\n"
            "Summarize as 3-5 bullet points what I worked on. Be concise and specific. "
            "Where applicable, use Obsidian wiki-link syntax [[like this]] to reference "
            "tickets, repos, or projects that likely have their own notes."
        )
        return call_llm(prompt, self.use_claude, self.use_sonnet, self.ollama_model, model="sonnet")

    def append_wrapup(self, today_path, note_summaries, github_summary, github_model, archived_stories=None, papercuts=None):
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
            section += f"\n**GitHub activity:**\n{github_summary}\n"

        if archived_stories:
            section += "\n**Stories archived (branch merged):**\n"
            for stem, pr in archived_stories:
                section += f"- [[{stem}]] — {self._pr_link(pr)}\n"

        if papercuts:
            section += "\n**Papercuts logged today:**\n"
            for entry in papercuts:
                section += f"- {entry}\n"

        all_models = list(dict.fromkeys(
            [m for _, _, m in note_summaries if m] + ([github_model] if github_model else [])
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
        archived_stories = []

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

                merged_prs = activity.get('mergedPRs', [])
                if merged_prs:
                    print("\n📦 Checking for merged-branch stories to archive...")
                    archived_stories = self.archive_merged_stories(merged_prs)
                    if not archived_stories:
                        print("  None found")
            else:
                print("  GitHub activity unavailable, skipping")

        # Papercuts logged today
        print("\n🩹 Checking papercuts log...")
        papercuts = self.fetch_todays_papercuts()
        if papercuts:
            print(f"  Found {len(papercuts)} entr{'y' if len(papercuts) == 1 else 'ies'}")
        else:
            print("  None found")

        # Append wrap-up to daily note
        today_path = self.migrator.get_daily_note_path(self.today)
        if self.dry_run:
            print(f"\n  [dry-run] Would append ## Wrap-up to today's note")
        elif note_summaries or github_summary or archived_stories or papercuts:
            if today_path.exists():
                print(f"\n✅ Writing Wrap-up to {today_path.name}...")
                self.append_wrapup(today_path, note_summaries, github_summary, github_model, archived_stories, papercuts)
            else:
                print(f"\n⚠️  Today's note not found at {today_path.name}, skipping write")

        # Weekly summary (Friday or --weekly flag)
        is_friday = self.today.weekday() == 4
        if (is_friday or self.weekly) and not self.no_weekly:
            print(f"\n📅 Running weekly summary...")
            self.trigger_weekly_summary()

        # Commit the day's vault changes
        print(f"\n💾 Committing vault changes...")
        if self.dry_run:
            print("  [dry-run] Would commit vault changes")
        else:
            committed = git_utils.commit_all(
                self.vault_path, f"Daily notes: {self.today.strftime('%Y-%m-%d')}"
            )
            print("  Committed" if committed else "  Nothing to commit")

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
