"""All workspace operations belong to the application, not Codex native tools."""

import json

print(
    json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Native tools are disabled. Return structured proposals using the supplied source snapshot.",
            }
        }
    )
)
