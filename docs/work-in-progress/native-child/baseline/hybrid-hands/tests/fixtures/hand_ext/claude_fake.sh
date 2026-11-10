#!/bin/sh
# Fake claude: --version and `auth status --json`; FAKE_CLAUDE_LOGGED_IN=1 -> logged in.
if [ "$1" = "--version" ]; then echo "2.1.318 (Claude Code)"; exit 0; fi
if [ "$1" = "auth" ]; then
  if [ "$FAKE_CLAUDE_LOGGED_IN" = "1" ]; then
    echo '{"loggedIn":true,"authMethod":"claude.ai","email":"secret-hand@example.com","orgId":"SECRET-ORG"}'; exit 0
  fi
  echo '{"loggedIn":false,"authMethod":"none"}'; exit 1
fi
exit 2
