"""
SessionController

Manages session creation and switching.
"""

from typing import TYPE_CHECKING, Optional

from ..core.events import SessionSwitchEvent

if TYPE_CHECKING:
    from ..app import PiCodingAgentApp


class SessionController:
    """
    Session controller for session management
    """

    def __init__(self, app: "PiCodingAgentApp", coding_agent):
        self._app = app
        self._coding_agent = coding_agent
        self._current_session_id: Optional[str] = None

    async def show_session_picker(self) -> None:
        """Show session picker (placeholder)"""
        self._app.message_renderer.add_system_message(
            "Session picker not implemented yet"
        )

    async def create_new_session(self) -> None:
        """Create new session"""
        if not self._coding_agent:
            self._app.message_renderer.add_system_message(
                "No session manager available"
            )
            return

        try:
            session_id = await self._coding_agent.session_manager.create_session(
                self._coding_agent.model.id
            )
            await self.switch_to_session(session_id)
            self._app.message_renderer.add_system_message(
                f"Created new session: {session_id[:8]}"
            )
        except Exception as e:
            self._app.message_renderer.add_system_message(
                f"Failed to create session: {e}"
            )

    async def switch_to_session(self, session_id: str) -> None:
        """Switch to session"""
        self._current_session_id = session_id

        # Publish event
        self._app.event_bus.publish(SessionSwitchEvent(session_id=session_id))

        # Clear and load history
        self._app.message_renderer.clear_conversation()

        if self._coding_agent:
            await self._coding_agent.set_session_id(session_id, load_history=True)

        self._app.layout_manager.update_status_bar(session=session_id[:8])
