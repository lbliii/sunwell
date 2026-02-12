# ChirpUI Component Library

Reusable kida template components for Sunwell Studio UI.

## 📦 Available Components

### Forms (`forms.html`)
- `text_field(name, value, label, placeholder, required, errors, attrs)` - Text input with validation
- `textarea_field(name, value, label, placeholder, rows, required, errors, attrs)` - Textarea with validation
- `select_field(name, value, label, options, required, errors, attrs)` - Select dropdown
- `checkbox_field(name, checked, label, errors, attrs)` - Checkbox input

### Layout (`card.html`, `modal.html`)
- `card(variant, padding)` - Card container
- `card_header(title, actions)` - Card header section
- `card_body()` - Card body content
- `card_footer()` - Card footer actions
- `modal(id, title, size)` - Modal dialog
- `modal_actions()` - Modal action buttons

### Feedback (`alert.html`, `toast.html`, `spinner.html`)
- `alert(variant, dismissible, icon)` - Alert messages
- `alert_title()` - Alert title
- `toast(variant, duration, position, icon)` - Toast notifications
- `toast_title()` - Toast title
- `spinner(size, variant, label)` - Loading spinner
- `skeleton(width, height, variant)` - Skeleton loader

### Data Display (`table.html`, `badge.html`, `status.html`)
- `table(variant, striped, hoverable)` - Data table
- `table_header()`, `table_header_cell()`, `table_body()`, `table_row()`, `table_cell()` - Table parts
- `badge(text, variant, icon)` - Badge component
- `status_indicator(status, label, size)` - Status with dot
- `status_badge(text, variant, icon)` - Status badge
- `status_pill(text, variant, dismissible)` - Pill badge

### Navigation (`tabs.html`, `pagination.html`)
- `tabs(variant, size)` - Tab container
- `tab_list()`, `tab()`, `tab_panel()`, `tab_panels()` - Tab parts
- `pagination(current_page, total_pages, show_edges, max_visible)` - Page navigation
- `pagination_info(current_page, per_page, total_items)` - Pagination info

### Interactive (`button.html`, `progress.html`)
- `button(variant, size, disabled, type, attrs)` - Button component
- `button_group(align)` - Button group
- `progress_bar(value, max, variant, show_label, size)` - Progress bar
- `progress_steps(current, total)` - Step indicator

### Utility (`empty.html`)
- `empty_state(icon, title)` - Empty state placeholder

## 🎨 Usage Examples

### Basic Form
```html
{% import "chirpui/forms.html" as forms %}

<form>
    {% call forms.text_field("username", "", "Username", "Enter username", true, errors) %}
        <small class="form-hint">Must be unique</small>
    {% end %}

    {% call forms.textarea_field("bio", "", "Bio", "Tell us about yourself", 4) %}{% end %}

    {% call forms.select_field("role", "", "Role", [
        {"value": "admin", "label": "Administrator"},
        {"value": "user", "label": "User"}
    ], true) %}{% end %}
</form>
```

### Modal with Form
```html
{% import "chirpui/modal.html" as ui_modal %}
{% import "chirpui/forms.html" as forms %}

{% call ui_modal.modal("new-project", "Create Project", "md") %}
    <form>
        {% call forms.text_field("name", "", "Project Name", required=true) %}{% end %}

        {% call ui_modal.modal_actions() %}
            <button type="button" class="btn btn-ghost">Cancel</button>
            <button type="submit" class="btn btn-primary">Create</button>
        {% end %}
    </form>
{% end %}
```

### Card with Content
```html
{% import "chirpui/card.html" as ui_card %}

{% call ui_card.card("primary", "lg") %}
    {% call ui_card.card_header("Project Stats", true) %}
        <button class="btn btn-sm">Refresh</button>
    {% end %}

    {% call ui_card.card_body() %}
        <p>Your project statistics...</p>
    {% end %}

    {% call ui_card.card_footer() %}
        <a href="/more">View More</a>
    {% end %}
{% end %}
```

### Alert Messages
```html
{% import "chirpui/alert.html" as ui_alert %}

{% call ui_alert.alert("success", true, "✓") %}
    {% call ui_alert.alert_title() %}Success!{% end %}
    <p>Your changes have been saved.</p>
{% end %}
```

### Data Table
```html
{% import "chirpui/table.html" as ui_table %}

{% call ui_table.table("default", true, true) %}
    {% call ui_table.table_header() %}
        {% call ui_table.table_header_cell(true, "asc") %}Name{% end %}
        {% call ui_table.table_header_cell() %}Status{% end %}
    {% end %}

    {% call ui_table.table_body() %}
        {% for item in items %}
            {% call ui_table.table_row() %}
                {% call ui_table.table_cell() %}{{ item.name }}{% end %}
                {% call ui_table.table_cell() %}{{ item.status }}{% end %}
            {% end %}
        {% end %}
    {% end %}
{% end %}
```

### Tabs
```html
{% import "chirpui/tabs.html" as ui_tabs %}

{% call ui_tabs.tabs() %}
    {% call ui_tabs.tab_list() %}
        {% call ui_tabs.tab("overview", "Overview", true) %}{% end %}
        {% call ui_tabs.tab("settings", "Settings") %}{% end %}
    {% end %}

    {% call ui_tabs.tab_panels() %}
        {% call ui_tabs.tab_panel("overview", true) %}
            <p>Overview content</p>
        {% end %}

        {% call ui_tabs.tab_panel("settings") %}
            <p>Settings content</p>
        {% end %}
    {% end %}
{% end %}
```

### Progress Indicators
```html
{% import "chirpui/progress.html" as ui_progress %}

{# Progress bar #}
{% call ui_progress.progress_bar(75, 100, "success", true, "lg") %}{% end %}

{# Step progress #}
{% call ui_progress.progress_steps(2, 4) %}{% end %}
```

### Status Indicators
```html
{% import "chirpui/status.html" as ui_status %}

{% call ui_status.status_indicator("success", "Active", "md") %}{% end %}
{% call ui_status.status_badge("Completed", "success", "✓") %}{% end %}
{% call ui_status.status_pill("New", "primary", true) %}{% end %}
```

## 🎯 Component Variants

Most components support these variants:
- **default** - Default styling
- **primary** - Primary brand color
- **success** - Success/positive state
- **warning** - Warning/caution state
- **error/danger** - Error/negative state
- **info** - Informational state
- **muted** - Subdued/secondary

## 📏 Size Options

Components with size support:
- **sm** - Small
- **md** - Medium (default)
- **lg** - Large
- **xl** - Extra large

## ♿ Accessibility

All components include:
- Proper ARIA roles and attributes
- Keyboard navigation support
- Screen reader friendly labels
- Focus management

## 🔧 Customization

Components use CSS custom properties from `chirpui.css` for theming. Override in your theme:

```css
:root {
    --color-primary: #your-color;
    --spacing-md: 1rem;
    --radius-md: 0.5rem;
}
```

## 📝 Contributing

When adding new components:
1. Use `{% def component_name() %}` for definition
2. Use `{{ caller() }}` for content slots
3. Support common variants and sizes
4. Include ARIA attributes
5. Document in this README
