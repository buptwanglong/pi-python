"""Interaction layer exceptions."""


class InteractionError(Exception):
    """Base exception for interaction layer."""
    pass


class CommandExecutionError(InteractionError):
    """Command execution failed."""
    pass


class InputProcessingError(InteractionError):
    """Input processing failed."""
    pass


class ModeInitializationError(InteractionError):
    """Mode initialization failed."""
    pass
