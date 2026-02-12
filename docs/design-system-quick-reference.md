# Design System Quick Reference

## 🎨 Biomorphic Components

```html
{% import "bio-card.html" as bio %}
{% import "particles.html" as fx %}

{# Cards #}
{% call bio.bio_card(variant="radiant", glow=true, breathe=true) %}...{% end %}
{% call bio.bio_card(morph=true, interactive=true) %}...{% end %}

{# Buttons #}
{% call bio.bio_button() %}Cast Spell{% end %}

{# Progress #}
{% call bio.bio_progress(value=75, label="Mana") %}{% end %}

{# Input #}
{% call bio.bio_input(placeholder="Enter...") %}{% end %}

{# Particles #}
{% call fx.ambient_particles(count=8) %}{% end %}
{% call fx.particle_burst(trigger_selector=".btn") %}{% end %}
```

## 🔘 Button Variants

```html
{% import "button-variants.html" as btn %}

{# Variants #}
{% call btn.button(variant="primary|secondary|ghost|danger|success") %}
{% call btn.button(size="sm|md|lg|xl") %}
{% call btn.button(loading=true|false, disabled=true|false) %}
{% call btn.button(icon="✦", icon_position="left|right") %}
{% call btn.button(bio=true) %}  {# Biomorphic style #}

{# Icon button #}
{% call btn.icon_button("⚙️", label="Settings") %}{% end %}

{# Button group #}
{% call btn.button_group(attached=true) %}
  {% call btn.button() %}First{% end %}
  {% call btn.button() %}Second{% end %}
{% end %}
```

## 🎭 Themes

```html
{% import "theme-switcher.html" as themes %}
{% call themes.theme_switcher() %}{% end %}
```

```javascript
// JavaScript API
window.setTheme('holy-light|void|forest|ocean');
```

## ⌨️ Command Palette

- **Open:** `Cmd/Ctrl+K`
- **Navigate:** `↑↓`
- **Execute:** `Enter`
- **Close:** `ESC`

```html
{% import "command-palette.html" as cmd %}
{% call cmd.command_palette() %}{% end %}
```

## 🌀 Spring Animations

```html
{# Hover effects #}
<div class="spring-scale">Scale on hover</div>
<div class="spring-lift">Lift on hover</div>
<div class="spring-rotate">Rotate on hover</div>
<button class="btn-spring">Button press</button>
<button class="elastic-btn">Elastic bounce</button>

{# Entrance animations #}
<div class="spring-bounce-in">Bounce in</div>
<div class="spring-slide-in">Slide in</div>
<div class="card-spring-enter">Card entrance</div>
<div class="modal-spring">Modal scale</div>

{# Continuous #}
<div class="spring-breathe">Breathing</div>
<div class="spring-float">Floating</div>

{# Stagger group #}
<div class="spring-stagger">
  <div>Item 1</div>
  <div>Item 2</div>
  <div>Item 3</div>
</div>
```

## 🎨 Utility Classes

### Layout
```html
<div class="stack">              <!-- Vertical -->
<div class="stack-sm|lg|xl">     <!-- Spacing variants -->
<div class="cluster">            <!-- Horizontal wrap -->
<div class="grid grid-auto">     <!-- Auto-responsive -->
<div class="switcher">           <!-- Conditional layout -->
<div class="center">             <!-- Perfect center -->
```

### Animations
```html
<div class="scroll-fade-in">     <!-- Scroll reveal -->
<div class="hover-lift">         <!-- Lift on hover -->
<div class="hover-scale">        <!-- Scale on hover -->
<div class="hover-glow">         <!-- Glow on hover -->
<div class="animate-pulse-glow"> <!-- Continuous pulse -->
```

### Biomorphic
```html
<div class="blob">               <!-- Organic shape -->
<div class="blob-morph">         <!-- Morphing blob -->
<div class="blob-breathe">       <!-- Breathing blob -->
<div class="holy-radiance">      <!-- Multi-layer glow -->
<div class="holy-pulse">         <!-- Pulsing light -->
<div class="halo">               <!-- Ring of light -->
<div class="light-rays">         <!-- Rotating rays -->
<div class="holy-shimmer">       <!-- Divine sparkle -->
```

## 🎯 Design Tokens

### Spacing
```css
var(--space-3xs)   /* 4-5px */
var(--space-sm)    /* 16-20px */
var(--space-md)    /* 24-30px */  ← Most common
var(--space-lg)    /* 32-40px */
var(--space-xl)    /* 48-60px */
```

### Typography
```css
var(--text-xs)     /* 12-14px */
var(--text-base)   /* 16-18px */  ← Body text
var(--text-lg)     /* 18-21px */
var(--text-2xl)    /* 24-32px */
var(--text-4xl)    /* 36-54px */
```

### Colors
```css
var(--color-primary)            /* Theme primary */
var(--color-primary-glow)       /* Glow color */
var(--color-surface)            /* Card background */
var(--color-text)               /* Primary text */
var(--color-text-muted)         /* Secondary text */
```

### Shadows & Effects
```css
var(--shadow-sm|md|lg|xl)       /* Layered shadows */
var(--glow-sm|md|lg)            /* Holy glows */
var(--radius-sm|md|lg|xl)       /* Border radius */
```

### Animations
```css
var(--duration-fast)            /* 150ms */
var(--duration-normal)          /* 250ms */
var(--duration-slow)            /* 350ms */

var(--ease-out)                 /* Standard */
var(--ease-bounce)              /* Bouncy */

var(--spring-gentle)            /* Soft spring */
var(--spring-medium)            /* Standard spring */
var(--spring-bounce)            /* Strong spring */
var(--spring-elastic)           /* Overshoot */
```

## 📦 Component Badges

```html
<span class="badge badge--primary|success|warning|danger|radiant">
<span class="badge badge--sm|lg">
```

## 📝 Inputs

```html
<input class="input">
<input class="input input--error|success">
<input class="input input--sm|lg">
<input class="bio-input">  <!-- Organic style -->
```

## 🎴 Cards

```html
<div class="card">                      <!-- Standard -->
<div class="card card--elevated">      <!-- Higher shadow -->
<div class="card card--bordered">      <!-- Border style -->
<div class="card card--flat">          <!-- No shadow -->
<div class="card card--gradient">      <!-- Gradient bg -->
<div class="card card--sm|lg">         <!-- Size variants -->
<div class="card card-interactive">    <!-- Hover effects -->
```

## 🎨 Complete Example

```html
{% import "bio-card.html" as bio %}
{% import "button-variants.html" as btn %}
{% import "particles.html" as fx %}

{# Floating magic #}
{% call fx.ambient_particles(count=6) %}{% end %}

<div class="stack stack-xl">
  <header class="scroll-fade-in">
    <h1>My Page</h1>
  </header>

  <div class="grid grid-auto spring-stagger">
    {% call bio.bio_card(variant="radiant", interactive=true) %}
      <div class="stack stack-sm">
        <h3>✦ Divine Card</h3>
        <p class="text-muted">Holy biomorphic design</p>

        <div class="cluster">
          <span class="badge badge--radiant">Active</span>
        </div>

        {% call btn.button(variant="primary", bio=true) %}
          Open
        {% end %}
      </div>
    {% end %}
  </div>
</div>
```

---

**Full docs:** `NEXT_LEVEL_DESIGN_SYSTEM.md`
**Showcase:** `/biomorphic-showcase`
**Command Palette:** `Cmd/Ctrl+K`
