Review all staged and unstaged git changes, then write a commit message.

Steps:
1. Run `git diff` and `git diff --cached` to see what changed
2. Run `git log --oneline -5` to match this repo's commit style
3. Draft a commit message:
   - Subject line: 50 chars max, imperative mood ("Add X" not "Added X")
   - Blank line, then a body if the change is complex
4. Show me the message and ask for approval before committing

If $ARGUMENTS is provided, use it as context or a hint for the message.