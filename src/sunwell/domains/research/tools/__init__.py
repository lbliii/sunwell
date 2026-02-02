"""Research domain tools (RFC-DOMAINS).

Self-registering tools for research and knowledge work:
- web_search: Search the web for information
- summarize: Summarize content
- extract_claims: Extract factual claims from text

Tools are discovered automatically by DynamicToolRegistry.discover()
when sunwell.domains.research.tools is specified as the package.
"""

# Tools are discovered via pkgutil.iter_modules, no explicit imports needed
