from typing import TYPE_CHECKING, Protocol

from ares.managers.manager_mediator import ManagerMediator

if TYPE_CHECKING:
    from ares import AresBot


class Behavior(Protocol):
    """Interface that all behaviors should adhere to.

    Notes
    -----
    This is in POC stage currently, final design yet to be established.
    Currently only used for `Mining`, but should support combat tasks.
    Should also allow users to creat their own `Behavior` classes.
    And design should allow a series of behaviors to be executed for
    the same set of tags.

    Additionally, `async` methods need further thought.
    """

    def execute(self, ai: "AresBot", config: dict, mediator: ManagerMediator) -> bool:
        """Execute the implemented behavior.

        Parameters
        ----------
        ai :
            Bot object that will be running the game.
        config :
            Dictionary with the data from the configuration file.
        mediator :
            ManagerMediator used for getting information from other managers.

        Returns
        -------
        bool :
            Return value depends on combat / macro behavior interfaces.
            See those interfaces for more info.
        """
        ...
