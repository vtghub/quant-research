class QuantResearchError(Exception):
    """Base class for all errors raised by quant_research."""


class ConfigError(QuantResearchError):
    """Raised when a pipeline config fails validation or references an unknown registry name."""


class DataSourceError(QuantResearchError):
    """Raised when a data vendor returns no data, malformed data, or an unrecoverable error."""


class CacheError(QuantResearchError):
    """Raised on cache read/write failures."""


class RegistryError(QuantResearchError):
    """Raised on duplicate registration or lookup of an unknown registry name."""


class HookAbort(QuantResearchError):
    """Raise from inside a hook callback to deliberately halt the pipeline run."""
