# Shell Completion Setup

Enable tab completion for Sunwell commands, options, and arguments.

## Bash

Add to your `~/.bashrc`:

```bash
# Sunwell tab completion
eval "$(_SUNWELL_COMPLETE=bash_source sunwell)"
```

Or generate a completion script to source:

```bash
# Generate completion script
_SUNWELL_COMPLETE=bash_source sunwell > ~/.sunwell-complete.bash

# Add to ~/.bashrc
echo 'source ~/.sunwell-complete.bash' >> ~/.bashrc
```

Reload your shell:

```bash
source ~/.bashrc
```

## Zsh

Add to your `~/.zshrc`:

```zsh
# Sunwell tab completion
eval "$(_SUNWELL_COMPLETE=zsh_source sunwell)"
```

Or generate a completion script:

```zsh
# Generate completion script
_SUNWELL_COMPLETE=zsh_source sunwell > ~/.sunwell-complete.zsh

# Add to ~/.zshrc
echo 'source ~/.sunwell-complete.zsh' >> ~/.zshrc
```

Reload your shell:

```zsh
source ~/.zshrc
```

## Fish

Add to `~/.config/fish/completions/sunwell.fish`:

```fish
# Generate and source completions
_SUNWELL_COMPLETE=fish_source sunwell | source
```

Or create a completion file:

```fish
# Generate completion script
_SUNWELL_COMPLETE=fish_source sunwell > ~/.config/fish/completions/sunwell.fish
```

## What Gets Completed

Shell completion provides suggestions for:

### Commands

```bash
sunwell con<TAB>  # → sunwell config
sunwell lens l<TAB>  # → sunwell lens list
```

### Options

```bash
sunwell --ver<TAB>  # → sunwell --verbose
sunwell -<TAB>  # Shows all options
```

### Shortcuts

```bash
sunwell -s a<TAB>  # → sunwell -s a-2 (or other 'a' shortcuts)
sunwell -s <TAB>  # Shows all available shortcuts
```

### File Paths

```bash
sunwell -s a-2 docs/<TAB>  # Shows files in docs/
sunwell . src/<TAB>  # Shows directories
```

## Troubleshooting

### Completion Not Working

1. **Verify installation**:
   ```bash
   which sunwell
   # Should show path to sunwell
   ```

2. **Check Click version**:
   ```bash
   python -c "import click; print(click.__version__)"
   # Should be 8.0+
   ```

3. **Regenerate completions**:
   ```bash
   # Remove cached completions
   rm ~/.sunwell-complete.*
   
   # Regenerate for your shell
   _SUNWELL_COMPLETE=bash_source sunwell > ~/.sunwell-complete.bash
   source ~/.sunwell-complete.bash
   ```

### Slow Completion

If completion is slow on first use:

1. This is normal - shortcuts are loaded from lens files
2. Subsequent completions use cache
3. Invalidate cache if shortcuts seem stale:
   ```python
   from sunwell.interface.cli.core.shortcuts import invalidate_shortcut_cache
   invalidate_shortcut_cache()
   ```

### Wrong Completions

If you see outdated shortcuts:

```bash
# The shortcut cache persists per-session
# Restart your shell or invalidate the cache
exec $SHELL
```

## Advanced: Custom Completions

For custom completion behavior, extend the Click completion system:

```python
# In your custom lens or extension
from sunwell.interface.cli.core.shortcuts import get_cached_shortcuts

def custom_complete(ctx, param, incomplete):
    """Custom completion function."""
    shortcuts = get_cached_shortcuts()
    return [s for s in shortcuts if s.startswith(incomplete)]
```

## Platform Notes

### macOS

If using the default Bash (3.2), completion may not work fully. Consider:
- Upgrading to Bash 4+ via Homebrew
- Using Zsh (default since macOS Catalina)

```bash
# Install newer Bash
brew install bash

# Or use Zsh (recommended)
chsh -s /bin/zsh
```

### Windows

On Windows with PowerShell, Click completion is not natively supported.
Consider using:
- Windows Subsystem for Linux (WSL)
- Git Bash

### Linux

Most distributions include completion support out of the box.
Ensure `bash-completion` package is installed:

```bash
# Debian/Ubuntu
sudo apt install bash-completion

# Fedora/RHEL
sudo dnf install bash-completion
```

---

*Shell completion makes Sunwell faster to use. Tab early, tab often.*
