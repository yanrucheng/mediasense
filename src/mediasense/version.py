"""Installed MediaSense application version."""

from importlib.metadata import PackageNotFoundError, version


def application_version() -> str:
    """Read the one version declared by installed package metadata."""

    try:
        return version("mediasense")
    except PackageNotFoundError:
        return "uninstalled"


__version__ = application_version()
