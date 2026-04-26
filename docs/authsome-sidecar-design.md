# authsome — Sidecar Architecture Design

_Status: Draft · Last updated: 2026-04-23_

---

## What This Is

authsome is evolving from a credential management library into a **sidecar process** — the local auth layer that runs alongside any agent and handles credential injection transparently.

The agent makes plain HTTP requests. authsome intercepts, resolves credentials, injects the right `Authorization` header, and forwards. No auth code in the agent. No credentials in prompts, logs, or model inputs.

```
authsome run -- python cold_email_agent.py
```

That is the entire interface.

---

## The Problem with the Current Pattern

Every agent today does one of these:

- Reads credentials from `.env` — plaintext, unscoped, no rotation
- Hard-codes tokens in system prompts — visible to the model, leaked to logs
- Passes env vars through the chain — no audit trail, no revocation, no scoping

None of these have identity. None of them answer: *which agent, acting on behalf of whom, accessed what, when, and why?*

authsome is the layer that does.

---

## Architecture

authsome is a single installed package (`pip install authsome`) backed by five internal layers. Each layer has a single, bounded responsibility. No layer crosses into another's domain.

```
authsome run -- <agent>
       │
       ▼
   [ sidecar ]            ← authsome process; the only orchestrator
       │
       ├──▶ identity      ← who is acting, on whose behalf
       ├──▶ policy        ← is this allowed
       ├──▶ vault         ← retrieve encrypted credential
       ├──▶ auth          ← refresh if expired
       └──▶ audit         ← record everything
```

The agent talks only to the sidecar via `HTTP_PROXY`. No component exposes a public interface outside of this stack.

---

## Layer Responsibilities

### Sidecar

**Owns:** process lifecycle, subprocess management, proxy wiring, orchestration.

Starts the HTTP proxy. Spawns the agent as a subprocess with `HTTP_PROXY` set to the local proxy address. Intercepts outgoing HTTP requests from the agent. Calls Identity → Policy → Vault → Auth in sequence. Injects the resolved credential into the `Authorization` header. Forwards the authenticated request to the external API. Tears down cleanly when the agent exits.

Does not store credentials. Does not make access decisions. Does not know about encryption.

---

### Identity

**Owns:** agent identity, principal chain token.

Generates an Ed25519 key pair on first run. Stores the private key in the OS keychain. Registers the public key in a local identity registry. Receives the user token from the caller — never self-asserts the user identity. Combines the agent actor token and the user subject token into a single signed principal chain token (`actor=agent, subject=user`).

Standard: SPIFFE URI format (`agent://local/cold_email`), Ed25519, OAuth 2.0 Token Exchange (RFC 8693).

Does not store credentials. Does not make access decisions. Does not know about token expiry.

---

### Policy

**Owns:** access control, allow/deny decisions.

Evaluates every credential request before the vault is touched. Checks both the agent identity and the user identity together. Answers one question:

```
can(agent, on_behalf_of=user, operation, resource) → allow | deny
```

If deny, the request stops here. Nothing else runs.

Standard: Cedar for rules. TOML config as a starting point.

Does not store credentials. Does not refresh tokens. Does not know about encryption.

---

### Vault

**Owns:** encrypted credential storage, expiry metadata.

Verifies the signed principal chain token before serving anything. Retrieves the requested credential from SQLite. Decrypts it in memory using the master key from the OS keychain. Returns the plaintext value plus expiry metadata. Accepts write-back of updated credentials from the sidecar after a refresh. Credentials are user-scoped: `{user}/service/credential-name`.

Standard: SQLite for storage. libsodium XSalsa20-Poly1305 for encryption. Master key held in OS keychain — never written to disk.

Does not make access decisions. Does not refresh tokens. Does not know about the agent or user beyond verifying the token signature.

---

### Auth

**Owns:** token refresh, OAuth acquisition flows.

Receives an expired credential and its associated refresh material — both passed in by the sidecar, sourced from the vault. Calls the external token endpoint. Returns a fresh credential and updated expiry to the sidecar. The sidecar writes the fresh credential back to the vault.

Auth is stateless. It does not call the vault directly. It does not store anything.

Standard: OAuth 2.0 (RFC 6749). Device Authorization Grant (RFC 8628) for browser-less acquisition. PKCE (RFC 7636).

---

### Audit

**Owns:** append-only event log.

Records every request through the stack: timestamp, agent, user, operation, resource, outcome. Captures policy decisions (allow and deny) and auth events (token refreshed, token acquired, refresh failed). Does not make decisions. Does not store credentials. Does not participate in the request flow — it only observes and records.

```
2026-04-23T10:32:01Z | agent=cold_email | user=manoj | policy=allow | resource=manoj/gmail/access-token | outcome=token_refreshed
```

---

## Call Graph

```
agent
  ↓  plain HTTP request (HTTP_PROXY=localhost:7777)
sidecar
  ↓
identity  →  signed principal chain token
  ↓
policy    →  allow / deny
  ↓  (deny: return 403 to agent, stop)
vault     →  encrypted credential + expiry metadata
  ↓  (if expired)
auth      →  fresh credential
  ↓
sidecar   →  vault.write(fresh credential)   ← sidecar handles write-back
  ↓
sidecar injects Authorization header
  ↓
external API
  ↓
audit     ←  append-only log entry at every step
```

### Who calls what

| Component | Calls | Called by |
|---|---|---|
| Sidecar | Identity, Policy, Vault, Auth, Audit | Agent (via HTTP_PROXY) |
| Identity | OS keychain | Sidecar |
| Policy | Nothing | Sidecar |
| Vault | OS keychain (master key) | Sidecar |
| Auth | External token endpoint | Sidecar |
| Audit | Nothing | Sidecar |

The sidecar is the only orchestrator. No internal component calls another directly. This keeps each layer independently testable and the responsibility boundary clean.

---

## Vault Master Key

The vault master key is a 32-byte random value (256 bits) — the exact key size required by XSalsa20-Poly1305.

Generated once at `authsome init`:

```
secrets.token_bytes(32)
```

Stored in the OS keychain as a hex-encoded string (64 characters). Never written to disk. Never logged. Loaded into memory at vault open, used to decrypt credentials in memory, released when the process exits.

The cryptographic separation model: the encrypted SQLite database (the blob) and the master key (the unlock) never coexist on disk. Compromising either alone is not sufficient.

---

## Package Structure

Single package on PyPI. Internal layers as submodules — not separately published, independently testable.

```
authsome/
├── pyproject.toml
├── README.md
├── .python-version
│
├── src/
│   └── authsome/
│       ├── __init__.py
│       ├── cli.py                  # entry point: init, login, run, status, audit
│       │
│       ├── sidecar/
│       │   └── __init__.py         # process lifecycle, subprocess, proxy wiring
│       │
│       ├── identity/
│       │   └── __init__.py         # key generation, principal chain token
│       │
│       ├── policy/
│       │   └── __init__.py         # allow/deny evaluation
│       │
│       ├── vault/
│       │   └── __init__.py         # encrypted storage, keychain integration
│       │
│       ├── auth/
│       │   └── __init__.py         # token refresh, OAuth flows
│       │
│       └── audit/
│           └── __init__.py         # append-only event log
│
└── tests/
    ├── test_identity.py
    ├── test_policy.py
    ├── test_vault.py
    ├── test_auth.py
    ├── test_audit.py
    └── test_sidecar.py
```

---

## CLI Interface

```bash
authsome init                          # generate identity keys, set up vault, store master key in keychain
authsome login <provider>              # OAuth acquisition flow (Device Code / PKCE)
authsome run -- <agent command>        # start sidecar + agent, wire HTTP_PROXY automatically
authsome status                        # show sidecar state, registered identities, vault health
authsome audit                         # tail the audit log
```

`authsome run` is the primary interface. It is the only command most developers will use after initial setup.

---

## Standards Referenced

| Concern | Standard |
|---|---|
| Agent identity format | SPIFFE URI (`agent://local/<name>`) |
| Key pair | Ed25519 |
| Principal chain token | OAuth 2.0 Token Exchange (RFC 8693) |
| Access control rules | Cedar (Amazon) |
| Credential storage | SQLite |
| Encryption at rest | XSalsa20-Poly1305 (libsodium) |
| Master key storage | OS keychain (keyring) |
| Token refresh | OAuth 2.0 (RFC 6749) |
| Browser-less OAuth | Device Authorization Grant (RFC 8628) |
| PKCE | RFC 7636 |

---

## What authsome Is Not

- Not a SaaS secrets manager — fully local, no cloud sync, no vendor dependency
- Not a full agent identity platform — this is the foundational layer; the rest is roadmap
- Not enterprise security software — Alpha, MIT licensed, developer tooling
- Not a replacement for network-level identity (SPIFFE/SPIRE) — complements it at the credential layer

---

## Relationship to Current authsome (v0.1.x)

The current authsome package handles OAuth flows and credential storage — this maps to the **Auth** and **Vault** layers in this design. The sidecar, identity, policy, and audit layers are net new.

The package name (`authsome`) becomes the sidecar — the thing developers install and run. The internal layers are not separately published on PyPI.
