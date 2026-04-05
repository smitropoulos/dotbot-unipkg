# dotbot-unipkg

A [Dotbot](https://github.com/anishathalye/dotbot) plugin to streamline package management across different distributions and operating systems.

`dotbot-unipkg` provides a unified interface to manage packages, automatically detecting and using the available system package manager.

## Features

- **Multi-Platform Support**: Automatically detects and uses `pacman`, `apt-get`, `brew`, `dnf`, or `zypper`.
- **Intelligent Installation**: Checks if a package is already installed before attempting to install it.
- **Alternative Names**: Specify fallback package names for different distributions (e.g., `fd` vs `fd-find`).
- **OS Filtering**: Conditionally install packages based on the operating system (e.g., `linux` or `macos`).
- **Silent Operation**: Runs package manager commands in the background for a clean Dotbot execution.

## Installation

Add `dotbot-unipkg` as a submodule to your dotfiles repository:

```bash
git submodule add https://github.com/smitropoulos/dotbot-unipkg dotbot-plugins/dotbot-unipkg
```

### Enable the Plugin

To use the plugin, you must tell Dotbot where to find it. You can do this in your `install` script or your `install.conf.yaml`.

#### Option 1: In `install.conf.yaml` (Recommended)

Add the path to the plugin directory in the `plugins` section of your configuration:

```yaml
- plugins:
    - dotbot-plugins/dotbot-unipkg
```

#### Option 2: In your `install` script

Pass the plugin path using the `-p` flag:

```bash
BASEDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIPKGPLUGIN="${BASEDIR}/dotbot-plugins/dotbot-unipkg/unipkg.py"

"${BASEDIR}/dotbot/bin/dotbot" \n    -d "${BASEDIR}" \n    -c "install.conf.yaml" \n    -p "${UNIPKGPLUGIN}" \n    "${@}"
```

## Usage

The plugin introduces the `unipkg` directive. It supports several configuration options:

- `update`: Updates the package manager's local cache.
- `verbose`: Enables verbose output for package manager commands.
- `install`: A list of packages to ensure are installed.

### Basic Example

```yaml
- unipkg:
    update: true
    verbose: true # Show output for all commands
    install:
      - neovim
      - ripgrep
      - lsd
      - zoxide
```

### Advanced Configuration

#### Granular Verbosity

You can set a global `verbose` flag and override it for specific packages.

```yaml
- unipkg:
    verbose: true # Global default: show output for all commands
    install:
      - nvim
      - tmux:
          verbose: false # Local override: silence this specific package
```

#### Alternative Names

Use `alt_name` to handle packages that have different names across various package managers. The plugin will try the primary name first, then fall back to the alternatives.

```yaml
- unipkg:
    - install:
        - fd:
            alt_name: fd-find
        - bat:
            alt_name: [batcat, bat-extras]
```

#### OS Filtering

Use `filter` to limit a package installation to specific operating systems. Currently supported filters are `linux` and `macos`.

```yaml
- unipkg:
    - install:
        - g++:
            filter: linux
        - coreutils:
            filter: [macos]
```

#### Combining Features

You can use both `alt_name` and `filter` for the same package:

```yaml
- unipkg:
    - install:
        - python3:
            alt_name: python
            filter: [linux, macos]
```

## Supported Package Managers

- **Arch Linux**: `pacman`
- **Debian/Ubuntu**: `apt-get`
- **macOS/Linux**: `Homebrew`
- **Fedora/RHEL**: `dnf`
- **openSUSE**: `zypper`

## License

[MIT](LICENSE)
