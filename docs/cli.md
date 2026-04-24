# CLI Reference

All commands support `--json` for machine-readable output and `--profile` to switch between credential sets (personal, work, agent, etc.).

---

## Commands

| Command | Description |
|---------|-------------|
| `init` | Initialize `~/.authsome` directory and default profile. |
| `whoami` | Show home directory and encryption mode. |
| `doctor` | Run health checks on directory layout and encryption. |
| `list` | List all providers (bundled + custom) and their connection states. |
| `inspect <provider>` | Show the full provider definition schema. |
| `login <provider>` | Authenticate with a provider using its configured flow. |
| `get <provider>` | Get connection metadata (secrets redacted by default). |
| `export <provider>` | Export credentials in `env`, `shell`, or `json` format. |
| `run --provider <p> -- <cmd>` | Run a subprocess with injected credentials. |
| `proxy run -- <cmd>` | Run a subprocess behind the local auth injection proxy. |
| `logout <provider>` | Log out of a connection and remove local state. |
| `revoke <provider>` | Complete reset of the provider, removing all connections and client secrets. |
| `remove <provider>` | Uninstall a local provider or reset a bundled provider. |
| `register <path>` | Register a custom provider from a JSON file. |

---

## Global Flags

| Flag | Description |
|------|-------------|
| `--json` | Machine-readable JSON output. |
| `--profile <name>` | Switch between credential sets (personal, work, agent). |
| `--quiet` | Suppress non-essential output. |
| `--no-color` | Disable ANSI colors. |

---

## Command Details

### `init` / `doctor` / `whoami`

```bash
authsome init      # initialize ~/.authsome
authsome doctor    # verify installation health
authsome whoami    # show home directory and encryption mode
```

### `list` / `inspect`

```bash
authsome list                   # all connections + token status
authsome inspect github --json  # full provider schema
```

### `login`

```bash
authsome login <provider> [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--flow <type>` | Override the auth flow. Valid values: `pkce`, `device_code`, `dcr_pkce`, `api_key`. |
| `--connection <name>` | Connection name (default: `default`). |
| `--scopes <s1,s2>` | Comma-separated scopes to request. |
| `--force` | Overwrite an existing connection. |

```bash
authsome login github                    # OAuth2 browser flow (PKCE)
authsome login github --flow device_code # headless / no local browser
authsome login openai                    # secure API key entry via browser bridge
```

Setup can use browser PKCE, device code, or a browser bridge for secure API key entry. After setup, agents can run headlessly in CI, SSH, cron, background workers, or parallel pipelines.

### `get`

```bash
authsome get <provider> [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--connection <name>` | Connection name (default: `default`). |
| `--field <field>` | Return only a specific field. |
| `--show-secret` | Reveal encrypted secret values in output. |

```bash
authsome get github               # connection metadata, secrets redacted
authsome get github --field status
```

### `export`

```bash
authsome export <provider> [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--connection <name>` | Connection name (default: `default`). |
| `--format <fmt>` | Output format: `env` (default), `shell`, or `json`. |

```bash
authsome export github --format shell   # export GITHUB_TOKEN=...
```

### `run`

```bash
authsome run --provider <p1> [--provider <p2>] -- <command>
```

Short flag: `-p` is an alias for `--provider`.

Runs `<command>` as a subprocess with credentials injected into its environment. Multiple `--provider` flags can be combined. Note: `run` does not support `--connection`; it always uses the default connection for each provider.

```bash
authsome run --provider openai -- python my_agent.py
authsome run -p github -p openai -- python my_script.py
```

### `proxy run`

```bash
authsome proxy run -- <command> [args...]
```

Use `authsome proxy run -- <command>` when you want HTTP(S) requests to receive provider auth headers at request time without exporting secrets into the child process environment.

The proxy automatically matches outbound requests to known provider hosts (e.g. `api.openai.com`, `api.github.com`) using provider metadata and injects the appropriate `Authorization` header. Unmatched traffic is forwarded unchanged.

```bash
authsome proxy run -- python my_agent.py
authsome proxy run -- curl https://api.openai.com/v1/models
```

**How it works:**

1. Starts a local proxy on an ephemeral port.
2. Launches the child command with `HTTP_PROXY` / `HTTPS_PROXY` set.
3. Intercepts matched requests and injects auth headers.
4. Stops the proxy when the child exits.
5. Returns the child's exit code.

### `register`

```bash
authsome register <path/to/provider.json> [--force]
```

Registers a custom provider. Use `--force` to overwrite an existing provider with the same name. See the [provider registration guide](./register-provider.md) for JSON templates and field reference.

### `logout` / `revoke` / `remove`

```bash
authsome logout <provider> [--connection <name>]   # log out + revoke remotely
authsome revoke <provider>                          # reset all connections and client secrets
authsome remove <provider>                          # uninstall local provider or reset bundled
```
