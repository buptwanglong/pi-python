"""
Model info modal: show current model (provider, model_id, context_window, max_tokens).
Opened by Ctrl+L.
"""

from textual.screen import ModalScreen
from textual.widgets import Static, Button
from textual.containers import Vertical


class ModelInfoScreen(ModalScreen[None]):
    """Read-only modal showing current model configuration."""

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, provider: str, model_id: str, context_window: int, max_tokens: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self._provider = provider or "-"
        self._model_id = model_id or "-"
        self._context_window = context_window
        self._max_tokens = max_tokens

    def compose(self):
        with Vertical():
            yield Static("当前模型", id="model-info-title")
            yield Static(f"Provider: {self._provider}")
            yield Static(f"Model ID: {self._model_id}")
            yield Static(f"Context window: {self._context_window}")
            yield Static(f"Max tokens: {self._max_tokens}")
            yield Button("关闭", id="model-info-close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "model-info-close":
            self.dismiss(None)
