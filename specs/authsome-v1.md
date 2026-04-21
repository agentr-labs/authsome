# Portable Specification: Local Auth Library + CLI

## 1. Purpose

This document defines a portable, language-agnostic specification for a local authentication library and CLI that lets humans, agents, and developer tools manage third-party credentials in a consistent way.

The system is designed so that:

- a Python implementation and a JavaScript implementation can follow the same logic,
- both implementations can read and write the same credential store,
- providers can be registered in a shared format,
- credentials can be retrieved, refreshed, revoked, exported, and injected consistently,
- the system remains local-first and embeddable.

This spec describes the behavioral contract, filesystem layout, data models, provider schema, CLI contract, and library contract.

It does not prescribe one specific framework, database, HTTP client, or encryption library.

---

## 2. Product Definition

The product consists of two surfaces.

### 2.1 Library
A language SDK that allows applications, CLIs, agents, servers, and tools to:

- discover registered providers,
- initiate authentication,
- retrieve credentials,
- refresh tokens,
- revoke connections,
- remove local credentials,
- export credentials into runtime environments,
- build authenticated request headers.

### 2.2 CLI
A terminal interface that allows humans and agents to:

- list providers,
- log in to a provider,
- revoke provider credentials,
- remove local provider credentials,
- inspect provider metadata,
- export credentials,
- run commands with injected credentials,
- register new providers.

Profile management is optional because the default operating mode uses profile `default` unless explicitly specified.

---

## 3. Design Principles

1. **Portable**  
   Multiple implementations in different languages must be able to interoperate using the same local store and schemas.

2. **Local-first**  
   The default mode is local storage and local execution. Hosted sync is out of scope for this spec.

3. **Provider-aware**  
   Authentication is modeled per provider rather than as generic secret blobs.

4. **Safe by default**  
   Commands should return metadata by default, not raw secrets.

5. **Machine-friendly**  
   All CLI commands should support structured output.

6. **Human-friendly**  
   Common tasks should have simple verbs and predictable semantics.

7. **Extensible**  
   New auth types, providers, and metadata should be addable without breaking compatibility.

---

## 4. Core Concepts

### 4.1 Provider
A provider defines how to authenticate against a third-party system.

Examples:
- github
- google
- slack
- notion
- openai
- anthropic

A provider definition includes:
- provider identity and display metadata,
- auth type,
- flow configuration,
- endpoint metadata,
- default scopes,
- export behavior.

### 4.2 Profile
A profile is a local credential namespace.

The default profile name is always:
- `default`

Implementations MUST assume profile `default` unless the caller explicitly specifies another profile.

Examples of non-default profiles:
- work
- personal
- agent-prod

A profile contains provider metadata, provider state, OAuth client credentials, and zero or more named connections per provider.

### 4.3 OAuth Client Config
An OAuth client config is the saved OAuth client credentials for a provider within a profile.

There is one client config per provider per profile.

An OAuth client config contains:
- `client_id`
- `client_secret`
- optional redirect URI or registration metadata

OAuth client credentials are sensitive provider configuration and MUST be stored encrypted at rest.

### 4.4 Connection
A connection is a named credential instance for a provider within a profile.

A single provider MAY have multiple connections inside the same profile.

Examples:
- profile `default` with provider `github` and connection `default`
- profile `default` with provider `github` and connection `work`
- profile `work` with provider `google` and connection `corp-admin`

A connection is uniquely identified by:
- `profile_name`
- `provider_name`
- `connection_name`

### 4.5 Credential Record
A credential record is the normalized local state associated with one named connection.

### 4.6 Auth Type
The auth mechanism used by a provider.

Initial auth types in this spec:
- `oauth2`
- `api_key`

### 4.7 Flow Type
The specific authentication flow.

Initial flow types in this spec:
- `pkce`
- `device_code`
- `dcr_pkce`
- `api_key`

---

## 5. Filesystem Layout

The default root directory is:

```text
~/.authlib/
```

Portable implementations MUST support overriding this root with an environment variable and/or explicit configuration.

Recommended override environment variable:

```text
AUTHLIB_HOME
```

### 5.1 Directory Structure

```text
~/.authlib/
  version
  config.json
  providers/
    github.json
    google.json
    slack.json
    custom-acme.json
  profiles/
    default/
      store.db
      metadata.json
      lock
```

### 5.2 Required Files

#### `version`
A plain text file containing the store format version.

Example:

```text
1
```

#### `config.json`
Global implementation-independent settings.

#### `providers/*.json`
Portable provider definitions.

#### `profiles/<name>/store.db`
The credential store backing a profile.

This may be implemented using a key-value engine, SQLite-backed KV layer, or equivalent, as long as behavior and serialization remain compatible.

#### `profiles/<name>/metadata.json`
Profile metadata.

#### `profiles/<name>/lock`
Optional lock file used to coordinate concurrent writes.

---

## 6. Data Serialization Rules

To ensure cross-language compatibility:

1. All structured metadata MUST be serialized as UTF-8 JSON.
2. Timestamps MUST use RFC 3339 / ISO 8601 in UTC.
3. Binary encrypted payloads MUST be encoded as base64 when embedded in JSON.
4. Unknown fields MUST be preserved when possible.
5. Implementations MUST ignore unknown fields they do not understand.

This allows forward-compatible upgrades across implementations.

---

## 7. Global Configuration Schema

### 7.1 `config.json`

```json
{
  "spec_version": 1,
  "default_profile": "default",
  "encryption": {
    "mode": "local_key"
  }
}
```

### 7.2 Required Fields

- `spec_version`: integer
- `default_profile`: string

### 7.3 Optional Fields

- `encryption`
- `telemetry`
- `ui`
- `experimental`

Implementations MAY add fields.

---

## 8. Profile Metadata Schema

### 8.1 `profiles/<name>/metadata.json`

```json
{
  "name": "default",
  "created_at": "2026-04-16T09:00:00Z",
  "updated_at": "2026-04-16T09:00:00Z",
  "description": "Default local profile"
}
```

### 8.2 Required Fields

- `name`
- `created_at`
- `updated_at`

---

## 9. Provider Definition Schema

Provider definitions MUST be stored as JSON files so multiple implementations can consume them directly.

Bundled providers ship only provider definitions. Implementations MUST NOT assume bundled OAuth app credentials are available.

### 9.1 OAuth Client Credentials

For `oauth2` providers, client credentials are distinct from user connection credentials.

There is one client config per provider per profile. Client credentials include:
- `client_id`
- `client_secret`
- optional client metadata such as redirect URI, registration metadata, or issuer-specific settings

Client credentials are sensitive configuration and MUST be stored encrypted at rest when persisted locally.

Recommended logical key:

```text
profile:<profile_name>:<provider_name>:client
```

### 9.2 Example OAuth Provider

```json
{
  "schema_version": 1,
  "name": "github",
  "display_name": "GitHub",
  "auth_type": "oauth2",
  "flow": "pkce",
  "oauth": {
    "authorization_url": "https://github.com/login/oauth/authorize",
    "token_url": "https://github.com/login/oauth/access_token",
    "revocation_url": null,
    "device_authorization_url": null,
    "scopes": ["repo", "read:user"],
    "pkce": true,
    "supports_device_flow": false,
    "supports_dcr": false
  },
  "export": {
    "env": {
      "access_token": "GITHUB_ACCESS_TOKEN",
      "refresh_token": "GITHUB_REFRESH_TOKEN"
    }
  }
}
```

### 9.3 Example API Key Provider

```json
{
  "schema_version": 1,
  "name": "openai",
  "display_name": "OpenAI",
  "auth_type": "api_key",
  "flow": "api_key",
  "api_key": {
    "header_name": "Authorization",
    "header_prefix": "Bearer",
    "env_var": "OPENAI_API_KEY"
  },
  "export": {
    "env": {
      "api_key": "OPENAI_API_KEY"
    }
  }
}
```

### 9.4 Required Top-Level Fields

- `schema_version`
- `name`
- `display_name`
- `auth_type`
- `flow`

### 9.5 Auth-Type-Specific Sections

#### For `oauth2`
Required section: `oauth`

#### For `api_key`
Required section: `api_key`

The `api_key` section SHOULD include:
- `header_name`: HTTP header used to send the key
- `header_prefix`: optional prefix (e.g. `Bearer`)
- `env_var`: environment variable name to check before prompting

### 9.6 Provider Resolution Rules

When a provider is requested by name:

1. The implementation MUST look for `providers/<name>.json`.
2. If not found, it MAY search built-in bundled providers.
3. If both exist, local file overrides built-in definition.

---

## 10. Credential Store Contract

The credential store is logically a namespaced key-value store.

Implementations may use:
- py-key-value-aio,
- SQLite-backed KV,
- LevelDB,
- LMDB,
- equivalent local KV store.

Interoperability matters more than backend choice.

### 10.1 Key Namespace

Required logical keys:

```text
provider:<provider_name>:definition
profile:<profile_name>:<provider_name>:metadata
profile:<profile_name>:<provider_name>:state
profile:<profile_name>:<provider_name>:client
profile:<profile_name>:<provider_name>:connection:<connection_name>
```

This layout allows one provider to own multiple named connections within the same profile.

### 10.2 Value Encoding

Values MUST be JSON payloads, optionally encrypted before persistence.

### 10.3 Encryption Requirement

Sensitive credential fields MUST be encrypted at rest.

Sensitive fields include:
- access tokens
- refresh tokens
- api keys
- client secrets
- ID tokens when stored
- provider-issued secrets

### 10.4 Encryption Portability Rule

The spec requires field-level confidentiality, not one exact crypto implementation.

To support multi-language compatibility, implementations MUST support at least one shared envelope format.

Recommended portable envelope:

```json
{
  "enc": 1,
  "alg": "AES-256-GCM",
  "kid": "local",
  "nonce": "base64...",
  "ciphertext": "base64...",
  "tag": "base64..."
}
```

The exact local key management strategy is implementation-defined, but implementations that want cross-language read/write compatibility on the same machine SHOULD use the same master key source.

### 10.5 Master Key Recommendation

Recommended options, in order:

1. OS keychain / credential manager storing a local master key
2. A local wrapped key stored under `~/.authlib/`
3. A passphrase-derived key for headless environments

Implementations MUST document which mode they use.

---

## 11. Provider Metadata Record Schema

The provider metadata record stores non-secret metadata about the provider within a profile.

Examples:
- default connection name
- list of known connection names
- preferred account label
- last selected connection

Example:

```json
{
  "schema_version": 1,
  "profile": "default",
  "provider": "github",
  "default_connection": "default",
  "connection_names": ["default", "work"],
  "last_used_connection": "work",
  "metadata": {}
}
```

---

## 12. OAuth Client Config Schema

The OAuth client config stores saved client credentials for a provider. There is at most one per provider per profile.

### 12.1 Example OAuth Client Config

```json
{
  "schema_version": 1,
  "profile": "default",
  "provider": "github",
  "client_id": "abc123",
  "client_secret": {
    "enc": 1,
    "alg": "AES-256-GCM",
    "kid": "local",
    "nonce": "...",
    "ciphertext": "...",
    "tag": "..."
  },
  "source": "user_supplied",
  "metadata": {}
}
```

### 12.2 Required Fields

- `schema_version`
- `profile`
- `provider`
- `client_id`
- `client_secret`
- `source`
- `metadata`

### 12.3 Recommended Source Values

- `user_supplied`
- `env_imported`
- `dcr_generated`

---

## 13. Connection Record Schema

### 13.1 Example OAuth Connection Record

```json
{
  "schema_version": 1,
  "provider": "github",
  "profile": "default",
  "connection_name": "default",
  "auth_type": "oauth2",
  "status": "connected",
  "scopes": ["repo", "read:user"],
  "access_token": {
    "enc": 1,
    "alg": "AES-256-GCM",
    "kid": "local",
    "nonce": "...",
    "ciphertext": "...",
    "tag": "..."
  },
  "refresh_token": {
    "enc": 1,
    "alg": "AES-256-GCM",
    "kid": "local",
    "nonce": "...",
    "ciphertext": "...",
    "tag": "..."
  },
  "token_type": "Bearer",
  "expires_at": "2026-04-16T15:40:22Z",
  "obtained_at": "2026-04-16T14:40:22Z",
  "account": {
    "id": "12345",
    "label": "manojbajaj95"
  },
  "metadata": {}
}
```

### 13.2 Example API Key Connection Record

```json
{
  "schema_version": 1,
  "provider": "openai",
  "profile": "default",
  "connection_name": "default",
  "auth_type": "api_key",
  "status": "connected",
  "api_key": {
    "enc": 1,
    "alg": "AES-256-GCM",
    "kid": "local",
    "nonce": "...",
    "ciphertext": "...",
    "tag": "..."
  },
  "account": {
    "id": null,
    "label": null
  },
  "metadata": {}
}
```

### 13.3 Required Fields

- `schema_version`
- `provider`
- `profile`
- `connection_name`
- `auth_type`
- `status`
- `metadata`

### 13.4 Allowed Status Values

- `not_connected`
- `connected`
- `expired`
- `revoked`
- `invalid`

---

## 14. Provider State Record Schema

The provider state record stores transient or non-secret state.

Examples:
- last refresh attempt time
- last refresh error
- cached discovered endpoints
- PKCE verifier during login session
- device flow polling state

Example:

```json
{
  "schema_version": 1,
  "provider": "github",
  "profile": "default",
  "last_refresh_at": "2026-04-16T15:10:00Z",
  "last_refresh_error": null,
  "metadata": {}
}
```

---

## 15. Authentication Flows

The initial portable spec supports both human-assisted bootstrap and runtime reuse.

### 15.1 OAuth 2 PKCE

Used for browser-capable local environments.

#### Required Behavior

1. Resolve provider definition.
2. Resolve app credentials for the provider.
3. Generate PKCE code verifier and challenge.
4. Start a temporary localhost callback listener, OR allow manual code entry fallback.
5. Open authorization URL in the user’s browser.
6. Receive authorization code.
7. Exchange code for token set.
8. Persist normalized connection record.

#### Expected Result

A connected OAuth credential record with tokens, scopes, app reference, and expiry metadata.

### 15.2 OAuth 2 Device Code Flow

Used for headless or remote environments.

#### Required Behavior

1. Resolve provider definition.
2. Resolve app credentials for the provider.
3. Request device code.
4. Display verification URL and user code.
5. Poll token endpoint according to provider rules.
6. Persist normalized connection record.

### 15.3 DCR + PKCE

Used when the provider supports Dynamic Client Registration.

#### Required Behavior

1. Register client dynamically.
2. Store generated app metadata securely if needed.
3. Continue with PKCE flow.

DCR support MAY be optional in some implementations, but the provider model must support it.

### 15.4 API Key

A single unified flow for `api_key` providers. Tries the environment variable first, then falls back to an interactive prompt.

#### Required Behavior

1. If provider definition specifies `api_key.env_var`, check that environment variable.
2. If the variable is set and non-empty, use its value as the API key.
3. Otherwise, prompt for the API key securely (e.g. masked input).
4. Validate non-empty input.
5. Store encrypted key.
6. Mark connection as connected.

---

## 16. Refresh Semantics

Refresh logic applies to `oauth2` providers with refresh token capability.

### 16.1 Required Library Behavior

When a caller requests a usable access token:

1. If token is valid and not near expiry, return it.
2. If token is expired or near expiry, attempt refresh.
3. Refresh MUST resolve the saved OAuth client credentials for the provider.
4. If refresh succeeds, update the record.
5. If refresh fails, set state appropriately and surface an error.

### 16.2 Near-Expiry Window

Implementations SHOULD refresh within a configurable window before expiry.

Recommended default:
- 300 seconds before `expires_at`

### 16.3 Refresh Failure Status

Recommended transitions:
- refreshable failure: remain `expired`
- non-recoverable failure: transition to `invalid`

---

## 17. Revoke vs Remove Semantics

These operations MUST be distinct.

### 17.1 Revoke
`revoke(provider)` means:

1. attempt remote credential revocation if the provider supports it,
2. remove or invalidate local credential material,
3. mark status as revoked or remove the record.

### 17.2 Remove
`remove(provider)` means:

1. delete local credential material,
2. do not contact remote provider,
3. unregister only the local connection state.

---

## 18. Export Semantics

Export converts stored credentials into runtime-friendly output.

### 18.1 Supported Formats

Implementations SHOULD support:
- `env`
- `shell`
- `json`

### 18.2 Provider Export Map

Provider definitions may specify canonical environment variable names.

Example:

```json
{
  "export": {
    "env": {
      "access_token": "GITHUB_ACCESS_TOKEN",
      "refresh_token": "GITHUB_REFRESH_TOKEN"
    }
  }
}
```

### 18.3 Safe Defaults

- `get` should default to metadata.
- `export` should explicitly reveal runtime values.
- `run` should inject values directly without printing them.

---

## 19. CLI Specification

The executable name is implementation-defined, but this spec refers to it as:

```text
auth
```

### 19.1 Global Flags

All commands SHOULD support:

- `--profile <name>`
- `--json`
- `--quiet`
- `--no-color`

### 19.2 Commands

#### `auth init`
Initialize the root directory and default profile.

#### `auth list`
List providers and connection states.

#### `auth login <provider>`
Authenticate with the provider using its configured flow.

Optional flags:
- `--flow <flow>`
- `--scopes <csv>`
- `--connection <name>`
- `--client-id <value>`
- `--client-secret <value>`

Behavior rules:
- profile defaults to `default`
- connection defaults to `default`
- if `--client-id` and `--client-secret` are provided, implementations MUST save them as the provider's OAuth client config for reuse
- if OAuth client credentials are already saved for the provider, implementations SHOULD reuse them
- bundled providers do not imply bundled OAuth client credentials

#### `auth revoke <provider>`
Revoke credentials remotely if supported, then remove local credential state.

Optional flags:
- `--connection <name>`

#### `auth remove <provider>`
Delete local credential state without remote revocation.

Optional flags:
- `--connection <name>`

#### `auth get <provider>`
Return provider connection metadata by default.

Optional flags:
- `--connection <name>`
- `--field <field>`
- `--show-secret`

#### `auth inspect <provider>`
Return provider definition and local connection summary.

Optional flags:
- `--connection <name>`

#### `auth export <provider>`
Export credential material in selected format.

Optional flags:
- `--connection <name>`
- `--format env|shell|json`
- `--prefix <prefix>`

#### `auth run --provider <provider> -- <command...>`
Run a subprocess with injected exported credentials.

Optional flags:
- `--provider <provider>` repeated
- `--providers <csv>`
- `--connection <provider=name>` repeated

#### `auth register <path-or-url>`
Register a provider definition.

#### `auth whoami`
Show the active profile and basic local context.

#### `auth doctor`
Run health checks on directory layout, encryption availability, provider parsing, and store access.

### 19.3 Profile Commands

Optional advanced commands:

#### `auth profile list`
List local profiles.

#### `auth profile create <name>`
Create a profile.

#### `auth profile use <name>`
Set the global default profile.

---

## 20. CLI Output Contract

### 20.1 Human Output
Human-readable output may vary, but should preserve command semantics.

### 20.2 JSON Output
Structured output MUST be stable enough for machine use.

Example for `auth list --json`:

```json
{
  "profile": "default",
  "providers": [
    {
      "name": "github",
      "auth_type": "oauth2",
      "status": "connected",
      "scopes": ["repo", "read:user"],
      "expires_at": "2026-04-16T15:40:22Z"
    },
    {
      "name": "openai",
      "auth_type": "api_key",
      "status": "connected"
    }
  ]
}
```

### 20.3 Exit Codes

Recommended exit code semantics:

- `0` success
- `1` generic failure
- `2` invalid usage
- `3` provider not found
- `4` authentication failed
- `5` credential missing
- `6` refresh failed
- `7` store unavailable

---

## 21. Library Interface Contract

Each implementation should expose native APIs idiomatic to its language, but the following conceptual operations MUST exist.

### 21.1 Core Operations

- `listProviders()`
- `getProvider(name)`
- `registerProvider(definition)`
- `listConnections(profile, provider?)`
- `getConnection(provider, profile, connectionName)`
- `getDefaultConnection(provider, profile)`
- `setDefaultConnection(provider, profile, connectionName)`
- `login(provider, options)`
- `getAccessToken(provider, profile, connectionName)`
- `getAuthHeaders(provider, profile, connectionName)`
- `revoke(provider, profile, connectionName)`
- `remove(provider, profile, connectionName)`
- `export(provider, profile, connectionName, format)`
- `run(command, providers, profile)`

### 21.2 OAuth Client Config Operations

- `getClientConfig(profile, provider)`
- `setClientConfig(profile, provider, config)`
- `removeClientConfig(profile, provider)`

### 21.3 Expected Error Categories

- provider not found
- unsupported auth type
- unsupported flow
- credential missing
- app credentials missing
- token expired and refresh failed
- encryption unavailable
- store unavailable
- invalid provider schema

---

## 22. Auth Header Construction Rules

### 22.1 OAuth2
For OAuth2 providers, `getAuthHeaders()` SHOULD produce:

```json
{
  "Authorization": "Bearer <access_token>"
}
```

unless the provider definition specifies otherwise.

### 22.2 API Key
For API key providers, header construction follows provider config.

Examples:

```json
{
  "Authorization": "Bearer <api_key>"
}
```

or

```json
{
  "X-API-Key": "<api_key>"
}
```

---

## 23. Provider Registration Contract

`register` adds or updates a provider definition in `providers/<name>.json`.

### 23.1 Required Validation

Implementations MUST validate:
- required fields exist,
- `name` is filesystem-safe,
- `auth_type` is recognized,
- flow is valid for auth type,
- URLs are syntactically valid where required.

### 23.2 Update Behavior

If a provider already exists:
- implementations MAY overwrite only with explicit confirmation or force mode,
- library APIs SHOULD expose replace/update semantics explicitly.

---

## 24. Built-In Providers

Implementations MAY ship bundled provider definitions.

Recommended initial providers:

### OAuth2
- github
- google
- slack
- notion
- linear

### API key
- openai
- anthropic
- tavily
- serpapi
- resend
- stripe

Bundled providers MUST follow the same provider schema as local registered providers.

Bundled providers MUST NOT imply bundled OAuth app credentials.

---

## 25. Security Requirements

### 25.1 OAuth Client Credential Storage

OAuth client credentials (`client_id` and `client_secret`) MUST be treated as sensitive provider configuration when persisted.

Rules:
- `client_secret` MUST be encrypted at rest
- `client_id` SHOULD be persisted alongside the client secret when supplied explicitly for reuse
- implementations MUST persist explicit `client_id` and `client_secret` provided during login for reuse
- implementations SHOULD record the `source` of client credentials (`user_supplied`, `dcr_generated`, `env_imported`)
- implementations MUST avoid printing client secrets in logs, command output, or errors

### 25.2 Default Secret Handling

Implementations MUST avoid printing raw secrets unless explicitly requested.

### 25.3 Process Injection

`run` MUST inject secrets into subprocess environment without logging them.

### 25.4 Logging

Secret material MUST NOT appear in logs.

### 25.5 Error Messages

Errors SHOULD identify the failed provider and operation, but MUST avoid leaking secret values.

### 25.6 Local Access Assumption

This spec assumes the local machine and user account are trusted relative to remote services, but the store still requires encryption at rest.

---

## 26. Concurrency and Locking

Implementations SHOULD guard write operations with profile-level locking.

Recommended behavior:

1. acquire profile lock,
2. read current record,
3. apply update,
4. write updated record,
5. release lock.

Locks MAY be advisory.

---

## 27. Compatibility Rules

### 27.1 Backward Compatibility

Implementations reading older schema versions SHOULD migrate in memory where possible.

### 27.2 Forward Compatibility

Implementations MUST ignore unknown fields.

### 27.3 Cross-Language Compatibility Goal

A Python and JavaScript implementation are considered compatible if they can:

- read the same provider definitions,
- locate the same profile directories,
- interpret the same JSON records,
- decrypt records using the same shared keying mode,
- perform the same command semantics.

---

## 28. Minimum Viable Compliance

An implementation is minimally compliant with spec version 1 if it supports:

- local root resolution,
- implicit profile `default`,
- implicit connection `default`,
- JSON provider definitions,
- encrypted OAuth client config and connection storage,
- `oauth2` with browser-capable PKCE flow,
- `api_key` flow (env var first, prompt fallback),
- `list`, `login`, `get`, `remove`, `export`, `run`,
- stable JSON command output.

---

## 29. Deferred Scope / Future Extensions

The following areas are intentionally out of scope for the initial local-first spec, but are reasonable future extensions once the core local model is stable.

### 29.1 Remote Sync

Remote sync allows the local credential store to project selected records into external secret managers or secure remote backends.

Remote sync MUST treat the local store as canonical. Remote systems are sync targets, not the primary source of truth.

Possible sync targets:
- Doppler
- 1Password
- Vault KV
- cloud secret managers
- encrypted file/object storage

Recommended future sync modes:
- `flattened_env`
- `flattened_json_map`
- `json_blob`
- provider-specific sync adapters

Future remote sync work should define:
- export/import semantics
- conflict resolution rules
- selective sync by profile/provider/connection
- secret rotation and remote overwrite policies
- encryption and trust boundary requirements
- one-way vs two-way sync behavior

### 29.2 Secret References and Broker Mode

A future version may support secret references or runtime handles instead of returning raw secret material.

Examples:
- process-local secret injection handles
- opaque references that are resolved only at runtime
- brokered access for agents without direct secret exposure

### 29.3 HTTP Client and Framework Adapters

Future implementations may define standard adapters for:
- HTTP clients
- web frameworks
- MCP servers
- subprocess runners
- background workers

These adapters should remain thin wrappers over the core provider and connection model.

### 29.4 Token Introspection and Validation Hooks

Future versions may define provider hooks for:
- token validation
- account lookup
- scope inspection
- connection health checks
- provider-specific refresh or revocation semantics

### 29.5 Team / Shared Profiles

The initial spec is single-user local-first. A future version may define:
- shared profile layouts
- delegated access to shared connections
- imported connection bundles
- collaboration-safe locking and audit metadata

### 29.6 Runtime Authorization and Approval Layers

The initial spec focuses on credential lifecycle, not runtime authorization.

Future layers may define:
- purpose-scoped approvals
- action-level policy checks
- delegated identity chains
- human-in-the-loop confirmations
- approval-bound temporary credentials

### 29.7 Audit and Event Stream

A future version may define a portable event model for:
- login events
- refresh events
- export events
- revoke/remove events
- sync events
- runtime access events

### 29.8 Compliance Principle for Future Extensions

Future extensions SHOULD avoid breaking:
- local portability
- profile/provider/connection identity
- JSON serialization rules
- encrypted record compatibility

---

## 30. Non-Goals

The following are explicitly out of scope for spec version 1:

- hosted sync service
- multi-user team sharing
- distributed secret replication
- enterprise policy engine
- runtime approval workflows
- organization-wide RBAC
- MCP gateway behavior
- remote execution control plane

These may be layered later, but are not required for interoperability.

---

## 31. Example End-to-End Behavior

### 31.1 Bundled Provider with User-Owned OAuth Client Credentials

1. User runs `auth login github --client-id abc --client-secret xyz`
2. CLI resolves built-in provider definition for `github`
3. CLI saves OAuth client credentials under profile `default`, provider `github`
4. CLI creates PKCE challenge and localhost callback server
5. User authorizes in browser
6. CLI exchanges code for token set
7. CLI stores encrypted connection record under profile `default`, provider `github`, connection `default`
8. `auth list` now shows `github` as connected

### 31.2 Multiple Connections for the Same Provider

1. User runs `auth login sendgrid` → stores connection `default`
2. User runs `auth login sendgrid --connection bulk` → stores a second connection `bulk`
3. `auth export sendgrid --connection bulk` exports the `bulk` connection's API key
4. `auth run --provider sendgrid --connection sendgrid=bulk -- python send.py` injects the `bulk` credentials

### 31.3 Registered Custom Provider

1. User runs `auth register ./acmecrm.json`
2. User runs `auth login acmecrm --client-id abc --client-secret xyz`
3. CLI resolves registered provider definition for `acmecrm`
4. CLI saves OAuth client credentials under profile `default`, provider `acmecrm`
5. CLI creates PKCE challenge and localhost callback server
6. User authorizes in browser
7. CLI exchanges code for token set
8. CLI stores encrypted connection record under profile `default`, provider `acmecrm`, connection `default`

### 31.4 Use in Python

1. Python app loads profile `default`
2. App asks for GitHub auth headers for connection `default`
3. Library reads stored connection record
4. Library resolves saved OAuth client credentials for the provider
5. Library refreshes token if needed
6. Library returns `Authorization: Bearer ...`

### 31.5 Use in JavaScript

1. Node app loads same profile path
2. Node library reads same JSON provider, client config, and connection records
3. Node library decrypts credentials using the same key mode
4. Node library returns equivalent auth headers

---

## 32. Naming Recommendations

For portability, the following naming is recommended across implementations:

- spec name: `authlib spec`
- root env var: `AUTHLIB_HOME`
- default executable: `auth`
- default root dir: `~/.authlib`
- default profile: `default`
- default connection: `default`

Language-specific packages may vary.

Examples:
- Python package: `authlib-local`
- JavaScript package: `@authlib/local`
- CLI executable: `auth`

---

## 33. Summary

This spec defines a portable local auth substrate with:

- provider-aware local auth,
- portable provider definitions,
- per-provider OAuth client config (one per provider per profile),
- multiple named connections per provider,
- cross-language credential compatibility,
- local encrypted storage,
- normalized CLI semantics,
- embeddable library semantics.

It is intended to be the smallest shared foundation that multiple implementations can build on without fragmenting behavior or storage.

