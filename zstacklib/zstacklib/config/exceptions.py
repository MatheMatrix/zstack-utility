from __future__ import annotations


class ConfigError(Exception):
    """Configerror."""
    pass


class ConfigLoadError(ConfigError):
    """Configloaderror."""
    def __init__(self, path: str, message: str):
        """Init."""
        self.path = path
        super().__init__(f"Failed to load config '{path}': {message}")


class ConfigValidationError(ConfigError):
    """Configvalidationerror."""
    def __init__(self, path: str, message: str):
        """Init."""
        self.path = path
        super().__init__(f"Invalid config '{path}': {message}")
