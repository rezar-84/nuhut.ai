"""The loop commands as Agent Skills: one converter for the installer and the runtime.

Claude Code lists the loop's entry points as commands (.claude/commands/sdlc-*.md). Tools
that list skills instead (Antigravity's / menu, Codex, Cursor, Gemini CLI, Copilot) read
the same text as .agents/skills/<name>/SKILL.md. `install.py` and `sdlc.py repair
--shared-skills` both generate those files through command_to_skill_text(), so there is
one source. sdlc-doctor is not a loop skill: optional/skills/ already ships a skill by
that name.

Zero third-party dependencies (Python 3.8+ stdlib).
NOTE: Must never contain two literal opening curly braces in a row.
"""

import json
import re

LOOP_SKILLS = ("sdlc-plan", "sdlc-build", "sdlc-verify", "sdlc-review", "sdlc-finish", "sdlc-log")
LOOP_SKILL_WHEN = {
    "sdlc-plan": "Use when the user invokes /sdlc-plan or asks to plan, frame or scope a "
                 "change, or when a new request needs a tracked work item and a reviewed "
                 "plan before any code is written.",
    "sdlc-build": "Use only when the user invokes /sdlc-build or explicitly asks to build "
                  "or implement a plan that is already approved. Never on your own "
                  "initiative: building without an approved plan is what this loop exists "
                  "to prevent.",
    "sdlc-verify": "Use when the user invokes /sdlc-verify or asks to run the checks, and "
                   "before claiming that anything passes, works or is done.",
    "sdlc-review": "Use when the user invokes /sdlc-review or asks for a review of a plan "
                   "or a change, and when a plan or a diff reaches a review gate.",
    "sdlc-finish": "Use when the user invokes /sdlc-finish or asks to finish, close or wrap "
                   "up a work item that is built, and when the finish guard names an item "
                   "this session left open.",
    "sdlc-log": "Use when the user invokes /sdlc-log or asks to close, log or wrap up a "
                "work item that is built, verified and reviewed.",
}


def command_to_skill_text(name, cmd_text):
    """Rewrite the loop command <name> (the text of its .md file) as an Agent Skills
    SKILL.md: name and description in the frontmatter, the argument placeholder turned
    into prose, and references to other commands turned into references to their skills.
    Installer placeholders in <cmd_text> are left as they are."""
    m = re.match(r"^---\n(.*?)\n---\n", cmd_text, re.S)
    meta, body = {}, cmd_text
    if m:
        body = cmd_text[m.end():]
        for line in m.group(1).splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"')
    hint = meta.get("argument-hint", "")
    body = body.replace(
        "$ARGUMENTS",
        "the request given with this skill: the text after its name, or the request in the "
        "conversation that called for it" + (" (expected: `%s`)" % hint if hint else "") + ".")
    body = re.sub(r"`/(sdlc-[a-z-]+)`", r"the `\1` skill", body)
    description = "%s. %s" % (meta.get("description", name).rstrip("."),
                              LOOP_SKILL_WHEN.get(name, ""))
    return ("---\nname: %s\ndescription: %s\n---\n\n"
            "<!-- Generated from the kit's optional/claude-commands/%s.md by install.py. "
            "Kit-managed: change the kit, not this file. -->\n%s"
            % (name, json.dumps(description, ensure_ascii=False), name, body))
