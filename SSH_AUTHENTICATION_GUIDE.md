# SSH Authentication Guide

Outrider supports multiple SSH authentication methods with automatic intelligent fallback behavior. Authentication is attempted in priority order until one succeeds.

## Credential Fallback Strategy

When connecting to a remote host, SSH credentials are **automatically tried in priority order** until one succeeds:

### Priority Order (Highest to Lowest)

1. **Provided SSH Private Key** (highest priority)
   - Configured via `transport.options.key_file` or `ssh_options.key_file`
   - Must exist on filesystem
   - If available: tried first

2. **SSH Agent Keys**
   - Keys stored in local SSH agent (ssh-add)
   - Requires `allow_agent=true` (default)

3. **Discoverable Keys in ~/.ssh/**
   - Auto-discovered: `id_rsa`, `id_ed25519`, `id_ecdsa`, etc.
   - Requires `look_for_keys=true` (default)

4. **Password Authentication** (lowest priority for credentials)
   - Configured via `transport.options.password` or `ssh_options.password`
   - Used only if key-based auth methods fail
   - Fallback mechanism

### What About No-Auth/Anonymous?

**Not implemented, and here's why:**

1. **Extremely rare in practice** - virtually all SSH servers require authentication
2. **Server-dependent** - SSH server discloses available methods only after initial failure
3. **Low security value** - anonymous/no-password SSH is a security anti-pattern
4. **Paramiko limitation** - paramiko doesn't automatically try no-auth; servers must explicitly enable it
5. **Not needed for Outrider** - real-world deployments always have credentials

If you encounter an SSH server that allows no-auth, you can still connect via the generic_ssh plugin with a custom command, but this is not a recommended deployment pattern.

## Authentication Methods

### 1. SSH Key-Based Authentication (Recommended)

Most secure method. Automatically used if key file exists.

**Global SSH key:**

```yaml
transport:
  type: ssh
  options:
    key_file: ~/.ssh/id_rsa  # Path to private key
```

**Per-target SSH key:**

```yaml
targets:
  - host: host1.example.com
    user: ubuntu
    ssh_options:
      key_file: ~/.ssh/custom_key
```

### 2. Password Authentication

Used when no SSH key is available or key file doesn't exist.

**Global password:**

```yaml
transport:
  type: ssh
  options:
    password: "your-ssh-password"
    user: root
```

**Per-target password:**

```yaml
targets:
  - host: host1.example.com
    user: ubuntu
    ssh_options:
      password: "user-password"
```

### 3. SSH Config File (~/.ssh/config)

Automatically loaded if it exists. Provides:
- Custom usernames per host
- Custom ports
- Identity files (keys)
- ProxyJump/ProxyCommand support

**Example ~/.ssh/config:**

```
Host production
  HostName 192.168.1.100
  User deploy
  IdentityFile ~/.ssh/prod_key
  Port 2222

Host staging
  HostName 192.168.1.101
  User ubuntu
  IdentityFile ~/.ssh/staging_key
```

**Use in config:**

```yaml
targets:
  - host: production  # Matches SSH config entry
  - host: staging     # Matches SSH config entry
```

## Authentication Precedence

When connecting to a target, the system resolves authentication in this order (highest to lowest priority):

1. **Per-target SSH key file** (`ssh_options.key_file`)
   - Must exist on filesystem
   - If doesn't exist → falls back to next level

2. **Per-target password** (`ssh_options.password`)

3. **Per-target username** (`user` or `ssh_options.user`)

4. **Global transport key file** (`transport.options.key_file`)
   - Must exist on filesystem

5. **Global transport password** (`transport.options.password`)

6. **Global transport username** (`transport.options.user`)

7. **SSH config file** (~/.ssh/config)
   - Auto-loaded, provides hostname, user, port, keys

8. **Default username** (`"root"`)

## Common Configurations

### Config 1: Key-Based (Most Secure)

```yaml
transport:
  type: ssh
  options:
    key_file: ~/.ssh/id_rsa

targets:
  - host: host1.example.com
    user: ubuntu
  - host: host2.example.com
    user: ubuntu
```

### Config 2: Password-Based

```yaml
transport:
  type: ssh
  options:
    user: root
    password: "your-password"

targets:
  - host: 192.168.1.100
    port: 22
  - host: 192.168.1.101
    port: 22
```

### Config 3: Mixed Per-Target Auth

```yaml
transport:
  type: ssh
  options:
    key_file: ~/.ssh/default_key
    user: deploy

targets:
  - host: host1.example.com
    # Uses global key and user

  - host: host2.example.com
    user: admin
    ssh_options:
      password: "admin-password"
    # Overrides to use password auth with admin user

  - host: host3.example.com
    ssh_options:
      key_file: ~/.ssh/special_key
      user: special
    # Uses different key file and user
```

### Config 4: SSH Config File (Most Flexible)

If you have ~/.ssh/config set up:

```yaml
transport:
  type: ssh

targets:
  - host: production    # Reads from ~/.ssh/config
  - host: staging       # Reads from ~/.ssh/config
  - host: dev           # Reads from ~/.ssh/config
```

With ~/.ssh/config:
```
Host production
  HostName prod.example.com
  User deploy
  IdentityFile ~/.ssh/prod_key

Host staging
  HostName staging.example.com
  User ubuntu
  IdentityFile ~/.ssh/staging_key

Host dev
  HostName dev.example.com
  User root
  IdentityFile ~/.ssh/dev_key
```

## Behavior & Fallback

### Key File Behavior

- **If key file is specified**: SSHTouches file system to check existence
- **If file exists**: Uses key-based authentication
- **If file doesn't exist**: Falls back to password authentication (if provided)
- **If no password available**: Connection fails with clear error

### Smart Defaults

- Default key file: `~/.ssh/id_rsa` (only used if it exists)
- Default port: `22`
- Default user: `root`
- Default password: None (falls back to key auth)

### Error Messages

Clear logging tells you what authentication is being attempted:

```
[INFO] Initialized Docker runtime
[INFO] Initialized SSH transport
[DEBUG] Default SSH key found: /home/user/.ssh/id_rsa
[DEBUG] Connecting to host1.example.com (resolved: 192.168.1.100)
[INFO] Connected to host1.example.com
```

If key file doesn't exist:
```
[WARNING] Default SSH key not found: /home/user/.ssh/id_rsa, will use password auth if available
```

## Troubleshooting

### "No such file or directory" for key file

**Problem**: Key file specified but doesn't exist

**Solution**:
- Verify file path exists: `ls ~/.ssh/id_rsa`
- Use absolute path in config
- Or remove key_file and use password

```yaml
transport:
  type: ssh
  options:
    password: "your-password"  # Falls back to password auth
```

### "Authentication failed"

**Problem**: Neither key nor password worked

**Solutions**:
1. Verify credentials are correct
2. Check if user exists on remote system
3. Verify SSH is running on remote: `ssh -v user@host`
4. Check remote sshd logs for auth errors

### "Connection refused"

**Problem**: Can't connect to host:port

**Solutions**:
1. Verify host is reachable: `ping 192.168.1.100`
2. Verify SSH port: `ssh -p 2222 user@host`
3. Check firewall rules: `telnet host 22`
4. Verify SSH is listening: `netstat -tlnp | grep :22`

### "Permission denied (publickey)"

**Problem**: Key-based auth failed, no password available

**Solution**: Add a password to config as fallback

```yaml
transport:
  type: ssh
  options:
    key_file: ~/.ssh/id_rsa
    password: "fallback-password"  # Used if key fails
```

## Security Best Practices

1. **Use SSH keys, not passwords** when possible
2. **Protect private keys**: `chmod 600 ~/.ssh/id_rsa`
3. **Don't commit passwords to version control**
   - Use environment variables: `password: ${SSH_PASSWORD}`
   - Or external config files: `.gitignore` sensitive config
4. **Use different keys per system** if possible
5. **Rotate passwords/keys regularly**
6. **Use SSH config for host management**

## Environment Variables (Future Feature)

```yaml
transport:
  type: ssh
  options:
    password: ${SSH_PASSWORD}  # Reads from environment
    key_file: ${SSH_KEY_PATH}
```

(Currently not implemented, but can use shell substitution:)

```bash
SSH_PASSWORD="mypass" outrider deploy -c config.yaml
```

## Advanced: Controlling Authentication Behavior

### Disable SSH Agent (Force Key File Only)

If you want to skip SSH agent keys and only use specified key files:

```yaml
transport:
  type: ssh
  options:
    key_file: ~/.ssh/specific_key
    allow_agent: false      # Skip SSH agent
    look_for_keys: false    # Skip ~/.ssh/ discovery
    password: "fallback"    # Still tries password if key fails
```

Fallback order: `specific_key` → `password`

### Disable Key Discovery (Force Key File or Password)

If you want to skip automatic key discovery:

```yaml
transport:
  type: ssh
  options:
    key_file: ~/.ssh/id_rsa
    allow_agent: true       # SSH agent still checked
    look_for_keys: false    # Skip ~/.ssh/ auto-discovery
```

Fallback order: `id_rsa` → `SSH agent` → `password`

### Disable All Agent/Discovery (Explicit Credentials Only)

Most restrictive - only use explicitly provided credentials:

```yaml
transport:
  type: ssh
  options:
    key_file: ~/.ssh/prod_key
    allow_agent: false
    look_for_keys: false
    password: "fallback_only"
```

Fallback order: `prod_key` → `fallback_only`

### Debug: See What Auth Methods Are Tried

Enable verbose logging to see the auth strategy:

```bash
outrider deploy -c config.yaml -v
```

Output will show:
```
[DEBUG] Auth methods for 192.168.1.100 (in priority order): key: ~/.ssh/id_rsa → SSH agent → ~/.ssh/ keys → password
[DEBUG] Connecting to 192.168.1.100
[INFO] Connected to 192.168.1.100
```

If connection fails, detailed error shows what was attempted:
```
[ERROR] Failed to connect to 192.168.1.100: Authentication failed
  Attempted auth methods: key-based (~/.ssh/id_rsa), SSH agent, ~/.ssh/ keys, password
```

## Related Configuration

- **Per-target user**: Use `user:` field or `ssh_options.user`
- **Custom port**: Use `port:` field or `ssh_options.port`
- **Allow SSH agent**: `transport.options.allow_agent` (default: true)
- **Look for keys**: `transport.options.look_for_keys` (default: true)
- **Timeout**: `transport.options.timeout` (in seconds)
- **Host verification**: `--skip-host-verification` flag (testing only)

See [README.md](README.md) for complete configuration reference.
