# Estate Backend Approach

> **Status: largely implemented.** `POST /estates` now creates a real, durable
> `EstateState` shell (with `county`, executor, etc.) and `GET /estate/{estate_id}`
> reads it back; accounts/auth exist (`agent/auth/`), so estates are no longer purely
> UI-local. Still open from the proposal below: a dedicated
> `POST /estates/{estate_id}/documents` route (uploads still go through
> `/parse-document` / `/parse-documents`), `PATCH /estates/{estate_id}`, and the
> server-derived `setupStatus` / `missingRequiredFields[]` helpers.

This is the recommended backend shape for making newly created estates real, durable
records instead of UI-local state.

## Original Gap (now addressed)

Previously, the frontend could create an estate profile locally, but the agent service did
not know about it until a document was uploaded — the first upload created a blank estate
state and filled missing fields with placeholders like `Unknown Decedent`. `POST /estates`
removes that implicit-creation behavior.

That is fine for a prototype shell, but it creates confusing behavior:

- The Documents page may ask the backend for an estate that does not exist yet.
- The first upload becomes responsible for implicitly creating backend state.
- The backend does not receive the deceased name, date of death, role, relationship,
  county, or executor details from the create-estate modal.
- Deadline rules run against placeholder dates until real appointment data is present.

## Recommended Flow

Add a real create-estate API before upload:

1. Frontend submits the create-estate modal.
2. Web route validates with Zod and proxies to the agent.
3. Agent validates with Pydantic.
4. Agent writes a complete `EstateState` shell to Redis.
5. Frontend switches to the returned estate ID.
6. Uploads only append documents and merge extracted facts into an already-known estate.

## Suggested Agent Routes

```text
POST /estates
GET /estates/{estate_id}
PATCH /estates/{estate_id}
POST /estates/{estate_id}/documents
```

Keep `/parse-document` as a compatibility route during the hackathon, but route the
long-term UI through `/estates/{estate_id}/documents`.

## Suggested Create Payload

```json
{
  "deceasedName": "Test User",
  "dateOfDeath": "2026-06-03",
  "state": "california",
  "county": "Alameda",
  "executor": {
    "name": "Dana Milligan",
    "email": "dana@demo.com"
  },
  "executorRole": "Executor",
  "relationship": "Child"
}
```

`appointmentDate` should be nullable at creation. The app should collect it later from
letters testamentary or manual entry, because many users start setup before appointment.

## Redis Model

Use the existing key pattern:

```text
estate:{estate_id}
estate:{estate_id}:chunks
```

Recommended additions:

- `createdByUserId` once auth exists.
- `county` for probate-referee lookup and court routing.
- `executorRole` and `relationship` for UX copy.
- `setupStatus` for onboarding state, separate from probate `phase`.
- `missingRequiredFields[]` derived server-side from the estate state.

## Contract Rule

Document upload should never create an estate implicitly. If `estateId` does not exist,
the backend should return `404` and the UI should ask the user to create or select an
estate first.
