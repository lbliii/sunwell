"""Built-in templates for compound learning (RFC-122).

Pre-defined templates that seed the learning system with common task patterns.
These are loaded into SimulacrumStore at initialization.

Templates capture structural patterns for tasks like:
- CRUD endpoints
- Authentication flows
- Service modules
- Data pipelines
"""


from sunwell.memory.simulacrum.core.turn import Learning, TemplateData, TemplateVariable

# =============================================================================
# CRUD Endpoint Template
# =============================================================================


CRUD_ENDPOINT_TEMPLATE = Learning(
    fact="Task pattern: CRUD Endpoint",
    source_turns=(),
    confidence=0.9,
    category="template",
    template_data=TemplateData(
        name="CRUD Endpoint",
        match_patterns=(
            "CRUD",
            "REST API",
            "endpoint",
            "create read update delete",
            "resource API",
        ),
        variables=(
            TemplateVariable(
                name="entity",
                description="Model/resource name (User, Post, Product)",
                var_type="string",
                extraction_hints=(
                    "CRUD for {{entity}}",
                    "{{entity}} API",
                    "{{entity}} endpoint",
                    "REST {{entity}}",
                ),
            ),
        ),
        produces=(
            "{{entity}}Model",
            "{{entity}}Schema",
            "{{entity}}Routes",
            "{{entity}}Tests",
        ),
        requires=(
            "Database",
            "Framework",
        ),
        expected_artifacts=(
            "models/{{entity_lower}}.py",
            "schemas/{{entity_lower}}.py",
            "routes/{{entity_lower}}.py",
            "tests/test_{{entity_lower}}.py",
        ),
        validation_commands=(
            "pytest tests/test_{{entity_lower}}.py -v",
        ),
        suggested_order=50,
    ),
)


# =============================================================================
# Authentication Template
# =============================================================================


AUTH_TEMPLATE = Learning(
    fact="Task pattern: Authentication System",
    source_turns=(),
    confidence=0.9,
    category="template",
    template_data=TemplateData(
        name="Authentication System",
        match_patterns=(
            "authentication",
            "auth system",
            "login",
            "JWT",
            "OAuth",
            "user authentication",
        ),
        variables=(
            TemplateVariable(
                name="auth_type",
                description="Authentication type (jwt, oauth, session)",
                var_type="choice",
                extraction_hints=(
                    "JWT auth",
                    "OAuth {{auth_type}}",
                    "{{auth_type}} authentication",
                ),
                default="jwt",
            ),
        ),
        produces=(
            "AuthConfig",
            "AuthMiddleware",
            "AuthRoutes",
            "UserModel",
        ),
        requires=(
            "Database",
            "Framework",
        ),
        expected_artifacts=(
            "auth/config.py",
            "auth/middleware.py",
            "auth/routes.py",
            "models/user.py",
            "tests/test_auth.py",
        ),
        validation_commands=(
            "pytest tests/test_auth.py -v",
        ),
        suggested_order=10,  # Auth often needs to be early
    ),
)


# =============================================================================
# Service Module Template
# =============================================================================


SERVICE_MODULE_TEMPLATE = Learning(
    fact="Task pattern: Service Module",
    source_turns=(),
    confidence=0.85,
    category="template",
    template_data=TemplateData(
        name="Service Module",
        match_patterns=(
            "service",
            "business logic",
            "service layer",
            "domain service",
        ),
        variables=(
            TemplateVariable(
                name="domain",
                description="Domain/service name (Payment, Notification, Email)",
                var_type="string",
                extraction_hints=(
                    "{{domain}} service",
                    "{{domain}} module",
                    "handle {{domain}}",
                ),
            ),
        ),
        produces=(
            "{{domain}}Service",
            "{{domain}}Repository",
            "{{domain}}Tests",
        ),
        requires=(),
        expected_artifacts=(
            "services/{{domain_lower}}.py",
            "repositories/{{domain_lower}}.py",
            "tests/test_{{domain_lower}}_service.py",
        ),
        validation_commands=(
            "pytest tests/test_{{domain_lower}}_service.py -v",
        ),
        suggested_order=40,
    ),
)


# =============================================================================
# Test Suite Template
# =============================================================================


TEST_SUITE_TEMPLATE = Learning(
    fact="Task pattern: Test Suite",
    source_turns=(),
    confidence=0.85,
    category="template",
    template_data=TemplateData(
        name="Test Suite",
        match_patterns=(
            "test suite",
            "tests for",
            "test coverage",
            "add tests",
            "write tests",
        ),
        variables=(
            TemplateVariable(
                name="module",
                description="Module to test (auth, users, api)",
                var_type="string",
                extraction_hints=(
                    "tests for {{module}}",
                    "test {{module}}",
                    "{{module}} tests",
                ),
            ),
        ),
        produces=(
            "{{module}}UnitTests",
            "{{module}}IntegrationTests",
            "{{module}}Fixtures",
        ),
        requires=(),
        expected_artifacts=(
            "tests/unit/test_{{module_lower}}.py",
            "tests/integration/test_{{module_lower}}_integration.py",
            "tests/fixtures/{{module_lower}}_fixtures.py",
        ),
        validation_commands=(
            "pytest tests/ -v --cov={{module_lower}}",
        ),
        suggested_order=90,  # Tests often last
    ),
)


# =============================================================================
# Built-in Collections
# =============================================================================


BUILTIN_TEMPLATES: tuple[Learning, ...] = (
    CRUD_ENDPOINT_TEMPLATE,
    AUTH_TEMPLATE,
    SERVICE_MODULE_TEMPLATE,
    TEST_SUITE_TEMPLATE,
)
"""All built-in templates for seeding the learning system."""


BUILTIN_CONSTRAINTS: tuple[Learning, ...] = (
    Learning(
        fact="Tests are required for all new features",
        source_turns=(),
        confidence=0.95,
        category="constraint",
    ),
    Learning(
        fact="Type hints required for all public functions",
        source_turns=(),
        confidence=0.9,
        category="constraint",
    ),
    Learning(
        fact="Docstrings required for all public classes and functions",
        source_turns=(),
        confidence=0.85,
        category="constraint",
    ),
)
"""Built-in constraints for code quality."""


BUILTIN_DEAD_ENDS: tuple[Learning, ...] = (
    Learning(
        fact="Synchronous database calls don't work with async frameworks - use async drivers",
        source_turns=(),
        confidence=0.95,
        category="dead_end",
    ),
    Learning(
        fact="Global mutable state causes race conditions in async code",
        source_turns=(),
        confidence=0.9,
        category="dead_end",
    ),
)
"""Built-in dead ends to avoid common pitfalls."""


def load_builtins_into_store(store) -> int:
    """Load all built-in templates, constraints, and dead ends into a SimulacrumStore.

    Args:
        store: SimulacrumStore instance

    Returns:
        Number of learnings loaded
    """
    count = 0
    dag = store.get_dag()

    for learning in BUILTIN_TEMPLATES:
        dag.add_learning(learning)
        count += 1

    for learning in BUILTIN_CONSTRAINTS:
        dag.add_learning(learning)
        count += 1

    for learning in BUILTIN_DEAD_ENDS:
        dag.add_learning(learning)
        count += 1

    return count
