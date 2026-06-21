# Browserbase — Property Value Auto-Lookup

**Status**: Not yet integrated. Revisit after core pipeline is working end-to-end.  
**Owner**: TBD (likely Member 3 — fits naturally into the DeadlineAgent tool set)  
**Estimated build time**: 2–3 hours once the core is stable  
**Dependencies**: `browserbase`, `playwright`, existing `agent/llm/claude.py`

---

## What This Solves

One of the two live demo alerts is:

> **CRITICAL — DE-160 Inventory & Appraisal due in 9 days**  
> *No appraisal uploaded for: 1847 Marin Ave, Berkeley CA | 2019 Honda Civic*

Right now the estate has `appraised: false` on two assets and no value attached. An executor in the real world would spend hours on the phone or the web trying to get rough figures before hiring a certified appraiser.

Browserbase lets the DeadlineAgent go get that estimate itself — navigating to Zillow or the county assessor, pulling a current value, and attaching it to the asset. The alert softens from CRITICAL ("no data at all") to WARNING ("estimate found, certified appraisal still required").

**Demo beat this enables:**  
*"ClearPath didn't just tell Dana the appraisal was missing — it looked it up."*

---

## Where It Fits in the Architecture

The cleanest integration point is as a **tool exposed to the DeadlineAgent**. The agent already runs a Claude tool-use loop (`agent/agents/deadline_agent.py`). Adding `lookup_property_value` as one of its tools means:

1. Claude sees an asset with `appraised: false` and `type: real_estate`
2. Claude decides to call `lookup_property_value(address="1847 Marin Ave, Berkeley CA")`
3. Browserbase opens a headless browser, navigates to the county assessor / Zillow
4. Claude Vision reads the page screenshot and extracts the value
5. The tool returns `{ estimated_value: 1240000, source: "Zillow Zestimate", retrieved_at: "..." }`
6. Claude incorporates this into its alert reasoning: "estimate found, certified appraisal still needed"
7. The asset is updated in Redis with `estimated_value` populated

This is also a strong Anthropic track story: Claude reasoning about what data it needs, going to get it, then incorporating the result into its analysis.

Alternatively (simpler): a standalone `POST /enrich/property-value` endpoint that Member 4 calls from the UI when the user clicks "Look up estimate." Pick based on time available.

---

## File to Create

```
agent/
└── tools/
    └── property_lookup.py    ← New file
```

---

## Dependencies

```toml
# Add to pyproject.toml (agent/)
browserbase = "*"          # Browserbase Python SDK
playwright = "*"           # Playwright for browser control
```

```bash
uv add browserbase playwright
playwright install chromium
```

New environment variable in `agent/.env`:
```bash
BROWSERBASE_API_KEY=
BROWSERBASE_PROJECT_ID=
```

---

## Implementation

### `agent/tools/property_lookup.py`

```python
import os
import base64
from datetime import datetime, timezone
from browserbase import Browserbase
from playwright.sync_api import sync_playwright
from pydantic import BaseModel

bb = Browserbase(api_key=os.environ["BROWSERBASE_API_KEY"])


class PropertyLookupResult(BaseModel):
    address: str
    estimated_value: int | None
    source: str
    confidence: str          # "high" | "medium" | "low"
    notes: str
    retrieved_at: str


def lookup_property_value(address: str) -> PropertyLookupResult:
    """
    Open a headless browser via Browserbase, navigate to the Alameda County
    Assessor and/or Zillow, screenshot the result, and feed it to Claude Vision
    to extract the property value.

    Using Claude Vision to read the page (rather than CSS selectors) makes this
    robust to layout changes — a selector-based scraper breaks the moment the
    site redesigns; Claude reads the page like a human.
    """
    session = bb.sessions.create(
        project_id=os.environ["BROWSERBASE_PROJECT_ID"]
    )

    screenshot_b64 = None
    page_text = ""
    source_url = ""

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(session.connect_url)
        context = browser.new_context()
        page = context.new_page()

        # Try Alameda County Assessor first (official, less bot-detection)
        # Covers Berkeley / Oakland / Alameda County addresses
        try:
            page.goto("https://assessor.acgov.org/assessor/assr/index.jsp", timeout=15000)
            page.wait_for_load_state("networkidle")
            # Fill in the address search form
            page.fill("input[name='address']", address)
            page.keyboard.press("Enter")
            page.wait_for_load_state("networkidle")
            screenshot_bytes = page.screenshot(full_page=True)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
            source_url = page.url
        except Exception:
            pass

        # Fallback: Zillow
        if not screenshot_b64:
            try:
                encoded = address.replace(" ", "-").replace(",", "").lower()
                page.goto(f"https://www.zillow.com/homes/{encoded}_rb/", timeout=15000)
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(2000)   # let JS render the Zestimate
                screenshot_bytes = page.screenshot(full_page=False)
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
                source_url = page.url
            except Exception:
                pass

        browser.close()

    if not screenshot_b64:
        return PropertyLookupResult(
            address=address,
            estimated_value=None,
            source="lookup_failed",
            confidence="low",
            notes="Could not reach county assessor or Zillow. Manual appraisal required.",
            retrieved_at=datetime.now(timezone.utc).isoformat(),
        )

    # Feed the screenshot to Claude Vision to extract the value
    from agent.llm.claude import client  # Member 1's Anthropic client

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": screenshot_b64,
                    },
                },
                {
                    "type": "text",
                    "text": f"""This is a screenshot of a property listing or assessor page for:
{address}

Extract the property value (Zestimate, assessed value, or listed price) from this page.
Return JSON only, no other text:
{{
  "estimated_value": <integer in dollars, or null if not found>,
  "source_label": "<what the page calls this value: Zestimate / Assessed Value / List Price / etc>",
  "confidence": "<high if a clear dollar figure is shown, medium if approximate, low if not found>",
  "notes": "<any caveats — e.g. assessed value may differ from market value>"
}}"""
                }
            ]
        }]
    )

    import json
    try:
        raw = response.content[0].text.strip()
        data = json.loads(raw)
    except Exception:
        data = {"estimated_value": None, "source_label": "parse_error", "confidence": "low", "notes": "Claude could not parse the page."}

    source_label = data.get("source_label", "web_lookup")
    source = f"{source_label} via {source_url.split('/')[2]}" if source_url else source_label

    return PropertyLookupResult(
        address=address,
        estimated_value=data.get("estimated_value"),
        source=source,
        confidence=data.get("confidence", "low"),
        notes=data.get("notes", ""),
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )
```

---

## Wiring Into the DeadlineAgent Tool Loop

In `agent/agents/deadline_agent.py`, add this to the tools list passed to Claude:

```python
from agent.tools.property_lookup import lookup_property_value, PropertyLookupResult

TOOLS = [
    # ... existing tools (evaluate_rule, get_estate_state, etc.)
    {
        "name": "lookup_property_value",
        "description": (
            "Look up the current estimated market value of a real estate asset "
            "using public sources (county assessor, Zillow). Call this when you "
            "see a real_estate asset with appraised=false and no estimated_value. "
            "Returns an estimate and source — note this is NOT a certified appraisal "
            "and does not satisfy DE-160 requirements, but it gives the executor a "
            "working figure and should be recorded on the asset."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Full street address of the property, e.g. '1847 Marin Ave, Berkeley CA'"
                }
            },
            "required": ["address"]
        }
    }
]

# In the tool execution handler:
def execute_tool(tool_name: str, tool_input: dict):
    if tool_name == "lookup_property_value":
        result = lookup_property_value(tool_input["address"])
        # Also write the estimate back to estate state
        # redis_client.update_asset_value(estate_id, address=tool_input["address"], value=result.estimated_value)
        return result.model_dump()
    # ... other tools
```

---

## What Changes in the Demo

**Before Browserbase:**
> CRITICAL: DE-160 due in 9 days. No appraisal uploaded. 1847 Marin Ave unvalued.

**After Browserbase:**
> WARNING: DE-160 due in 9 days. Zillow Zestimate for 1847 Marin Ave: **$1,240,000** (retrieved 2026-06-20). A certified appraisal is still required — contact a probate referee.

The alert goes from "you're flying blind" to "here's your starting number, here's your next step." That's the product promise in one interaction.

---

## Risks and Caveats

| Risk | Mitigation |
|------|-----------|
| Zillow blocks headless browsers | Try county assessor first; Browserbase's residential IPs reduce detection risk |
| Page layout changes break extraction | Claude Vision reads the page like a human — resilient to selector changes |
| Browserbase session timeout during demo | Keep sessions short; close immediately after screenshot |
| County assessor only covers Alameda County | For the hackathon, 1847 Marin Ave Berkeley is Alameda County — fine. Generalize post-hackathon. |
| Value is an estimate, not a certified appraisal | Always label it as such in the UI and in the alert body. Never say "appraised." |
| Adds latency to the DeadlineAgent run | Run property lookup only when `appraised=false` and no `estimated_value` exists. Cache result on the asset. |

---

## Build Order (When You Revisit This)

1. Sign up for Browserbase, get API key + project ID
2. `uv add browserbase playwright && playwright install chromium`
3. Add env vars to `agent/.env`
4. Build and manually test `property_lookup.py` against the demo address
5. Add the tool definition to the DeadlineAgent tools list
6. Add tool execution handler
7. Test: seed demo estate → run DeadlineAgent → confirm it calls the tool and the alert updates
8. Wire the estimate value back to the asset in Redis so it persists
9. Update the AlertBanner in the frontend to show the source label and retrieval date
