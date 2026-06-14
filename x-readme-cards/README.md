# X README Cards

Updates the `robione-nr` GitHub profile README with recent X posts rendered as a three-card Markdown/HTML row.

The workflow fetches posts with Scweet, renders `outputs/x-posts.md`, inserts that markup between README markers, commits the README change on an update branch, automatically merges it into `main`, and pushes `main` to GitHub.

## Files

- `test.py`: fetches X posts and renders Markdown cards.
- `update_profile_readme.sh`: unattended VPS updater.
- `requirements.txt`: Python dependencies.
- `config.json`: local secret config. Do not commit this file.
- `outputs/`: generated JSON and Markdown. Do not commit this folder.

## Required README Markers

The target profile repo README must contain these markers. The updater will append them if they are missing.

```md
<!-- X-POSTS:START -->
<!-- X-POSTS:END -->
```

## VPS Setup

Install system basics:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv
```

Configure git identity:

```bash
git config --global user.name "Nolan Robidoux"
git config --global user.email "your-github-email@example.com"
```

Make sure the VPS has GitHub SSH access:

```bash
ssh -T git@github.com
```

Expected result is a successful authentication message for `robione-nr`.

## Configuration

Create `config.json` beside the scripts on the VPS. It should include the X username, max post count, and Scweet cookie values used by `test.py`.

Do not commit `config.json`.

## Run Manually

From this folder:

```bash
chmod +x update_profile_readme.sh
./update_profile_readme.sh
```

The script checks for required commands, creates or repairs `.venv`, installs Scweet if needed, clones the profile repo if needed, updates `README.md`, commits on `update-x-posts`, merges into `main`, and pushes `main`.

## Cron

Example hourly cron entry:

```cron
0 * * * * cd /opt/misc_scripts/x-readme-cards && ./update_profile_readme.sh >> update-x-posts.log 2>&1
```

## Generated Output Only

To render from existing `outputs/tweets.json` without fetching:

```bash
python3 test.py --no-fetch
```

## Safety Notes

- The script is designed for unattended updates, but it stops if the cloned profile repo has uncommitted changes.
- The branch workflow is still used: updates are committed on `update-x-posts`, then automatically merged into `main`.
- The updater uses `.venv/bin/python` directly rather than activating the virtualenv in shell state.

[Back to Misc Scripts](../README.md)

