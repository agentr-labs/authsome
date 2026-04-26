# Agent SSO Design

## Example Flow: Manoj asks `cold_email` to send an email

**Scenario:** Manoj asks his `cold_email` agent to send an email to a potential client using his Gmail account.

---

### Step 0 — Claim is established

Before the agent does anything, Manoj's identity has to enter the system. The agent cannot self-assert who triggered it — the claim must come from the caller.

Manoj authenticates once at session start and receives a user token. When he triggers the agent, that token travels with the request:

```
Manoj → "send email to client" + user_token(manoj)
```

The agent receives both the task and the user token. It cannot proceed without it. It does not generate or assume the user identity — it only forwards what was explicitly passed.

For a local-first single-user setup, this can be a session established at startup. For multi-user, each caller passes their own token and the agent cannot substitute or forge it.

**Standard:** OAuth 2.0 Token Exchange (RFC 8693) — the agent holds an actor token (its own identity) and a subject token (Manoj's identity). These two are combined into a single principal chain that travels through every subsequent layer.

---

### Step 1 — Identity

The `cold_email` agent loads its Ed25519 private key from the OS keychain. Using its own private key and the user token received from Manoj, it creates a signed principal chain token that carries two things:

- **Actor (agent):** `cold_email`
- **Subject (user):** `manoj`

Both identities are now cryptographically bound together in one token. Every subsequent layer — policy, vault, audit — reads this token to know both who is acting and on whose behalf.

---

### Step 2 — Policy

Before the vault is touched, policy is consulted:

```
can(cold_email, on_behalf_of=manoj, read, manoj/gmail/*) → allow
```

Policy checks the agent identity and the user identity together. If a different agent — say `web_scraper` — tried to access `manoj/gmail/*`, policy would deny it here and nothing else would run. If `cold_email` tried to access `sarah/gmail/*` on behalf of Sarah, that would also be denied — `cold_email` can only access credentials for the user who initiated the request.

---

### Step 3 — Vault

Policy allowed the request. The vault verifies the signed token, confirms it matches the identity registry, then looks up `manoj/gmail/access-token`. It finds the token but the expiry metadata shows it expired 20 minutes ago. The vault surfaces the token and its metadata to the auth layer.

What the vault holds:

```
manoj/gmail/access-token      (expired)
manoj/gmail/refresh-token
manoj/gmail/client-id
manoj/gmail/client-secret
```

Credentials are user-scoped. If Sarah were using the same agent, her credentials would live at `sarah/gmail/*` — completely separate.

---

### Step 4 — Auth

The auth layer receives the expired access token and its associated refresh credentials from the vault. It calls Google's token endpoint with the refresh token, client ID, and client secret. Google returns a fresh access token. The auth layer writes the new token and updated expiry back to the vault, then hands the fresh access token to the agent.

The agent never sees the refresh token, client secret, or anything it doesn't need. It only receives the access token it asked for.

---

### Step 5 — Audit

Every step above is logged:

```
2026-04-20T10:32:01Z | agent=cold_email | user=manoj | policy=allow | resource=manoj/gmail/access-token | outcome=token_refreshed
```

The audit log records the full principal chain — not just which agent acted, but on whose behalf, what they accessed, what happened, and when.

---

### Step 6 — Agent sends the email

The `cold_email` agent uses the fresh Gmail access token to call the Gmail API and sends the email.

---

## Component Responsibilities

### Identity

**What it is:** A stable, cryptographically-bound name for the agent.

**What it does:**
- Generates and holds an Ed25519 key pair on first run
- Stores the private key in the OS keychain
- Registers the public key in a local identity registry
- Receives the user token from the caller (never self-asserts the user identity)
- Combines its own actor token and the caller's subject token into a signed principal chain (actor=agent, subject=user)

**What it does not do:**
- Does not store credentials
- Does not make access decisions
- Does not know about token expiry or OAuth
- Does not generate or assume the user identity — it only signs what was passed in

**Standard:** SPIFFE URI format for agent identity (`agent://local/cold_email`), Ed25519 for the key pair, OAuth 2.0 Token Exchange (RFC 8693) for the actor+subject principal chain.

---

### Policy

**What it is:** The access control layer. Decides what is allowed before anything is retrieved.

**What it does:**
- Evaluates every credential request against a set of rules
- Checks both the agent identity and the user identity together
- Answers one question: `can(agent, on_behalf_of=user, operation, resource) → allow | deny`
- Stops the request immediately if the answer is deny

**What it does not do:**
- Does not store credentials
- Does not refresh tokens
- Does not know about encryption

**Standard:** Cedar (Amazon's policy language) for rules. Simple TOML config as a starting point.

---

### Vault

**What it does:**
- Stores credentials encrypted at rest (API keys, OAuth tokens, connection strings)
- Scopes credentials to a user: `{user}/service/credential-name`
- Verifies the identity token before serving any credential
- Tracks expiry metadata alongside each credential
- Writes updated credentials back when the auth layer refreshes them
- Never serves plaintext credentials to disk

**What it does not do:**
- Does not make access decisions (that is policy's job)
- Does not refresh tokens (that is auth's job)
- Does not know about the agent or user beyond verifying the token

**Standard:** SQLite for storage. libsodium (XSalsa20-Poly1305) for encryption. Vault master key held in OS keychain.

---

### Auth

**What it is:** The credential lifecycle layer. Handles everything related to token validity and acquisition.

**What it does:**
- Detects expired tokens using expiry metadata from the vault
- Refreshes OAuth access tokens using stored refresh credentials
- Handles OAuth acquisition flows (Device Authorization Flow for new credentials)
- Writes refreshed tokens back to the vault
- Returns a usable credential to the agent

**What it does not do:**
- Does not store credentials permanently (that is vault's job)
- Does not make access decisions
- Does not know about agent or user identity beyond what it receives

**Standard:** OAuth 2.0 (RFC 6749) for token flows. Device Authorization Grant (RFC 8628) for browser-less OAuth acquisition.

---

### Audit

**What it is:** An append-only log of every request through the stack.

**What it does:**
- Records every credential access with: timestamp, agent, user, operation, resource, outcome
- Captures the full principal chain (`cold_email` on behalf of `manoj`)
- Records policy decisions (allow and deny)
- Records auth events (token refreshed, token acquired, refresh failed)

**What it does not do:**
- Does not make any decisions
- Does not store credentials
- Does not participate in the request flow — it only observes and records

---

## What Each Layer Owns

| Layer    | Owns                                      | Does not touch                        |
|----------|-------------------------------------------|---------------------------------------|
| Identity | Key pair, signed principal chain token    | Credentials, access rules, tokens     |
| Policy   | Access rules, allow/deny decisions        | Credentials, keys, token lifecycle    |
| Vault    | Encrypted credential storage, expiry data | Access rules, token refresh, identity |
| Auth     | Token refresh, OAuth flows                | Credential storage, access rules      |
| Audit    | Append-only event log                     | Everything else                       |
