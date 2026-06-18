#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${VENV_DIR:-$SCRIPT_DIR/.venv}"
WORK_DIR="${WORK_DIR:-$SCRIPT_DIR/profile-work}"
REPO_URL="${REPO_URL:-git@github.com:robione-nr/robione-nr.git}"
REPO_DIR="${REPO_DIR:-$WORK_DIR/robione-nr}"
MAIN_BRANCH="${MAIN_BRANCH:-main}"
UPDATE_BRANCH="${UPDATE_BRANCH:-update-x-posts}"
README_PATH="${README_PATH:-README.md}"
COMMIT_MESSAGE="${COMMIT_MESSAGE:-docs(readme): update X posts}"
AUTO_MERGE_MAIN="${AUTO_MERGE_MAIN:-true}"
DRY_RUN="${DRY_RUN:-false}"
NO_FETCH="${NO_FETCH:-false}"
SHOW_DIFF="${SHOW_DIFF:-false}"
VERBOSE="${VERBOSE:-false}"

START_MARKER="<!-- X-POSTS:START -->"
END_MARKER="<!-- X-POSTS:END -->"

log() {
  printf '%s\n' "$*"
}

log_run_header() {
  printf '===== %s =====\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')"
}

usage() {
  printf 'Usage: %s [--dry-run] [--no-fetch] [--show-diff] [--verbose]\n' "$(basename "$0")"
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --dry-run)
        DRY_RUN=true
        ;;
      --no-fetch)
        NO_FETCH=true
        ;;
      --show-diff)
        SHOW_DIFF=true
        ;;
      --verbose)
        VERBOSE=true
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        usage
        log "Unknown option: $1"
        exit 1
        ;;
    esac
    shift
  done
}

install_apt_package() {
  package="$1"

  if ! command -v apt-get >/dev/null 2>&1; then
    log "Missing $package and apt-get is not available. Install $package, then rerun this script."
    exit 1
  fi

  log "Installing $package"
  sudo apt-get update
  sudo apt-get install -y "$package"
}

ensure_command() {
  command_name="$1"
  apt_package="$2"

  if command -v "$command_name" >/dev/null 2>&1; then
    return
  fi

  install_apt_package "$apt_package"

  if ! command -v "$command_name" >/dev/null 2>&1; then
    log "$command_name is still unavailable after installing $apt_package."
    exit 1
  fi
}

ensure_local_file() {
  path="$1"

  if [ ! -f "$path" ]; then
    log "Missing required file: $path"
    exit 1
  fi
}

ensure_venv() {
  if [ ! -d "$VENV_DIR" ]; then
    log "Creating Python virtualenv at $VENV_DIR"
    if ! python3 -m venv "$VENV_DIR"; then
      install_apt_package python3-venv
      python3 -m venv "$VENV_DIR"
    fi
  fi

  PYTHON="$VENV_DIR/bin/python"
  PIP="$VENV_DIR/bin/pip"

  if [ ! -x "$PYTHON" ] || [ ! -x "$PIP" ]; then
    log "Virtualenv at $VENV_DIR is incomplete. Recreating it."
    rm -rf "$VENV_DIR"
    if ! python3 -m venv "$VENV_DIR"; then
      install_apt_package python3-venv
      python3 -m venv "$VENV_DIR"
    fi
  fi

  PYTHON="$VENV_DIR/bin/python"
  PIP="$VENV_DIR/bin/pip"
}

ensure_python_dependencies() {
  if ! "$PYTHON" -m pip --version >/dev/null 2>&1; then
    log "Virtualenv at $VENV_DIR cannot run pip."
    exit 1
  fi

  if ! "$PYTHON" -c "import Scweet" >/dev/null 2>&1; then
    if [ "$DRY_RUN" = "true" ]; then
      log "Dry run: Scweet is not installed in $VENV_DIR. No dependencies were installed."
      exit 1
    fi

    log "Installing Python dependencies from requirements.txt"
    "$PIP" install -r "$SCRIPT_DIR/requirements.txt"
  else
    log "Scweet is already installed in $VENV_DIR"
  fi
}

ensure_repo() {
  mkdir -p "$WORK_DIR"

  if [ ! -d "$REPO_DIR/.git" ]; then
    log "Cloning $REPO_URL into $REPO_DIR"
    git clone "$REPO_URL" "$REPO_DIR"
  fi

  cd "$REPO_DIR"
  git fetch origin "$MAIN_BRANCH"
  git checkout "$MAIN_BRANCH"
  git pull --ff-only origin "$MAIN_BRANCH"

  if ! git diff --quiet || ! git diff --cached --quiet; then
    log "$REPO_DIR has uncommitted changes. Commit or remove them, then rerun this script."
    exit 1
  fi
}

ensure_readme_markers() {
  readme="$REPO_DIR/$README_PATH"

  if [ ! -f "$readme" ]; then
    if [ "$DRY_RUN" = "true" ]; then
      log "Dry run: would create $README_PATH with X post markers"
      return 1
    fi

    log "Creating $README_PATH with X post markers"
    printf '# robione-nr\n\n%s\n%s\n' "$START_MARKER" "$END_MARKER" > "$readme"
    return
  fi

  if ! grep -Fq "$START_MARKER" "$readme" || ! grep -Fq "$END_MARKER" "$readme"; then
    if [ "$DRY_RUN" = "true" ]; then
      log "Dry run: would add X post markers to $README_PATH"
      return 1
    fi

    log "Adding X post markers to $README_PATH"
    printf '\n%s\n%s\n' "$START_MARKER" "$END_MARKER" >> "$readme"
  fi
}

prepare_update_branch() {
  cd "$REPO_DIR"

  if git rev-parse --verify "$UPDATE_BRANCH" >/dev/null 2>&1; then
    git branch -D "$UPDATE_BRANCH"
  fi

  git checkout -b "$UPDATE_BRANCH"
}

commit_readme_update() {
  cd "$REPO_DIR"

  if git diff --quiet -- "$README_PATH"; then
    log "No README changes to commit."
    exit 0
  fi

  git add "$README_PATH"
  git commit -m "$COMMIT_MESSAGE"
}

publish_update() {
  cd "$REPO_DIR"

  if [ "$AUTO_MERGE_MAIN" = "true" ]; then
    git checkout "$MAIN_BRANCH"
    git merge --no-ff "$UPDATE_BRANCH" -m "Merge branch '$UPDATE_BRANCH'"
    git push origin "$MAIN_BRANCH"
    log "Updated origin/$MAIN_BRANCH through branch $UPDATE_BRANCH."
  else
    git push -u origin "$UPDATE_BRANCH" --force-with-lease
    log "Pushed branch $UPDATE_BRANCH. Open a pull request, or merge it manually after review."
  fi
}

run_xcards() {
  args=("$SCRIPT_DIR/xcards.py" "--readme" "$REPO_DIR/$README_PATH")

  if [ "$DRY_RUN" = "true" ]; then
    args+=("--dry-run")
  fi

  if [ "$NO_FETCH" = "true" ]; then
    args+=("--no-fetch")
  fi

  if [ "$SHOW_DIFF" = "true" ]; then
    args+=("--show-diff")
  fi

  if [ "$VERBOSE" = "true" ]; then
    args+=("--verbose")
  fi

  "$PYTHON" "${args[@]}"
}

cd "$SCRIPT_DIR"

log_run_header
parse_args "$@"

ensure_command git git
ensure_command python3 python3
ensure_local_file "$SCRIPT_DIR/xcards.py"
ensure_local_file "$SCRIPT_DIR/config.json"
ensure_local_file "$SCRIPT_DIR/requirements.txt"

ensure_venv
ensure_python_dependencies
ensure_repo
if ! ensure_readme_markers; then
  exit 0
fi

if [ "$DRY_RUN" != "true" ]; then
  prepare_update_branch
fi

cd "$SCRIPT_DIR"
if [ "$DRY_RUN" = "true" ]; then
  run_xcards
  log "Dry run complete. No commit or push."
  exit 0
fi

run_xcards

commit_readme_update
publish_update
