class UIElement:
    """Base class for UI elements."""

    pass


class Checkbox(UIElement):
    """Checkbox extends UIElement."""

    pass


class Label(UIElement):
    """Label extends UIElement."""

    pass


class Textbox(UIElement):
    """Textbox extends UIElement."""

    pass


class UIProtocol:
    """
    Represents the game map protocol.
    Contains a list of UI elements.
    """

    def __init__(self, elements: list[UIElement]):
        self.elements = elements
