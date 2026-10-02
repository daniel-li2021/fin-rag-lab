def build_app(*args, **kwargs):
    """Load the local app only when requested, keeping the private factory isolated."""
    from .server import build_app as factory
    return factory(*args, **kwargs)

__all__ = ["build_app"]
