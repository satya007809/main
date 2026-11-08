# Using your Claude plan (Max) instead of API credits

A custom app cannot sign in with a Claude Pro/Max subscription, and the Claude API is billed separately.
Claude Code, however, is part of your Claude plan. In **Claude-plan mode** the server makes no AI calls:

```
iPhone app ──► Server: Drive scan, inventory, storage, validation, Word report building
                  ▲
                  │ tools/bid_agent.py  (HTTPS + your access token)
                  │
Claude Code (Claude app → Code, on your plan): reads pages and photos, applies your playbooks,
                  submits the analysis and report text. The server checks everything and rejects anything unsupported.
```

The safeguards are the same as in API mode: the same validator, the same rule that unverified external
checks stay pending, and the same page limit and report builder. Each analysis records
`Claude Code (Claude subscription)` as its model, together with the playbook versions used.

## One-time setup

1. **Server**: in `backend/.env` set

   ```
   BID_AI_MODE=claude_code
   ```

   No `ANTHROPIC_API_KEY` is needed. Restart the server.
2. **Access token**: iPhone app → Settings → *Claude Code access* → **Create access token** → Copy. It is
   shown only once and can be revoked by swiping it away.
3. **Claude Code environment** (claude.ai → Code, or the Code tab in the Claude iPhone app). Open the
   environment settings (the environment menu in a session's title bar → Edit) for the environment you
   use with this repository:
   * **Network access**: add your server's host (e.g. `api.your-domain.in`) under *Allowed domains*.
   * **Network secrets** (shown as *API credentials* in older app versions): add the token for that host as
     `Authorization: Bearer <token>`. If that section isn't offered, add an environment variable
     `BID_AGENT_TOKEN=<token>` instead.
   * **Environment variable**: `BID_SERVER_URL=https://api.your-domain.in`.

   Never paste the token into a chat message.
4. Start a Claude Code session on this repository. The `investigate-case` skill and `tools/bid_agent.py`
   are included in the repository, so there is nothing else to install.

## Daily use

1. In the iPhone app create the case, paste the Drive link and scan as usual.
2. Tap **Investigate in Claude Code** and copy the instruction. It looks like
   *"Use the investigate-case skill to investigate case CLM/OD/2026/7788 (case id …) and write its Word report, page limit 7."*
3. Paste it into a Claude Code session and send. Claude Code then:
   * reads scanned pages and photos, including Telugu, Kannada, Hindi and other regional languages;
   * applies your global rules and the case playbooks;
   * submits its analysis and corrects it until the server accepts it;
   * writes the report text and fits it to the page limit.
4. Back in the iPhone app, pull to refresh. Findings and the new Word report appear on the case.
5. After adding field notes or verification results, tap **Rerun in Claude Code** and repeat.

## Limits to keep in mind

* Large cases (many scanned pages or photos) use more of your plan's usage allowance. If you hit the
  limit, continue the same session later; work already submitted is kept on the server.
* Each case needs one Claude Code conversation. It isn't a one-tap button inside the iPhone app.
* To switch to fully automatic mode later, set `BID_AI_MODE=api` and add an `ANTHROPIC_API_KEY`. No other
  change is needed.
