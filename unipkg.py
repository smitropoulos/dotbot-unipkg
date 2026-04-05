from __future__ import annotations

import shlex
import subprocess
import sys
from abc import ABC
from shutil import which
from typing import ClassVar

import dotbot

plugin_name = "Unipkg"


class UniPkg(dotbot.Plugin):
    # only support the unipkg directive
    _mainDirective = "unipkg"

    def _log_error(self, msg: str) -> None:
        self._log.error(f"{plugin_name} - {msg}")

    def _log_info(self, msg: str) -> None:
        self._log.info(f"{plugin_name} - {msg}")

    def __init__(self, context) -> None:  # noqa: ANN001
        super().__init__(context)
        pmf = PackageManagerFactory()
        self._packageManager = pmf.spawn()
        self.parser = DirectivesParser()

    def can_handle(self, directive: str) -> bool:
        # only allow the directives listed above
        return directive in (self._mainDirective)

    def handle(self, directive, data) -> bool:  # noqa: ANN001, ARG002
        directives = self.parser.parse(data)

        if directives.update is True:
            self._log_info("Updating repos ...")
            self._packageManager.update(verbose=directives.verbose)

        filtering = OsFiltering()
        for install_entry in directives.install_entries:
            # effective verbose is entry level if set, else global
            effective_verbose = (
                install_entry.verbose
                if install_entry.verbose is not None
                else directives.verbose
            )

            self._log_info(f"Installing {install_entry}")
            if filtering.filter_out(install_entry):
                self._log_info(
                    f"filtering out {install_entry.package_name} - filter: {install_entry.filters}"
                )
                continue

            install_success = self._packageManager.package_install(
                install_entry.package_name, verbose=effective_verbose
            )
            # try alternative names if present
            if not install_success and len(install_entry.package_name_alt) != 0:
                for alt_name in install_entry.package_name_alt:
                    install_success = self._packageManager.package_install(
                        alt_name, verbose=effective_verbose
                    )
            if not install_success:
                # instead of bailing, continue and log this
                self._log_error(f"error installing {install_entry}")
            else:
                self._log_info(f"installed {install_entry}")

        self._log_info("done")
        return True


class OsFiltering:
    supported_os: ClassVar[list[str]] = ["linux", "macos"]

    def __init__(self) -> None:
        self.platform = self._get_platform()

    def _get_platform(self) -> str:
        return sys.platform

    def _should_filter(self, install_entry: InstallEntry) -> bool:
        return bool(install_entry.filters is not None and len(install_entry.filters) != 0)

    def filter_out(self, install_entry: InstallEntry) -> bool:
        """handles filtering based on OS

        Returns:
            True to filter the entry out, e.g. not handle it at all
        """
        return bool(
            self._should_filter(install_entry) and self.platform not in install_entry.filters
        )


class Directives:
    """Holds all parsed directives from the configuration."""

    update: bool = False
    verbose: bool = False
    install_entries: list[InstallEntry] = []  # noqa: RUF012


class InstallEntry:
    def __init__(
        self,
        name: str | None = None,
        alts: list[str] | None = None,
        filters: list[str] | None = None,
        verbose: bool | None = None,
    ) -> None:
        """Initializes the Package object."""
        self.package_name = name if name is not None else ""
        self.package_name_alt = alts if alts is not None else []
        self.filters = filters if filters is not None else []
        self.verbose = verbose

    def __repr__(self) -> str:
        """Provides a clean, readable string representation."""
        name_str = self.package_name
        if self.package_name_alt:
            name_str += f" (alternative name: {', '.join(self.package_name_alt)})"

        filter_str = ""
        if self.filters:
            filter_str = f"- (filters: {', '.join(self.filters)})"

        return f"{name_str} {filter_str}"


class DirectivesParser:
    _mainDirective = "unipkg"
    _installSubDirective = "install"
    _updateSubDirective = "update"

    def _parse_package_attributes(self, entry: InstallEntry, attributes: dict | None) -> None:
        """Helper to populate an InstallEntry from an attributes dictionary."""
        if attributes is None:
            return

        # Safely get alt_name and ensure it's a list
        alt_name = attributes.get("alt_name")
        if isinstance(alt_name, str):
            entry.package_name_alt = [alt_name]
        elif isinstance(alt_name, list):
            entry.package_name_alt = alt_name

        # Safely get filter and ensure it's a list
        package_filter = attributes.get("filter")
        if isinstance(package_filter, str):
            entry.filters = [package_filter]
        elif isinstance(package_filter, list):
            entry.filters = package_filter

        # Safely get verbose
        entry.verbose = attributes.get("verbose")

    def _parse_install_list(self, packages_data: list) -> list[InstallEntry]:
        """Parses a list of packages containing mixed types (strings and dicts)."""
        parsed_entries = []
        for item in packages_data:
            # Handle simple package names like "lsd"
            if isinstance(item, str):
                entry = InstallEntry(name=item)
                parsed_entries.append(entry)

            # Handle complex package entries like {"neovim": {...}}
            elif isinstance(item, dict):
                # Extract the name (key) and attributes (value)
                for name, attributes in item.items():
                    entry = InstallEntry(name=name)
                    self._parse_package_attributes(entry, attributes)
                    parsed_entries.append(entry)

        return parsed_entries

    def parse(self, data: list) -> Directives:
        """The main entry point for parsing the configuration list."""
        directives = Directives()

        for item in data:
            if isinstance(item, str) and item == self._updateSubDirective:
                directives.update = True

            elif isinstance(item, dict) and self._updateSubDirective in item:
                directives.update = item[self._updateSubDirective]

            elif isinstance(item, dict) and "verbose" in item:
                directives.verbose = item["verbose"]

            elif isinstance(item, dict) and self._installSubDirective in item:
                packages_list = item[self._installSubDirective]
                # Delegate the mixed-type list to the helper
                install_entries = self._parse_install_list(packages_list)
                directives.install_entries.extend(install_entries)

        return directives


def run_in_shell(cmd: str, *, verbose: bool = False) -> bool:
    if not verbose:
        stdout = stderr = subprocess.DEVNULL
    else:
        stdout = stderr = None

    result = subprocess.call(cmd, shell=True, stdout=stdout, stderr=stderr)
    return result == 0


class PackageManager(ABC):
    """package manager interface"""

    def package_install(self, package: str, verbose: bool = False) -> bool:
        """install a package

        Returns:
            success
        """
        # check if package is installed
        if self.package_is_installed(package, verbose=verbose):
            return True

        # check if package exists in repos
        if not self.package_exists(package, verbose=verbose):
            return False

        cmd = f"{self._package_install_command} {shlex.quote(package)}"
        return run_in_shell(cmd, verbose=verbose)

    def update(self, verbose: bool = False) -> None:
        """update the caches"""
        run_in_shell(self._update_command, verbose=verbose)

    def package_exists(self, package: str, verbose: bool = False) -> bool:
        """check if the package exists in the remote

        Returns:
            success
        """
        cmd = f"{self._package_exists_command} {shlex.quote(package)}"
        return run_in_shell(cmd, verbose=verbose)

    def package_is_installed(self, package: str, verbose: bool = False) -> bool:
        """checks if the packages is already installed

        Returns:
            true if installed, false if not
        """
        cmd = f"{self._package_is_installed_command} {shlex.quote(package)}"
        return run_in_shell(cmd, verbose=verbose)


class PacmanPackageManager(PackageManager):
    def __init__(self) -> None:
        super().__init__()
        self._update_command = "sudo pacman --sync --refresh --refresh"
        self._package_exists_command = "pacman -Si"  # plus pkg
        self._package_is_installed_command = "pacman -Qe"  # plus pkg
        self._package_install_command = "sudo pacman -S --noconfirm --needed"  # plus pkg

    def package_exists(self, package: str, verbose: bool = False) -> bool:
        # regex here be specific
        cmd = f"{self._package_exists_command} ^{shlex.quote(package)}$"
        return run_in_shell(cmd, verbose=verbose)


class AptPackageManager(PackageManager):
    def __init__(self) -> None:
        super().__init__()
        self._update_command = "DEBIAN_FRONTEND=noninteractive sudo apt-get update"
        self._package_exists_command = "DEBIAN_FRONTEND=noninteractive apt-cache show"  # plus pkg
        self._package_is_installed_command = "dpkg -s"  # plus pkg
        self._package_install_command = (
            "DEBIAN_FRONTEND=noninteractive sudo apt-get install -y"  # plus pkg
        )


class BrewPackageManager(PackageManager):
    def __init__(self) -> None:
        super().__init__()
        self._update_command = "brew update"
        self._package_exists_command = "brew info"  # plus pkg
        self._package_is_installed_command = "brew list"  # plus pkg
        self._package_install_command = "brew install"  # plus pkg


class DnfPackageManager(PackageManager):
    def __init__(self) -> None:
        super().__init__()
        self._update_command = "sudo dnf makecache"
        self._package_exists_command = "dnf list available"  # plus pkg
        self._package_is_installed_command = "dnf list installed"  # plus pkg
        self._package_install_command = "sudo dnf install -y"  # plus pkg


class ZypperPackageManager(PackageManager):
    def __init__(self) -> None:
        super().__init__()
        self._update_command = "sudo zypper refresh"
        self._package_exists_command = "zypper search --match-exact"  # plus pkg
        self._package_is_installed_command = "zypper se --installed-only --match-exact"  # plus pkg
        self._package_install_command = "sudo zypper install --non-interactive"  # plus pkg


class PackageManagerFactory:
    pms = (
        {"executable": "brew", "pm": BrewPackageManager},
        {"executable": "apt-get", "pm": AptPackageManager},
        {"executable": "pacman", "pm": PacmanPackageManager},
        {"executable": "dnf", "pm": DnfPackageManager},
        {"executable": "zypper", "pm": ZypperPackageManager},
    )

    def spawn(self) -> PackageManager:
        for pm_tuple in self.pms:
            if which(pm_tuple["executable"]) is not None:
                return pm_tuple["pm"]()
        msg = "Not supported platform"
        raise RuntimeError(msg)
