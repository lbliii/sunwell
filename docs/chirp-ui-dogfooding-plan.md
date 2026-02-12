# Chirp-UI Dogfooding & Improvement Plan

## Current State Analysis

chirp-ui is a **headless, htmx-native component library** using Kida template macros. Current components (v0.1):

| Component | Status | htmx Features |
|-----------|--------|---------------|
| card | ✅ Complete | Native `<details>` for collapse |
| modal | ✅ Complete | Native `<dialog>` |
| tabs | ✅ Complete | htmx tab switching |
| dropdown | ✅ Complete | Native `<details>` |
| toast | ✅ Complete | htmx OOB swap |
| table | ✅ Complete | htmx sortable headers |
| pagination | ✅ Complete | htmx page nav |
| alert | ✅ Complete | Static display |
| forms | ✅ Complete | Field macros with errors |

**Strengths:**
- ✅ Zero JavaScript (uses native HTML5 APIs)
- ✅ htmx-native design
- ✅ Headless/minimal styling (BEM classes + CSS custom properties)
- ✅ Composable (`{% slot %}` for content injection)
- ✅ Clean Kida macro API

**Gaps for Sunwell:**
- ❌ No Holy Light theme
- ❌ Missing components: badges, spinners, empty states, progress bars
- ❌ No SSE/streaming components
- ❌ No status indicators or confidence bars
- ❌ Not currently used in Sunwell (still using inline styles)

## Improvement Strategy

### Phase 1: Holy Light Theme (Week 1)

Create `chirpui-holy-light.css` that overrides chirp-ui's CSS custom properties with Sunwell's Holy Light colors.

**File:** `/Users/llane/Documents/github/python/chirp-ui/src/chirp_ui/templates/themes/holy-light.css`

```css
/* chirp-ui Holy Light Theme
 * Sunwell's signature gold/void color palette for chirp-ui components.
 */

:root {
    /* Holy Spectrum - Light, positive, active */
    --chirpui-color-radiant: #ffd700;
    --chirpui-color-gold: #c9a227;
    --chirpui-color-gold-dim: #8a7235;
    --chirpui-color-success: #22c55e;

    /* Void Spectrum - Shadow, danger, unknown */
    --chirpui-color-void-purple: #7c3aed;
    --chirpui-color-void-indigo: #4f46e5;
    --chirpui-color-void-deep: #2e1065;

    /* Neutral - The canvas */
    --chirpui-bg: #0d0d0d;
    --chirpui-surface: #1a1a1a;
    --chirpui-surface-elevated: #262626;
    --chirpui-border: #333333;
    --chirpui-text: #e5e5e5;
    --chirpui-text-muted: #a8a8a8;

    /* Component-specific overrides */
    --chirpui-card-bg: var(--chirpui-surface);
    --chirpui-card-border: var(--chirpui-border);
    --chirpui-card-header-color: var(--chirpui-color-gold);

    --chirpui-modal-bg: var(--chirpui-surface-elevated);
    --chirpui-modal-border: var(--chirpui-color-gold-dim);

    --chirpui-alert-info-bg: rgba(201, 162, 39, 0.15);
    --chirpui-alert-info-border: var(--chirpui-color-gold-dim);
    --chirpui-alert-success-bg: rgba(34, 197, 94, 0.15);
    --chirpui-alert-success-border: var(--chirpui-color-success);
    --chirpui-alert-warning-bg: rgba(79, 70, 229, 0.15);
    --chirpui-alert-warning-border: var(--chirpui-color-void-indigo);
    --chirpui-alert-error-bg: rgba(124, 58, 237, 0.15);
    --chirpui-alert-error-border: var(--chirpui-color-void-purple);

    /* Interactive states */
    --chirpui-focus-ring: rgba(255, 215, 0, 0.3);
    --chirpui-hover-bg: var(--chirpui-surface-elevated);

    /* Transitions */
    --chirpui-transition-fast: 150ms ease;
    --chirpui-transition-normal: 250ms ease;
}

/* Card hover effect */
.chirpui-card:hover {
    border-color: var(--chirpui-color-gold);
    box-shadow: 0 4px 12px rgba(255, 215, 0, 0.15);
}

/* Focus states */
button:focus,
input:focus,
textarea:focus,
select:focus {
    outline: none;
    box-shadow: 0 0 0 3px var(--chirpui-focus-ring);
}

/* Modal radiant glow */
.chirpui-modal__title {
    color: var(--chirpui-color-radiant);
    text-shadow: 0 0 10px rgba(255, 215, 0, 0.2);
}
```

### Phase 2: New Components (Week 2-3)

Add components that Sunwell needs but chirp-ui is missing.

#### 2.1 Badge Component

**File:** `src/chirp_ui/templates/chirpui/badge.html`

```html
{#- chirp-ui: Badge component
    Small status indicators with semantic variants.

    Usage:
        from "chirpui/badge.html" import badge

        badge("Active", variant="success")
        badge("Pending", variant="warning", icon="◆")
-#}

{% def badge(text, variant="primary", icon=none, cls="") %}
<span class="chirpui-badge chirpui-badge--{{ variant }}{{ " " ~ cls if cls else "" }}">
    {% if icon %}
        <span class="chirpui-badge__icon">{{ icon }}</span>
    {% end %}
    {{ text }}
</span>
{% end %}
```

**CSS:**
```css
.chirpui-badge {
    display: inline-flex;
    align-items: center;
    gap: var(--chirpui-spacing-xs);
    padding: 0.25rem 0.5rem;
    border-radius: var(--chirpui-radius-sm);
    font-size: var(--chirpui-font-sm);
    font-weight: 500;
    border: 1px solid;
}

.chirpui-badge--primary {
    background: rgba(255, 215, 0, 0.15);
    color: var(--chirpui-color-radiant);
    border-color: var(--chirpui-color-gold-dim);
}

.chirpui-badge--success {
    background: rgba(34, 197, 94, 0.15);
    color: var(--chirpui-color-success);
    border-color: var(--chirpui-color-success);
}

.chirpui-badge--error {
    background: rgba(124, 58, 237, 0.15);
    color: var(--chirpui-color-void-purple);
    border-color: var(--chirpui-color-void-purple);
}

.chirpui-badge__icon {
    font-size: 1em;
}
```

#### 2.2 Spinner Component

**File:** `src/chirp_ui/templates/chirpui/spinner.html`

```html
{#- chirp-ui: Spinner component
    Loading indicators with Holy Light mote animation.

    Usage:
        from "chirpui/spinner.html" import spinner, spinner_thinking

        spinner()  # Mote pulse
        spinner_thinking()  # Spiral rotation
-#}

{% def spinner(size="md", cls="") %}
<span class="chirpui-spinner chirpui-spinner--{{ size }}{{ " " ~ cls if cls else "" }}"
      role="status"
      aria-label="Loading">
    <span class="chirpui-spinner__mote">✦</span>
</span>
{% end %}

{% def spinner_thinking(size="md", cls="") %}
<span class="chirpui-spinner-thinking chirpui-spinner-thinking--{{ size }}{{ " " ~ cls if cls else "" }}"
      role="status"
      aria-label="Processing">
    <span class="chirpui-spinner__char">◜</span>
</span>
{% end %}
```

**CSS:**
```css
.chirpui-spinner {
    display: inline-block;
    color: var(--chirpui-color-radiant);
    line-height: 1;
}

.chirpui-spinner__mote {
    display: inline-block;
    animation: mote-pulse 0.9s ease-in-out infinite;
}

@keyframes mote-pulse {
    0%, 100% {
        content: "·";
        opacity: 0.3;
        transform: scale(0.8);
    }
    33% {
        content: "✧";
        opacity: 0.7;
        transform: scale(1);
    }
    66% {
        content: "✦";
        opacity: 1;
        transform: scale(1.1);
    }
}

.chirpui-spinner-thinking__char {
    display: inline-block;
    animation: spiral-rotate 0.6s steps(4) infinite;
}

@keyframes spiral-rotate {
    0% { content: "◜"; }
    25% { content: "◝"; }
    50% { content: "◞"; }
    75% { content: "◟"; }
}

@media (prefers-reduced-motion: reduce) {
    .chirpui-spinner__mote,
    .chirpui-spinner-thinking__char {
        animation: none;
    }
}
```

#### 2.3 Empty State Component

**File:** `src/chirp_ui/templates/chirpui/empty.html`

```html
{#- chirp-ui: Empty State component
    Placeholder for empty lists/collections.

    Usage:
        from "chirpui/empty.html" import empty_state

        call empty_state(icon="✧", title="No Projects")
            <p>Create your first project to get started.</p>
            <button>+ New Project</button>
        end
-#}

{% def empty_state(icon=none, title="No items", cls="") %}
<div class="chirpui-empty-state{{ " " ~ cls if cls else "" }}">
    {% if icon %}
        <div class="chirpui-empty-state__icon">{{ icon }}</div>
    {% end %}
    <h2 class="chirpui-empty-state__title">{{ title }}</h2>
    <div class="chirpui-empty-state__body">
        {% slot %}
    </div>
</div>
{% end %}
```

**CSS:**
```css
.chirpui-empty-state {
    text-align: center;
    padding: var(--chirpui-spacing) * 2;
    color: var(--chirpui-text-muted);
}

.chirpui-empty-state__icon {
    font-size: 3rem;
    margin-bottom: var(--chirpui-spacing);
    color: var(--chirpui-color-gold-dim);
}

.chirpui-empty-state__title {
    margin: 0 0 var(--chirpui-spacing-sm) 0;
    color: var(--chirpui-text);
}
```

#### 2.4 Progress Bar Component

**File:** `src/chirp_ui/templates/chirpui/progress.html`

```html
{#- chirp-ui: Progress Bar component
    Visual progress indicator with Holy Light gradient.

    Usage:
        from "chirpui/progress.html" import progress_bar

        progress_bar(value=60, max=100, label="60% complete")
        progress_bar(value=3, max=5, variant="radiant")
-#}

{% def progress_bar(value, max=100, label=none, variant="gold", cls="") %}
<div class="chirpui-progress-bar chirpui-progress-bar--{{ variant }}{{ " " ~ cls if cls else "" }}"
     role="progressbar"
     aria-valuenow="{{ value }}"
     aria-valuemin="0"
     aria-valuemax="{{ max }}">
    <div class="chirpui-progress-bar__fill"
         style="width: {{ (value / max * 100) }}%">
    </div>
    {% if label %}
        <span class="chirpui-progress-bar__label">{{ label }}</span>
    {% end %}
</div>
{% end %}
```

**CSS:**
```css
.chirpui-progress-bar {
    position: relative;
    height: 0.5rem;
    background: var(--chirpui-surface-elevated);
    border-radius: var(--chirpui-radius-sm);
    overflow: hidden;
}

.chirpui-progress-bar__fill {
    height: 100%;
    transition: width var(--chirpui-transition-normal);
}

.chirpui-progress-bar--gold .chirpui-progress-bar__fill {
    background: var(--chirpui-color-gold);
}

.chirpui-progress-bar--radiant .chirpui-progress-bar__fill {
    background: linear-gradient(90deg, var(--chirpui-color-gold), var(--chirpui-color-radiant));
}

.chirpui-progress-bar__label {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    font-size: var(--chirpui-font-sm);
    color: var(--chirpui-text);
    font-weight: 500;
}
```

#### 2.5 Status Indicator Component

**File:** `src/chirp_ui/templates/chirpui/status.html`

```html
{#- chirp-ui: Status Indicator component
    Visual status with icon and label.

    Usage:
        from "chirpui/status.html" import status_indicator

        status_indicator("Running", variant="success")
        status_indicator("Error", variant="error", icon="⚠")
-#}

{% def status_indicator(label, variant="default", icon=none, pulse=false, cls="") %}
<div class="chirpui-status-indicator chirpui-status-indicator--{{ variant }}{{ " chirpui-status-indicator--pulse" if pulse else "" }}{{ " " ~ cls if cls else "" }}">
    {% if icon %}
        <span class="chirpui-status-indicator__icon">{{ icon }}</span>
    {% else %}
        <span class="chirpui-status-indicator__dot"></span>
    {% end %}
    <span class="chirpui-status-indicator__label">{{ label }}</span>
</div>
{% end %}
```

**CSS:**
```css
.chirpui-status-indicator {
    display: inline-flex;
    align-items: center;
    gap: var(--chirpui-spacing-xs);
    padding: 0.25rem 0.5rem;
    border-radius: var(--chirpui-radius-sm);
    font-size: var(--chirpui-font-sm);
    font-weight: 500;
}

.chirpui-status-indicator__dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
}

.chirpui-status-indicator--success {
    background: rgba(34, 197, 94, 0.15);
    color: var(--chirpui-color-success);
}

.chirpui-status-indicator--success .chirpui-status-indicator__dot {
    background: var(--chirpui-color-success);
}

.chirpui-status-indicator--error {
    background: rgba(124, 58, 237, 0.15);
    color: var(--chirpui-color-void-purple);
}

.chirpui-status-indicator--error .chirpui-status-indicator__dot {
    background: var(--chirpui-color-void-purple);
}

.chirpui-status-indicator--pulse .chirpui-status-indicator__dot {
    animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
    0%, 100% {
        opacity: 1;
    }
    50% {
        opacity: 0.5;
    }
}
```

### Phase 3: Dogfood in Sunwell (Week 4)

Replace Sunwell's custom CSS and inline styles with chirp-ui components.

#### 3.1 Install chirp-ui in Sunwell

```bash
cd /Users/llane/Documents/github/python/sunwell
pip install -e ../chirp-ui
```

#### 3.2 Update Sunwell's base template

```html
<!-- src/sunwell/interface/chirp/pages/_layout.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    ...
    <!-- chirp-ui base styles -->
    <link rel="stylesheet" href="/static/chirpui.css">
    <!-- Holy Light theme -->
    <link rel="stylesheet" href="/static/themes/holy-light.css">
    <!-- Sunwell custom -->
    <link rel="stylesheet" href="/static/css/theme.css">
    ...
</head>
```

#### 3.3 Convert existing components

**Example: Project Card**

**Before** (custom HTML):
```html
<div class="card project-card">
    <h3>{{ project.name }}</h3>
    <p>{{ project.description }}</p>
    {% if project.is_default %}
        <span class="badge badge-primary">Default</span>
    {% end %}
</div>
```

**After** (chirp-ui):
```html
{% from "chirpui/card.html" import card %}
{% from "chirpui/badge.html" import badge %}

{% call card(title=project.name) %}
    <p>{{ project.description }}</p>
    {% if project.is_default %}
        {{ badge("Default", variant="primary", icon="✦") }}
    {% end %}
{% end %}
```

**Example: Empty States**

**Before**:
```html
<div class="empty-state card">
    <div class="empty-state-icon">✧</div>
    <h2>No Projects Yet</h2>
    <p class="text-muted">Create your first project to get started</p>
</div>
```

**After**:
```html
{% from "chirpui/empty.html" import empty_state %}

{% call empty_state(icon="✧", title="No Projects Yet") %}
    <p class="text-muted">Create your first project to get started</p>
{% end %}
```

**Example: Modals**

**Before**:
```html
<div id="modal-container"></div>
<button hx-get="/projects/new-form" hx-target="#modal-container">
    + New Project
</button>
```

**After**:
```html
{% from "chirpui/modal.html" import modal, modal_trigger %}

{{ modal_trigger("new-project-modal", label="+ New Project") }}

{% call modal("new-project-modal", title="New Project", size="medium") %}
    <!-- form content via htmx -->
    <div hx-get="/projects/new-form" hx-trigger="load"></div>
{% end %}
```

### Phase 4: Advanced htmx Components (Week 5+)

Add components that leverage htmx's advanced features.

#### 4.1 SSE Stream Component

**File:** `src/chirp_ui/templates/chirpui/stream.html`

```html
{#- chirp-ui: SSE Stream component
    Live-updating content via Server-Sent Events.

    Usage:
        from "chirpui/stream.html" import sse_stream

        call sse_stream(url="/logs/stream", event_name="log-entry")
            <!-- Initial content -->
        end
-#}

{% def sse_stream(url, event_name, swap="beforeend", cls="") %}
<div class="chirpui-stream{{ " " ~ cls if cls else "" }}"
     hx-ext="sse"
     sse-connect="{{ url }}"
     sse-swap="{{ event_name }}"
     hx-swap="{{ swap }}">
    {% slot %}
</div>
{% end %}
```

#### 4.2 Live Search Component

**File:** `src/chirp_ui/templates/chirpui/search.html`

```html
{#- chirp-ui: Live Search component
    Debounced search with htmx.

    Usage:
        from "chirpui/search.html" import live_search

        live_search(url="/search", target="#results", placeholder="Search projects...")
-#}

{% def live_search(url, target, placeholder="Search...", debounce="300ms", cls="") %}
<input type="search"
       class="chirpui-search{{ " " ~ cls if cls else "" }}"
       placeholder="{{ placeholder }}"
       hx-get="{{ url }}"
       hx-trigger="keyup changed delay:{{ debounce }}"
       hx-target="{{ target }}"
       hx-indicator=".search-indicator">
<span class="search-indicator htmx-indicator">
    {% from "chirpui/spinner.html" import spinner %}
    {{ spinner(size="sm") }}
</span>
{% end %}
```

#### 4.3 Infinite Scroll Component

**File:** `src/chirp_ui/templates/chirpui/infinite.html`

```html
{#- chirp-ui: Infinite Scroll component
    Load more content on scroll intersection.

    Usage:
        from "chirpui/infinite.html" import infinite_scroll

        infinite_scroll(url="/items?page=2", target="#items-list")
-#}

{% def infinite_scroll(url, target, threshold="0.5", cls="") %}
<div class="chirpui-infinite-scroll{{ " " ~ cls if cls else "" }}"
     hx-get="{{ url }}"
     hx-trigger="intersect threshold:{{ threshold }}"
     hx-target="{{ target }}"
     hx-swap="beforeend">
    {% from "chirpui/spinner.html" import spinner %}
    <div class="chirpui-infinite-scroll__loading">
        {{ spinner() }}
        <p>Loading more...</p>
    </div>
</div>
{% end %}
```

## Testing Strategy

### Unit Tests

Test component rendering and variants:

```python
# tests/test_components.py
from chirp_ui import get_loader
from kida import Environment

def test_badge_variants():
    env = Environment(loader=get_loader())
    template = env.get_template("chirpui/badge.html")

    # Test primary variant
    html = template.module.badge("Active", variant="primary")
    assert "chirpui-badge--primary" in html
    assert "Active" in html

    # Test with icon
    html = template.module.badge("Success", variant="success", icon="✓")
    assert "✓" in html
    assert "chirpui-badge__icon" in html
```

### Visual Regression Tests

Capture screenshots of all components in different states:

```python
# tests/test_visual.py
from playwright.sync_api import sync_playwright

def test_component_screenshots():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # Render component showcase
        page.goto("http://localhost:8080/showcase")

        # Screenshot each component
        page.locator(".chirpui-badge").screenshot(path="screenshots/badge.png")
        page.locator(".chirpui-card").screenshot(path="screenshots/card.png")

        # Compare with baseline
        # ...
```

## Documentation

### Component Showcase Page

Create a live showcase of all chirp-ui components:

**File:** `docs/showcase.html`

```html
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="../src/chirp_ui/templates/chirpui.css">
    <link rel="stylesheet" href="../src/chirp_ui/templates/themes/holy-light.css">
</head>
<body>
    <h1>chirp-ui Component Showcase</h1>

    <section>
        <h2>Badges</h2>
        {{ badge("Primary", variant="primary") }}
        {{ badge("Success", variant="success", icon="✓") }}
        {{ badge("Error", variant="error", icon="✗") }}
    </section>

    <section>
        <h2>Cards</h2>
        {% call card(title="Project Card") %}
            <p>Card content goes here.</p>
        {% end %}
    </section>

    <!-- ... all components ... -->
</body>
</html>
```

## Migration Checklist

### chirp-ui improvements:
- [ ] Add Holy Light theme CSS file
- [ ] Implement badge component
- [ ] Implement spinner components (mote pulse, spiral)
- [ ] Implement empty state component
- [ ] Implement progress bar component
- [ ] Implement status indicator component
- [ ] Add SSE stream component
- [ ] Add live search component
- [ ] Add infinite scroll component
- [ ] Create component showcase page
- [ ] Add visual regression tests

### Sunwell dogfooding:
- [ ] Install chirp-ui as dependency
- [ ] Include chirp-ui CSS in base template
- [ ] Include Holy Light theme
- [ ] Convert project cards to use chirp-ui
- [ ] Convert empty states to use chirp-ui
- [ ] Convert modals to use chirp-ui
- [ ] Convert tables to use chirp-ui
- [ ] Convert alerts to use chirp-ui
- [ ] Convert forms to use chirp-ui
- [ ] Remove redundant custom CSS

## Benefits

**For chirp-ui:**
- Real-world usage and testing
- Production-ready Holy Light theme
- More components for the library
- Better documentation via Sunwell usage

**For Sunwell:**
- Consistent UI components
- Less custom CSS to maintain
- Better accessibility (chirp-ui components are semantic)
- Easier onboarding (documented components)

## Timeline

- **Week 1:** Holy Light theme + basic component additions
- **Week 2:** Remaining component implementations
- **Week 3:** Sunwell integration prep (install, test)
- **Week 4:** Dogfood in Sunwell (convert pages)
- **Week 5+:** Advanced components, polish, documentation

Total: ~5 weeks for full integration.
