"""Import every quant_research implementation package so its registry
decorators run. Import this module (for its side effects) before resolving
anything from the core registries by name -- used by both the registry
listing endpoint and the Celery task, so it lives in one place."""
import quant_research.cache.duckdb_backend  # noqa: F401
import quant_research.cache.parquet_backend  # noqa: F401
import quant_research.data.sources  # noqa: F401
import quant_research.signals.library  # noqa: F401
import quant_research.strategy.library  # noqa: F401
import quant_research.universe.point_in_time  # noqa: F401
import quant_research.universe.static  # noqa: F401
