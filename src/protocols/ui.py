type PropertyValue = str | int | float | bool


class UIElement:
    """Base class for all UI elements."""

    def __init__(
        self,
        id: str,
        label: str = "",
        properties: dict[str, PropertyValue] | None = None,
    ):
        self.id = id
        self.label = label
        self.properties = properties or {}

    def render(self) -> str:
        """Abstract method to render the element."""
        raise NotImplementedError


class Button(UIElement):
    def __init__(
        self,
        id: str,
        label: str,
        properties: dict[str, PropertyValue] | None = None,
    ):
        super().__init__(id, label, properties)
        self.is_enabled = self.properties.get("is_enabled", True)

    def render(self) -> str:
        return (
            f'<button id="{self.id}" label="{self.label}" '
            f'is_enabled="{self.is_enabled}"></button>'
        )


class TextField(UIElement):
    def __init__(
        self,
        id: str,
        label: str,
        properties: dict[str, PropertyValue] | None = None,
    ):
        super().__init__(id, label, properties)
        self.placeholder = self.properties.get("placeholder", "")

    def render(self) -> str:
        return (
            f'<input type="text" id="{self.id}" label="{self.label}" '
            f'placeholder="{self.placeholder}"></input>'
        )


class Checkbox(UIElement):
    def __init__(
        self,
        id: str,
        label: str,
        properties: dict[str, PropertyValue] | None = None,
    ):
        super().__init__(id, label, properties)
        self.is_checked = self.properties.get("is_checked", False)

    def render(self) -> str:
        return (
            f'<input type="checkbox" id="{self.id}" label="{self.label}" '
            f'is_checked="{self.is_checked}"></input>'
        )


class Label(UIElement):
    def __init__(
        self,
        id: str,
        label: str,
        properties: dict[str, PropertyValue] | None = None,
    ):
        super().__init__(id, label, properties)

    def render(self) -> str:
        return f'<label id="{self.id}" label="{self.label}"></label>'


class Textbox(UIElement):
    def __init__(
        self,
        id: str,
        label: str,
        properties: dict[str, PropertyValue] | None = None,
    ):
        super().__init__(id, label, properties)
        self.value = self.properties.get("value", "")

    def render(self) -> str:
        return (
            f'<input type="text" id="{self.id}" label="{self.label}" '
            f'value="{self.value}"></input>'
        )


class UIProtocol:
    """Protocol defining the user interface elements."""

    elements: list[Button | TextField | Checkbox | Label | Textbox]

    def generate_ui(self) -> str:
        """Generates the UI string based on the defined elements."""
        ui_string = ""
        for element in self.elements:
            ui_string += element.render() + "\n"
        return ui_string


# Example Usage
if __name__ == "__main__":
    protocol = UIProtocol()
    protocol.elements = [
        Button(id="submit_button", label="Submit", properties={"is_enabled": True}),
        TextField(
            id="username",
            label="Username",
            properties={"placeholder": "Enter your username"},
        ),
        Checkbox(
            id="agree",
            label="I agree to the terms and conditions",
            properties={"is_checked": True},
        ),
        Label(id="greeting", label="Hello,"),
        Textbox(id="password", label="Password", properties={"value": "password"}),
    ]

    ui_code = protocol.generate_ui()
    print(ui_code)
