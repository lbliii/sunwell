"""Framework parsing."""

from sunwell.core.models.framework import Framework, FrameworkCategory


def parse_framework(data: dict) -> Framework:
    """Parse framework."""
    categories = ()
    if "categories" in data:
        categories = tuple(
            FrameworkCategory(
                name=c["name"],
                purpose=c["purpose"],
                structure=tuple(c.get("structure", [])),
                includes=tuple(c.get("includes", [])),
                excludes=tuple(c.get("excludes", [])),
                triggers=tuple(c.get("triggers", [])),
            )
            for c in data["categories"]
        )

    return Framework(
        name=data["name"],
        description=data.get("description"),
        decision_tree=data.get("decision_tree"),
        categories=categories,
    )
