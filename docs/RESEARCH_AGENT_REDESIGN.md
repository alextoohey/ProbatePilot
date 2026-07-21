# ResearchAgent redesign — scoped, not built

**Status:** not started. This is a scoping document for future work, written so it can be
picked up without re-deriving any of the research below. `agent/researcher/research_agent.py`
is untouched — it still does the news-search version described in "Why this exists" below.

## Why this exists

The current `ResearchAgent` (`agent/researcher/research_agent.py`) searches Google News RSS
(`news.google.com/rss/search`) for CA probate-related headlines and keyword-matches them for
relevance. Two real problems:

1. **Unofficial source.** `news.google.com/rss/search` has no published API contract — no key,
   no rate-limit guarantee, no ToS for programmatic use. Google can change or block it at any
   time with zero notice.
2. **No real judgment.** Relevance is plain substring matching (`if "deadline" in text`) with
   zero LLM involvement — despite being called an "agent," it doesn't reason about anything.
   This produces false positives: unrelated news containing words like "deadline" near
   "probate" gets flagged as a possible legal change, and each false positive becomes an
   alert telling a grieving executor "this may affect you, call your attorney."

Also worth knowing: **nothing calls this feature today.** No frontend trigger, no scheduler.
It's fully built and unit-tested but completely disconnected from the live app — same
situation the email notification UI was in before it got gated behind a flag.

## The better approach: ground-truth polling, not news search

Instead of searching for *reports about* changes, poll the actual official CA government
pages this app's own rules already cite, and detect *real* changes directly at the source.

### Verified source patterns (checked live, this session)

**Statutes** — `leginfo.legislature.ca.gov`
- URL pattern: `https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=PROB&sectionNum=NNNN`
- Stable per section. Every section fetched loaded cleanly.
- Ends with a diffable history line, one of two forms:
  - `Amended by Stats. YYYY, Ch. NNN, Sec. NN. Effective January 1, YYYY.`
  - `Enacted by Stats. 1990, Ch. 79.` (original 1990 Probate Code recodification, never
    amended since — sections that haven't changed since enactment show this instead)
- **The whole redesign hinges on diffing this one line per section.**

**Forms** — `courts.ca.gov` / `selfhelp.courts.ca.gov`
- **Important technical caveat, found the hard way**: the form PDFs
  (`courts.ca.gov/documents/deNNN.pdf` or the CDN path
  `courts.ca.gov/sites/default/files/courts/default/<date>/deNNN.pdf`) are **not
  text-extractable via a plain HTTP fetch** — they're encrypted/linearized binary. Don't try
  to read the printed "Rev." date off the PDF directly.
- **Track the HTML self-help page instead**: `selfhelp.courts.ca.gov/jcc-form/DE-NNN`. It has
  a clean `Effective: <date>` line that *is* fetchable as plain HTML/markdown.

### Per-rule source mapping (verified this session)

| rule id | source type | URL | change signal | notes |
|---|---|---|---|---|
| de-140 (petition) | form | `selfhelp.courts.ca.gov/jcc-form/DE-111` | `Effective:` line | Rule evaluates the *Petition*, which is **DE-111**, not DE-140 (DE-140 is the Order). Already fixed the title/citation in code as of this session's bug-fix pass — this table reflects the corrected mapping. |
| letters-testamentary | form + statute | `.../jcc-form/DE-150`; `?lawCode=PROB&sectionNum=8405` | `Effective:` line; history line | Clean |
| de-160 | form + statute | `.../jcc-form/DE-160`; `?...&sectionNum=8800` | `Effective:` line; history line | Clean. §8800 sets the existing 4-month deadline |
| creditor-notice | statute + form | `?...&sectionNum=9051`; `.../jcc-form/DE-157` | history line; `Effective:` line | §9051 = notice timing, exactly what the rule models |
| state-agency-notice | statute | `?...&sectionNum=9202` | history line | **This section was amended effective January 1, 2026 (AB 1521)** — live proof this detector would have caught something real and recent |
| debt-resolution, debt-order | statute | `?...&sectionNum=11420` | history line | Both anchor to the same section (payment priority order) |
| final-distribution | statute | `?...&sectionNum=12200` (also `12201`) | history line | |
| newspaper-notice (not yet an active rule) | statute + form | `?...&sectionNum=8121`; `.../jcc-form/DE-121` | history line; `Effective:` line | Was previously miscited in code comments as §9052 (fixed this session) |
| claim-period (not yet an active rule) | statute | `?...&sectionNum=9100` | history line | |
| estate-ein, estate-bank-account, final-1040, form-1041, death-certificates | — | — | — | Federal (IRS) or purely operational, genuinely out of scope for CA-gov polling |

### Architecture notes for whoever builds this

1. **This needs a real data-model change.** The current `get_research_run_state(estate_id)`
   is scoped *per estate*. But "did CA Probate Code §9202 change" is a **global** fact — it's
   the same answer for every estate, CA-wide. Polling it separately per estate is wasteful
   and can even produce inconsistent results across estates checked on different days. Needs
   a shared "last-known signal per tracked source" store (e.g. `research:source:{section_or_form}`
   → last-seen history/Effective string), checked once, then fanned out to whichever estates'
   rules reference that source when a real diff is detected.
2. **Claude has a real, well-scoped job here**: not "guess if a headline is relevant" (that
   problem goes away — you're diffing the same page, not classifying random news), but "once a
   diff is *confirmed*, summarize what actually changed and what it means for this specific
   rule." That's a legitimately good use of an LLM call, unlike the current keyword-matching
   version which has none.
3. **Keep the existing weekly-wake cadence.** These are government pages with no formal API
   contract — poll them conservatively (weekly, like today), not aggressively.
4. **Error handling**: page structure could drift over time (these aren't versioned APIs).
   Treat a failed extraction as "no signal this run," not a crash, and probably surface it in
   the Phoenix trace so a broken parser gets noticed rather than silently going stale forever.
5. **Rule promotion is separate from this.** Two of the strongest research findings
   (§9202 state-agency-notice, §12200 final-distribution) were already promoted to real
   `CALIFORNIA_PROBATE_RULES` entries this session — they didn't need any of the scraping
   work above, just the same deterministic-rule pattern every other rule already uses. This
   doc is only about the "did the *law itself* change" watcher, not about adding more
   per-estate deadline rules (that's regular, low-risk work — see
   `agent/rules/california_probate.py`).

### Rough effort estimate

~3-4 hours of focused work: registry + two parsers (statute page, form self-help page) +
global-state storage redesign + Claude summarization step + fan-out to affected estates +
tests mocking the HTTP layer (same pattern as the existing `test_research_agent.py`) + error
handling for fetch/parse failures. Not a quick add — treat it as its own deliberate piece of
work, not bundled into something else.

### Lower-confidence candidates not fully verified

A few more real CA probate obligations turned up during research but weren't fully source-verified
— worth a quick look before committing to the full source table above, but not asserted as fact here:
- **DE-174 / §9250 et seq.** (allowance or rejection of a filed creditor claim — deemed rejected
  after 30 days if the PR doesn't act). Statute looks clean; didn't pull the DE-174 form's
  `Effective:` date.
- **BOE-502-D / Rev. & Tax. Code §480** (change-in-ownership statement to the county assessor,
  due within 150 days of death). Real and important, but sits on a *different* CA-gov source
  family — Board of Equalization, not Judicial Council/`courts.ca.gov` — so it doesn't fit the
  two-source pipeline above as cleanly. Would need its own fetch pattern if pursued.
