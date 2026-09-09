#!/usr/bin/env bash
# Install svg-skill to one or more agent skill directories.
#
# Usage:
#   bash install.sh                     # Cursor only (default)
#   bash install.sh --all               # all supported agents (global)
#   bash install.sh --claude --codex    # specific agents
#   bash install.sh --project           # .agents/skills/svg-skill in cwd
#   bash install.sh --project --cursor  # .cursor/skills/svg-skill in cwd
#   bash install.sh /path/to/dest       # custom destination (legacy)
#   bash install.sh --list              # show supported agents
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SKILL_NAME="svg-skill"

FILES=(SKILL.md scenarios.md reference.md examples.md)
DIRS=(scripts)

usage() {
  cat <<'EOF'
Install svg-skill (Agent Skill pack) for AI coding tools.

Usage:
  bash install.sh [options] [custom-dest]

Options:
  --all          Install to all supported agents (global)
  --project      Install into the current project instead of home
  --list         List supported agents and install paths
  --cursor       Cursor
  --claude       Claude Code
  --codex        OpenAI Codex
  --agents       Universal ~/.agents/skills (Cline, Zed, Warp, Gemini CLI, …)
  --copilot      GitHub Copilot
  --windsurf     Windsurf
  --roo          Roo Code
  --cline        Cline
  --opencode     OpenCode
  --gemini       Gemini CLI
  -h, --help     Show this help

Examples:
  bash install.sh
  bash install.sh --all
  bash install.sh --claude --codex
  bash install.sh --project --agents
  bash install.sh .cursor/skills/svg-skill

Alternative (skills CLI, 70+ agents):
  npx skills add linyaosky/svg-skill -g -y
EOF
}

agent_path() {
  local agent="$1"
  local scope="${2:-global}"
  case "$agent" in
    cursor)
      [ "$scope" = project ] && echo ".cursor/skills/$SKILL_NAME" || echo "$HOME/.cursor/skills/$SKILL_NAME"
      ;;
    claude)
      [ "$scope" = project ] && echo ".claude/skills/$SKILL_NAME" || echo "$HOME/.claude/skills/$SKILL_NAME"
      ;;
    codex)
      [ "$scope" = project ] && echo ".agents/skills/$SKILL_NAME" || echo "$HOME/.codex/skills/$SKILL_NAME"
      ;;
    agents)
      [ "$scope" = project ] && echo ".agents/skills/$SKILL_NAME" || echo "$HOME/.agents/skills/$SKILL_NAME"
      ;;
    copilot)
      [ "$scope" = project ] && echo ".agents/skills/$SKILL_NAME" || echo "$HOME/.copilot/skills/$SKILL_NAME"
      ;;
    windsurf)
      [ "$scope" = project ] && echo ".windsurf/skills/$SKILL_NAME" || echo "$HOME/.codeium/windsurf/skills/$SKILL_NAME"
      ;;
    roo)
      [ "$scope" = project ] && echo ".roo/skills/$SKILL_NAME" || echo "$HOME/.roo/skills/$SKILL_NAME"
      ;;
    cline)
      [ "$scope" = project ] && echo ".cline/skills/$SKILL_NAME" || echo "$HOME/.cline/skills/$SKILL_NAME"
      ;;
    opencode)
      [ "$scope" = project ] && echo ".agents/skills/$SKILL_NAME" || echo "$HOME/.config/opencode/skills/$SKILL_NAME"
      ;;
    gemini)
      [ "$scope" = project ] && echo ".agents/skills/$SKILL_NAME" || echo "$HOME/.gemini/skills/$SKILL_NAME"
      ;;
    *)
      echo "Unknown agent: $agent" >&2
      return 1
      ;;
  esac
}

list_agents() {
  cat <<'EOF'
Supported agents (global install paths):

  cursor    ~/.cursor/skills/svg-skill
  claude    ~/.claude/skills/svg-skill
  codex     ~/.codex/skills/svg-skill
  agents    ~/.agents/skills/svg-skill     (Cline, Zed, Warp, Gemini CLI, …)
  copilot   ~/.copilot/skills/svg-skill
  windsurf  ~/.codeium/windsurf/skills/svg-skill
  roo       ~/.roo/skills/svg-skill
  cline     ~/.cline/skills/svg-skill
  opencode  ~/.config/opencode/skills/svg-skill
  gemini    ~/.gemini/skills/svg-skill

Project-scoped (--project): same agent keys under the current directory.

Install all:  bash install.sh --all
Skills CLI:   npx skills add linyaosky/svg-skill -g -y
EOF
}

copy_skill() {
  local dest="$1"

  mkdir -p "$dest"

  for f in "${FILES[@]}"; do
    if [ ! -f "$ROOT/$f" ]; then
      echo "Error: missing $f" >&2
      exit 1
    fi
    cp "$ROOT/$f" "$dest/"
  done

  for d in "${DIRS[@]}"; do
    if [ ! -d "$ROOT/$d" ]; then
      echo "Error: missing $d/" >&2
      exit 1
    fi
    rm -rf "$dest/$d"
    cp -R "$ROOT/$d" "$dest/"
  done

  chmod +x "$dest/scripts/validate.sh" 2>/dev/null || true
}

install_to() {
  local dest="$1"
  local label="$2"

  # Expand ~ in custom paths
  case "$dest" in
    "~/"*) dest="$HOME/${dest#\~/}" ;;
  esac

  echo "→ $label"
  echo "  $dest"
  copy_skill "$dest"
  echo ""
}

ALL_AGENTS=(cursor claude codex agents copilot windsurf roo cline opencode gemini)

SCOPE="global"
SELECTED=()
CUSTOM_DEST=""
INSTALL_ALL=false

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --list)
      list_agents
      exit 0
      ;;
    --all)
      INSTALL_ALL=true
      shift
      ;;
    --project)
      SCOPE="project"
      shift
      ;;
    --cursor|--claude|--codex|--agents|--copilot|--windsurf|--roo|--cline|--opencode|--gemini)
      SELECTED+=("${1#--}")
      shift
      ;;
    --*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      CUSTOM_DEST="$1"
      shift
      ;;
  esac
done

if [ -n "$CUSTOM_DEST" ] && { [ "$INSTALL_ALL" = true ] || [ ${#SELECTED[@]} -gt 0 ]; }; then
  echo "Error: custom destination cannot be combined with --all or agent flags" >&2
  exit 1
fi

if [ -n "$CUSTOM_DEST" ]; then
  install_to "$CUSTOM_DEST" "custom"
  echo "Done! Skill installed to:"
  echo "  $CUSTOM_DEST"
  exit 0
fi

if [ "$INSTALL_ALL" = true ]; then
  SELECTED=("${ALL_AGENTS[@]}")
elif [ ${#SELECTED[@]} -eq 0 ]; then
  SELECTED=(cursor)
fi

echo "Installing svg-skill (Agent Skill)..."
echo "  Source: $ROOT"
echo "  Scope:  $SCOPE"
echo ""

# Deduplicate destinations (codex/agents/copilot/opencode/gemini may share .agents/skills)
declare -a DESTS=()
declare -a LABELS=()

for agent in "${SELECTED[@]}"; do
  dest="$(agent_path "$agent" "$SCOPE")"
  label="$agent"

  duplicate=false
  for existing in "${DESTS[@]:-}"; do
    if [ "$existing" = "$dest" ]; then
      duplicate=true
      break
    fi
  done

  if [ "$duplicate" = false ]; then
    DESTS+=("$dest")
    LABELS+=("$label")
  fi
done

for i in "${!DESTS[@]}"; do
  install_to "${DESTS[$i]}" "${LABELS[$i]}"
done

echo "Done! Installed to ${#DESTS[@]} location(s)."
echo ""
echo "Try in your agent:"
echo '  "Draw a 24×24 outline search icon with currentColor"'
echo ""
echo "Or use the skills CLI for more agents:"
echo "  npx skills add linyaosky/svg-skill -g -y"
