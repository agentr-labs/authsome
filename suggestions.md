# Architecture Deepening Opportunities

## A1. DCR credential side-channel

- **Files:** `flows/dcr_pkce.py:241–248`, `client.py:440–456`, `models/connection.py`
- **Problem:** `DcrPkceFlow.authenticate()` packs dynamically-registered `client_id` and `client_secret` into `ConnectionRecord.metadata` under magic string keys (`_dcr_client_id`, `_dcr_client_secret`). Then `client.login()` unpacks them by those same strings and writes a separate `ProviderClientRecord`. The flow pretends to return one type while secretly encoding a second type inside it. Invisible from the type system; can only be understood by reading both files simultaneously.
- **Solution:** Give flows a richer return type — a `FlowResult` carrying both a `ConnectionRecord` and an optional `ProviderClientRecord`. `login()` receives a single typed object; no unpacking by magic string.
- **Benefits:** The contract between a flow and `login()` becomes explicit and type-checked. Following the DCR credential lifecycle drops from five files to two. Adding a new flow that produces client records is additive.

## A2. `login()` doing five jobs at once

- **Files:** `client.py:292–474`
- **Problem:** The 180-line `login()` method inlines five distinct phases: existing-connection detection, missing-credential bridge prompting (with per-flow field logic), scope resolution, flow dispatch, and post-flow DCR credential extraction. The ordering is load-bearing and non-obvious. The bridge prompting block (lines 354–419) mixes flow-type checks, field construction, and credential persistence into a single pass.
- **Solution:** Extract the bridge prompting into a `_prompt_missing_credentials()` helper that takes a `ProviderDefinition` and flow type and returns a supplemented config. `login()` becomes a coordinator calling three clearly-named helpers in sequence.
- **Benefits:** Each phase gets its own test surface. `login()` is readable in one pass without tracking intermediate state.

## A3. PKCE internals duplicated across three files

- **Files:** `flows/pkce.py`, `flows/dcr_pkce.py`, `flows/bridge.py`
- **Problem:** `_CallbackHandler`, `_generate_pkce()`, and `_find_free_port()` are defined independently in `pkce.py` and `dcr_pkce.py`. `bridge.py` has its own `_find_free_port()`. The proxy (`server.py`) already imports it from `bridge` — the two PKCE flows should too. A bug in the callback handler or PKCE generation must be fixed in two places.
- **Solution:** Extract a `flows/_pkce_utils.py` module (or extend `utils.py`) that owns all three. `DcrPkceFlow` becomes a thin DCR layer over shared mechanics.
- **Benefits:** One fix site for any PKCE protocol bug. `DcrPkceFlow`'s ~110 lines of real DCR logic become visible once the ~180 duplicated lines are removed.

## A4. Store key format split across three modules

- **Files:** `utils.py:build_store_key()`, `client.py:list_connections():228–234`, `store/sqlite_store.py`
- **Problem:** `build_store_key()` constructs keys, but `list_connections()` parses them by hand with `key.split(":")` and index offsets. These are two halves of the same contract with no shared owner. If the key format ever changes, both places need updating. The colon-splitting is fragile against provider or connection names that contain colons.
- **Solution:** Add a `parse_store_key()` companion to `build_store_key()` in `utils.py`, returning a typed `StoreKeyParts` namedtuple. `list_connections()` calls it instead of splitting inline.
- **Benefits:** The key format contract lives in one place. `list_connections()` is testable without caring about the string format. Any key segment rename is a single-file change.

## A5. Token refresh not delegated to flows

- **Files:** `client.py:_refresh_token():998–1082`
- **Problem:** Token refresh is implemented as an 84-line inline HTTP call in `AuthClient`, not in a flow handler. There is no way to override refresh behavior per flow type. Adding per-flow refresh variation (e.g., DCR-registered clients with different semantics, or signed-assertion flows) would require adding flow-type conditionals inside this method.
- **Solution:** Add an optional `refresh()` method to the `AuthFlow` interface with a default implementation covering standard OAuth token refresh. Flows override when needed. `_refresh_token()` delegates to the flow.
- **Benefits:** Refresh behavior gains the same seam as initial auth. Variation is additive (new override) rather than surgical (editing the 84-line method). Refresh is testable at the flow level.

## A6. Crypto backends with duplicated encrypt/decrypt

- **Files:** `crypto/local_file_crypto.py:81–124`, `crypto/keyring_crypto.py:80–123`
- **Problem:** `encrypt()` and `decrypt()` are byte-for-byte identical in both backends (44 lines each). The only difference is how the master key is loaded and persisted. The two classes are not a real seam — they are the same implementation with a different key-storage strategy bolted on.
- **Solution:** Extract a `CryptoCore` mixin or base class that owns the AES-256-GCM logic and takes the key as input. Both backends inherit it and only implement `_load_key()`. Or: collapse both into one class with an injected `KeyStorage` strategy.
- **Benefits:** A change to the encryption scheme (algorithm, IV size, tag handling) is a single edit. Each backend becomes small and visibly distinct.

## A7. `logout()` has inline remote revocation HTTP call

- **Files:** `client.py:logout():571–583`
- **Problem:** `logout()` directly calls `http_client.post(definition.oauth.revocation_url, ...)` inline, the same structural problem as `_refresh_token()`. Remote revocation is protocol-level behavior that flows should own, not `AuthClient`. Adding per-flow revocation variation (e.g., a flow that requires bearer auth on the revocation request) requires editing `client.py`.
- **Solution:** Add an optional `revoke()` method to the `AuthFlow` interface. `logout()` delegates to it when a flow handler exists. The default implementation covers standard RFC 7009 revocation.
- **Benefits:** Revocation, refresh, and initial auth all live at the same seam. `logout()` sheds the direct HTTP dependency and becomes a coordinator.

## A8. `_CallbackHandler` uses class variables as shared mutable state

- **Files:** `flows/pkce.py:37–75`, `flows/dcr_pkce.py:37–75`
- **Problem:** `_CallbackHandler.auth_code`, `.error`, and `.state` are class-level variables reset before each flow run. If two PKCE flows ever run concurrently (e.g., parallel tests), they share this state. The manual reset (`_CallbackHandler.auth_code = None` before the server starts) is not atomic with the server's first request.
- **Solution:** Pass a result container (a `threading.Event` + result dict, or a `queue.Queue`) into `_CallbackHandler` via the HTTP server's `RequestHandlerClass` or a closure. Each flow run gets its own isolated state.
- **Benefits:** PKCE flows become safe to run concurrently. Tests no longer risk cross-contamination. The fix also eliminates the "reset before start" anti-pattern.

## A9. `get_auth_headers()` causes double `get_connection()` per proxied request

- **Files:** `client.py:get_auth_headers():510–543`, `client.py:get_access_token():478–508`
- **Problem:** `get_auth_headers()` calls `get_connection()` directly (line 525), then calls `get_access_token()` which calls `get_connection()` again (line 497). For every intercepted proxy request, the credential record is read from SQLite twice. Combined with `router.py:route()` calling `list_providers()` (disk I/O) and `get_connection()` per matched provider on every request, the hot proxy path makes 3+ SQLite/disk calls per HTTP request with no caching.
- **Solution:** `get_auth_headers()` should call `get_connection()` once and pass the record to an internal helper. Longer term, `RequestRouter` should cache the provider list and connection lookup results with a short TTL.
- **Benefits:** Immediate reduction in SQLite round-trips on the hot path. The router caching fix prevents disk I/O from scaling with request volume.

## A10. `AuthClient` instantiates its concrete dependencies directly

- **Files:** `client.py:crypto:129–137`, `client.py:_get_store():848–855`
- **Problem:** The `crypto` property directly instantiates `LocalFileCryptoBackend` or `KeyringCryptoBackend` based on config. `_get_store()` directly instantiates `SQLiteStore`. There is no seam for injecting test doubles without monkey-patching the concrete classes. Tests in `test_client.py` patch at the module level to work around this, tightly coupling tests to the implementation.
- **Solution:** Accept optional factory callables in `AuthClient.__init__()` (e.g., `store_factory`, `crypto_factory`), defaulting to the current concrete instantiation. Tests pass lightweight in-memory fakes.
- **Benefits:** The seam between `AuthClient` and its subsystems becomes explicit and testable without monkey-patching. Integration and unit test distinctions become intentional rather than accidental.

## A11. `OAuthConfig.registration_endpoint` is a DCR-only field in the general model

- **Files:** `models/provider.py`, `flows/dcr_pkce.py:305–307`
- **Problem:** `OAuthConfig` carries `registration_endpoint` — a field that only has meaning when `flow == DCR_PKCE`. All other flows ignore it. The field is also the only one in `OAuthConfig` that is specific to a single flow type. If more flow-specific fields are added (e.g., device flow parameters), `OAuthConfig` becomes a growing catch-all.
- **Solution:** Move `registration_endpoint` into a `ClientRegistrationConfig` sub-model nested under the provider definition, only present when needed. The DCR flow reads it from there; other flows never see it.
- **Benefits:** `OAuthConfig` stays bounded to fields shared across OAuth flows. Flow-specific configuration has an obvious home. Adding new flow-specific config is additive rather than widening the shared model.

## A12. `CredentialStore` has no batch operations — `revoke()` and `list_connections()` make N round-trips

- **Files:** `store/base.py`, `client.py:revoke():599–641`, `client.py:list_connections():210–257`
- **Problem:** The `CredentialStore` interface only offers single-record `get`, `set`, and `delete`. `revoke()` loops over connection names calling `logout()` → `store.delete()` per connection — not atomic. `list_connections()` calls `store.get()` N times in a loop, one SQLite query per connection. Neither operation has any atomicity guarantee at the store level; a crash mid-revoke leaves partial state.
- **Solution:** Add `get_many(keys)` and `delete_many(keys)` to the `CredentialStore` interface with a SQLite implementation that uses a single transaction. `revoke()` and `list_connections()` use them.
- **Benefits:** `list_connections()` becomes a single SQLite query regardless of connection count. `revoke()` becomes atomic — either all connections are deleted or none are. The interface better reflects how callers actually use the store.

---

# CLI Design Suggestions

## 1. Rename `revoke` → `reset`

Current three commands cover different blast radius but naming doesn't signal this clearly:

| Current | Proposed | Blast radius |
|---------|----------|-------------|
| `logout` | `logout` | One connection's local state |
| `revoke` | `reset` | All connections + client secrets for a provider |
| `remove` | `remove` | Provider definition itself |

The word "revoke" implies a remote call that doesn't happen. "reset" maps better to "full local reset of a provider". Escalation becomes obvious: logout → reset → remove.

## 2. `--show-secret` needs a harder gate

Printing secrets to stdout is dangerous: shell history capture, shoulder surfing, screen recordings, accidental log piping.

Proposed guardrails:
- Require passkey/OS authentication confirmation before revealing secrets (e.g. Touch ID / system keychain prompt)
- Print a prominent stderr warning before output: `"WARNING: Secret printed to stdout. Run: history -d <n> to remove from shell history."`
- For agents: docs should explicitly state to use `authsome run` instead of `get --show-secret`

## 3. `export` is a fallback, not a first-class feature

`eval "$(authsome export ...)"` injects secrets into the shell for the entire session — inherited by all child processes, not scoped to the provider that needs them.

Proposed:
- Print a stderr warning when `export` is used: `"Note: secrets are now in your shell environment. Prefer 'authsome run' for scoped injection."`
- Docs and skill should position `export` as a last resort, not Option A
- `run` docs should list known SDKs/tools that don't respect `HTTP_PROXY` so users know when they're forced to fall back

## 20. Headless API key import via provider-declared env var

Each API key provider definition should declare its canonical env var (e.g. `OPENAI_API_KEY`). `login` logic should:

1. Check the provider's declared env var first
2. If set — import it silently, no browser interaction needed (headless CI path)
3. If not set — fall back to browser bridge (interactive path)
4. Apply same logic when already connected — if env var is present and differs from stored value, re-import it

This removes the need for any `--from-env` flag. CI pipelines set their standard env vars as usual; `authsome login openai` just works. The provider definition is the single source of truth for which env var maps to which provider.

Requires adding `env_var` field to `ApiKeyConfig` in the provider model.

## 19. Expand `inspect` to include connection summary

Current: `inspect <provider>` only dumps the provider definition schema. Docstring claims it also returns "local connection summary" — it doesn't.

Proposed: include a `connections` block in `inspect` output showing all connections for that provider — names, statuses, expiry, auth type. This makes `inspect` a one-stop command to understand a provider's full local state without needing `list` + `get`.

## 18. Fixed callback port 7999 — local race condition *(accepted trade-off)*

Callback server binds to fixed port `127.0.0.1:7999`. A local process could race to hit the callback before the real browser. State parameter validation mitigates external CSRF but not a privileged local attacker.

Fixed port is intentional — required for OAuth redirect URI pre-registration (`http://127.0.0.1:7999/callback`). Security risk accepted as a reasonable trade-off for convenience.

## 17. `login` — configurable auth flow timeout *(minor)*

PKCE callback timeout is hardcoded at 300s. No way for users or CI pipelines to set a tighter bound.

Add `--timeout <seconds>` to `login`. Default stays 300s for humans; CI pipelines can set a shorter value to fail fast instead of blocking a job slot.

## 16. Proxy `ssl_insecure=True` must be revisited

`start_proxy_server` sets `ssl_insecure=True` on mitmproxy options. This disables SSL certificate verification on outbound connections from the proxy, making it susceptible to MITM on its own outbound leg — the exact attack authsome is trying to prevent.

Likely added to handle the proxy's own HTTPS interception flow, but needs a surgical fix: verify server certs on outbound while still intercepting inbound. Must be revisited before any production/security-sensitive use.

## 15. Master key rotation — `authsome rekey` *(roadmap)*

`master.key` is generated once at `init` and never rotated. If compromised, all stored credentials are exposed permanently.

`authsome rekey` should: generate a new master key, re-encrypt all connection records in place, atomically swap the key file. Essential for users who suspect key exposure.

## 14. `run` — optional `--provider` scoping *(post-MVP)*

Current behavior: proxy injects for all connected providers whose `host_url` matches — intentional, acts as automatic policy.

Future: add optional `--provider` flag (repeatable). Behavior: if `--provider` is specified, scope injection to those providers only; otherwise inject all matched providers. This preserves backward compatibility and adds least-privilege opt-in.

```bash
authsome run --provider github -- python script.py   # scoped
authsome run -- python script.py                     # all matched (current)
```

## 13. Expand `whoami` *(high priority)*

Current `whoami` only shows home directory and encryption mode — too sparse to be useful for debugging or orientation.

Should also show:
- Active profile name
- Connected provider count (and list of connected provider names)
- Authsome version
- Encryption backend in use (local key vs keyring)

`whoami` should be the first command anyone runs when something's wrong.

## 12. `doctor` — additional checks for future versions

Current checks are sufficient for v1/alpha. Future versions should add:

- **File permissions:** `master.key` and `store.db` should be `0600` — fail loudly if world-readable
- **Profiles count bug:** `profiles_count` is an integer but treated as boolean; 0 profiles on a fresh install shows `FAIL` incorrectly
- **Connected providers:** warn if no providers have active connections
- **Proxy connectivity:** basic reachability test against registered provider `host_url`s
- **Key age:** warn if master key hasn't been rotated in >N days
- **Store integrity:** detect corrupted or locked SQLite db
- **Version compatibility:** check if authsome version matches the schema version in `config.json`

## 11. Exit code coverage *(post-MVP)*

Exit code set is stable for MVP/alpha. New error types added post-MVP should each get a dedicated exit code. Exit code map should be part of the versioned spec, not added ad-hoc. Code `1` (generic) should eventually be a last resort only.

New codes needed when implemented:
- Connection already exists (from suggestion #5)
- Provider already registered
- Endpoint unreachable (from suggestion #6)

## 10. Show `expires_at` in `list` output *(minor)*

`list` shows connection status but not expiry time. Agents starting long-running jobs can't tell if a token is about to expire.

`expires_at` should be included in `list` JSON output and shown human-friendly in terminal output (e.g. `expires in 47m`). Proxy handles refresh automatically so this is informational only.

## 9. Refresh failure handling

When token refresh fails but a fallback token is still valid, the failure is silent. This delays the inevitable and leaves agents unaware that re-authentication is needed.

At minimum: log a warning when refresh fails regardless of fallback availability. Broader refresh failure handling strategy to be defined later.

## 8. JSON output schema versioning *(post-MVP, spec-tracked)*

`--json` output has no version field or stability contract. Internal Pydantic model changes automatically become breaking API changes for agents parsing the output.

Planned: spec versioning system will govern JSON output shape. Each response should include `"v": 1`. Output shape per command should be explicitly documented and decoupled from internal model field names.

## 7. Audit logging — must have

Every credential access, injection, and mutation should be logged to a local audit trail at `~/.authsome/audit.log`. This is critical for both human and agent use — when a token leaks or an agent misbehaves, you need to know what was accessed and when.

**What to log (append-only, structured JSON lines):**

| Event | Fields |
|-------|--------|
| `login` | timestamp, provider, connection, flow, success/failure |
| `logout` / `reset` / `remove` | timestamp, provider, connection, actor (human/agent) |
| `get --show-secret` | timestamp, provider, connection, field accessed |
| `export` | timestamp, provider, connection, format |
| `run` — proxy injection | timestamp, provider, matched host, request method+path |
| `run` — proxy miss (no match) | timestamp, host, reason |
| `register` | timestamp, provider name, endpoints registered |

**Properties:**
- Append-only file, never truncated by authsome itself
- Structured JSON lines (one event per line) for easy `grep`/`jq` parsing
- No secret values logged — only metadata
- `authsome log` command to tail/filter the audit log
- `--no-audit` flag to suppress for specific commands (with a warning)
- Proxy injection misses logged to stderr in real time so users see silent failures immediately

## 6. `register` should confirm endpoints and smoke-test the provider *(low priority)*

`register` currently loads and schema-validates the JSON but does nothing to surface the trust decision to the user. A malicious provider file could point `token_url` at an attacker-controlled server.

Proposed:
- Print key endpoints and prompt confirmation before registering: `"Register 'my-service' with token endpoint https://...? [y/N]"` (skipped in `--json`/`--quiet` mode)
- After registration, run a basic connectivity test against the discovered endpoints (e.g. HEAD request to `host_url`, reachability check on `authorization_url`) and warn if anything is unreachable
- Fail loudly if endpoints look suspicious (non-HTTPS, localhost, IP addresses)

## 5. `login` should be idempotent — no-op if already connected

Current behavior: `login --force` silently overwrites with only a yellow warning. Default `login` re-auths unconditionally.

Proposed: `login` should be a no-op if a valid connection already exists — succeed silently and exit 0. This fixes both human and agent cases:

- **Humans** don't accidentally overwrite a valid connection
- **Agents** can call `login` unconditionally without orchestrating SEARCH → LOGIN logic

To re-authenticate, the explicit path is `logout` then `login`. `--force` can remain for non-interactive scripts that need to overwrite without a prior logout.

## 4. `--profile` CLI support (intentionally deferred)

`AuthClient` fully supports profiles internally but the CLI exposes none of it. Deferred to avoid confusion at this stage.

Future: expose `--profile <name>` as a global flag + `profile` subcommand group (`list`, `create`, `switch`, `delete`) once the core UX is stable.
