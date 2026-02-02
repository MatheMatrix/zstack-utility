from __future__ import annotations


class ConfigError(Exception):
    pass


class ConfigLoadError(ConfigError):
    def __init__(self, path: str, message: str):
        self.path = path
        super().__init__(f"Failed to load config '{path}': {message}")


class ConfigValidationError(ConfigError):
    def __init__(self, path: str, message: str):
        self.path = path
        super().__init__(f"Invalid config '{path}': {message}")
