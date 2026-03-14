"""Interaction layer exceptions."""


class InteractionError(Exception):
    """Base exception for interaction layer.

    All interaction-related exceptions inherit from this class.
    """
    pass


class CommandExecutionError(InteractionError):
    """Raised when a slash command fails to execute.

    This includes parsing errors, validation failures,
    and runtime execution errors.
    """
    pass


class InputProcessingError(InteractionError):
    """Raised when user input cannot be processed.

    This includes malformed input, ambiguous commands,
    or internal processing failures.
    """
    pass


class ModeInitializationError(InteractionError):
    """Raised when an interaction mode fails to initialize.

    This includes session creation failures, adapter setup errors,
    or publisher initialization problems.
    """
    pass
