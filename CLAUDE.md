# Bharati Investigation Desk

- `backend/` FastAPI server (tests: `cd backend && python -m pytest`), `ios/` SwiftUI app, `docs/`.
- To investigate a case or write/regenerate its report, use the `investigate-case` skill
  (`.claude/skills/investigate-case/SKILL.md`) with `tools/bid_agent.py`. Never bypass the server's
  validation or edit case data directly in the database.
