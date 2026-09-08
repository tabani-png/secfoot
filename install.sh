#!/usr/bin/env bash
# Installs secfoot and registers its skill with Claude Code.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="${HOME}/.claude/skills/sec-footnote-extract"

echo "==> Installing secfoot into ${HERE}"

PY="$(command -v python3 || true)"
if [ -z "${PY}" ]; then
  echo "python3 not found. Install Python 3.11 or newer, then run this again." >&2
  exit 1
fi
"${PY}" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' || {
  echo "Python 3.11 or newer is required. Found: $(${PY} --version)" >&2
  exit 1
}

"${PY}" -m venv "${HERE}/.venv"
"${HERE}/.venv/bin/pip" -q install --upgrade pip
"${HERE}/.venv/bin/pip" -q install -e "${HERE}" pytest
echo "    dependencies installed"

echo "==> Registering the skill at ${SKILL_DIR}"
mkdir -p "${SKILL_DIR}"
sed "s|__SECFOOT_HOME__|${HERE}|g" "${HERE}/SKILL.md" > "${SKILL_DIR}/SKILL.md"
echo "    skill installed"

echo "==> Checking it works (offline tests, no network)"
cd "${HERE}" && "${HERE}/.venv/bin/python" -m pytest -q -m "not live" | tail -1

cat <<NOTE

Done.

One thing left. SEC requires a contact address on every request, so set yours:

    export SEC_USER_AGENT="Your Name, Your Company you@example.com"

Put that line in your ~/.zshrc so it sticks.

Then try it:

    cd ${HERE}
    .venv/bin/python -m secfoot.benchmark_cli --tickers HPQ,CAT \\
      --user-agent "\$SEC_USER_AGENT"

Or just open Claude Code in any folder and ask it for treasury figures from a
10-K. The skill is registered and Claude will find it.
NOTE
