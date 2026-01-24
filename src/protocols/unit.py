class UIElement:
    """Base class for UI elements."""

    pass


class Checkbox(UIElement):
    """Checkbox UI element."""

    pass


class Label(UIElement):
    """Label UI element."""

    pass


class Textbox(UIElement):
    """Textbox UI element."""

    pass


class UIProtocol:
    """Protocol for defining game units."""

    elements: list[UIElement]
