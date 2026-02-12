# Sunwell Design System 2.0

Modern, fluid design system leveraging 2026 CSS features for polished, responsive interfaces.

## 🎨 What's New

### 1. **Fluid Spacing & Typography**
No more chunky, rigid spacing! Uses `clamp()` for smooth scaling across all viewport sizes.

**Before:**
```css
padding: 16px; /* Fixed, looks chunky on larger screens */
```

**After:**
```css
padding: var(--space-md); /* 24-30px, scales smoothly */
```

**Available Scales:**
- **Spacing:** `--space-3xs` through `--space-3xl` (4px → 120px, fluid)
- **Typography:** `--text-xs` through `--text-4xl` (12px → 54px, fluid)

### 2. **Modern Color System (oklch)**
Perceptually uniform colors that look better and scale predictably.

**Before:**
```css
color: #d4af37; /* RGB, not perceptually uniform */
```

**After:**
```css
color: var(--color-gold); /* oklch(70% 0.13 85) - perceptually uniform */
```

**Color Palette:**
- `--color-radiant`, `--color-gold`, `--color-gold-dim`
- `--color-void-purple`, `--color-void-indigo`, `--color-void-deep`
- Neutral scale from `--color-bg` to `--color-text`

### 3. **Container Queries**
Components adapt to their own size, not just viewport!

```html
<div class="card">
  <div class="card-content">
    <!-- Switches to grid layout when card > 400px wide -->
  </div>
</div>
```

### 4. **Auto-Responsive Grids**
No more media queries for basic responsive layouts!

```html
<!-- Automatically responsive - each item 15-20rem wide -->
<div class="grid grid-auto">
  <div>Card 1</div>
  <div>Card 2</div>
  <div>Card 3</div>
</div>
```

### 5. **Scroll-Driven Animations**
Elements animate as they scroll into view - no JavaScript!

```html
<div class="scroll-fade-in">
  <!-- Fades in as user scrolls to it -->
</div>
```

### 6. **Modern CSS Selectors**
`:has()`, `:is()`, `:where()` for powerful, clean styles.

```css
/* Card automatically adjusts padding if it has actions */
.card:has(.card-actions) {
  padding-block-end: var(--space-lg);
}
```

## 📐 Layout Primitives

### Container
```html
<div class="container">
  <!-- Max-width 1280px, fluid padding -->
</div>

<div class="container container-md">
  <!-- Smaller max-width for focused content -->
</div>
```

### Stack (Vertical Rhythm)
```html
<div class="stack">
  <h2>Title</h2>
  <p>Paragraph 1</p>
  <p>Paragraph 2</p>
  <!-- Consistent vertical spacing -->
</div>

<div class="stack stack-sm">
  <!-- Tighter spacing -->
</div>
```

### Grid
```html
<!-- Auto-responsive grid -->
<div class="grid grid-auto">
  <div>Item 1</div>
  <div>Item 2</div>
  <div>Item 3</div>
</div>

<!-- Custom grid -->
<div class="grid" style="grid-template-columns: 1fr 2fr;">
  <aside>Sidebar</aside>
  <main>Content</main>
</div>
```

### Cluster (Horizontal Wrapping)
```html
<div class="cluster">
  <button>Action 1</button>
  <button>Action 2</button>
  <button>Action 3</button>
  <!-- Wraps naturally, maintains spacing -->
</div>
```

### Switcher (Conditional Layout)
```html
<div class="switcher">
  <div>Column 1</div>
  <div>Column 2</div>
  <!-- Stacks when narrow, side-by-side when wide -->
</div>
```

## ✨ Micro-Animations

### Utility Classes
```html
<!-- Fade in from below -->
<div class="animate-fade-in-up">...</div>

<!-- Bounce on appearance -->
<div class="animate-scale-bounce">...</div>

<!-- Continuous pulse glow -->
<div class="animate-pulse-glow">...</div>

<!-- Rotate (for loading spinners) -->
<div class="animate-rotate">⚙️</div>

<!-- Wiggle on interaction -->
<button class="animate-wiggle" onclick="this.classList.add('animate-wiggle')">
  Click me!
</button>
```

### Hover Effects
```html
<!-- Lift up on hover -->
<div class="hover-lift">...</div>

<!-- Scale on hover -->
<button class="hover-scale">...</button>

<!-- Glow on hover -->
<div class="hover-glow">...</div>
```

### Interactive Cards
```html
<div class="card card-interactive">
  <!-- Lifts, glows, and shows border on hover -->
  <h3>Interactive Card</h3>
  <p>Hover over me!</p>
</div>
```

## 🎯 Component Examples

### Project Card with Modern Features
```html
<div class="card card-interactive scroll-fade-in">
  <div class="stack stack-sm">
    <div class="cluster">
      <h3>Project Name</h3>
      <span class="badge badge-success">Active</span>
    </div>
    <p class="text-muted">Project description goes here...</p>
    <div class="cluster card-actions">
      <button class="btn btn-primary hover-scale">Open</button>
      <button class="btn btn-ghost hover-glow">Settings</button>
    </div>
  </div>
</div>
```

### Responsive Grid of Cards
```html
<div class="grid grid-auto">
  <div class="card scroll-fade-in">
    <h4>Card 1</h4>
  </div>
  <div class="card scroll-fade-in">
    <h4>Card 2</h4>
  </div>
  <div class="card scroll-fade-in">
    <h4>Card 3</h4>
  </div>
  <!-- Auto-responsive, smooth animations -->
</div>
```

### Form with Modern Spacing
```html
<form class="stack">
  <div class="stack stack-sm">
    <label for="name">Project Name</label>
    <input type="text" id="name" class="hover-glow">
  </div>

  <div class="stack stack-sm">
    <label for="desc">Description</label>
    <textarea id="desc" class="hover-glow"></textarea>
  </div>

  <div class="cluster">
    <button type="submit" class="btn btn-primary hover-scale">Create</button>
    <button type="button" class="btn btn-ghost">Cancel</button>
  </div>
</form>
```

### Dashboard Layout
```html
<div class="grid grid-auto-lg">
  <div class="card scroll-fade-in">
    <div class="stack">
      <h3>Projects</h3>
      <div class="stat-big">42</div>
      <p class="text-muted">Active projects</p>
    </div>
  </div>

  <div class="card scroll-fade-in">
    <div class="stack">
      <h3>Tasks</h3>
      <div class="stat-big">187</div>
      <p class="text-muted">Pending items</p>
    </div>
  </div>

  <div class="card scroll-fade-in">
    <div class="stack">
      <h3>Memory</h3>
      <div class="stat-big">1.2K</div>
      <p class="text-muted">Stored insights</p>
    </div>
  </div>
</div>
```

## 🎨 Design Tokens Reference

### Spacing Scale
```css
--space-3xs: 4-5px    /* Tiny gaps */
--space-2xs: 8-10px   /* Compact spacing */
--space-xs:  12-15px  /* Small spacing */
--space-sm:  16-20px  /* Base spacing */
--space-md:  24-30px  /* Medium spacing */
--space-lg:  32-40px  /* Large spacing */
--space-xl:  48-60px  /* Extra large */
--space-2xl: 64-80px  /* Section spacing */
--space-3xl: 96-120px /* Hero spacing */
```

### Typography Scale
```css
--text-xs:   12-14px  /* Captions, labels */
--text-sm:   14-16px  /* Secondary text */
--text-base: 16-18px  /* Body text */
--text-lg:   18-21px  /* Emphasized */
--text-xl:   20-25px  /* Subheadings */
--text-2xl:  24-32px  /* Headings */
--text-3xl:  30-42px  /* Large headings */
--text-4xl:  36-54px  /* Hero text */
```

### Shadows & Glows
```css
--shadow-xs through --shadow-2xl  /* Layered shadows */
--glow-sm, --glow-md, --glow-lg   /* Interactive glows */
```

### Animation Durations
```css
--duration-instant: 100ms   /* Instant feedback */
--duration-fast:    150ms   /* Quick transitions */
--duration-normal:  250ms   /* Standard */
--duration-slow:    350ms   /* Deliberate */
--duration-slower:  500ms   /* Emphasized */
--duration-glacial: 1000ms  /* Dramatic */
```

### Easing Functions
```css
--ease-in-out:  cubic-bezier(0.4, 0, 0.2, 1)      /* Smooth */
--ease-out:     cubic-bezier(0, 0, 0.2, 1)        /* Decelerate */
--ease-in:      cubic-bezier(0.4, 0, 1, 1)        /* Accelerate */
--ease-bounce:  cubic-bezier(0.68, -0.55, 0.265, 1.55)  /* Bounce */
--ease-elastic: cubic-bezier(0.68, -0.6, 0.32, 1.6)     /* Elastic */
```

## 🚀 Migration Guide

### Update Spacing
```html
<!-- Before -->
<div style="padding: 16px; margin-bottom: 24px;">

<!-- After -->
<div class="stack" style="padding: var(--space-md);">
```

### Update Grids
```html
<!-- Before -->
<div class="grid" style="grid-template-columns: repeat(3, 1fr);">

<!-- After -->
<div class="grid grid-auto">
  <!-- Automatically responsive! -->
```

### Add Animations
```html
<!-- Before -->
<div class="card">

<!-- After -->
<div class="card scroll-fade-in hover-lift">
  <!-- Smooth animations! -->
```

## 🎯 Best Practices

1. **Use Layout Primitives**: Prefer `.stack`, `.cluster`, `.grid-auto` over custom flex/grid
2. **Use Fluid Spacing**: Use CSS variables, not hardcoded pixels
3. **Progressive Enhancement**: Scroll animations degrade gracefully
4. **Semantic HTML**: Design system enhances, doesn't replace good structure
5. **Accessibility First**: All animations respect `prefers-reduced-motion`

## 🔍 Browser Support

- **CSS Layers**: All modern browsers (2022+)
- **oklch()**: Safari 15+, Chrome 111+, Firefox 113+
- **Container Queries**: Chrome 105+, Safari 16+, Firefox 110+
- **Scroll-driven Animations**: Chrome 115+, polyfill available
- **:has()**: Chrome 105+, Safari 15.4+, Firefox 121+

All features degrade gracefully in older browsers!

## 📚 Learn More

- **Fluid Typography**: [Modern CSS](https://moderncss.dev/generating-font-size-css-rules-and-creating-a-fluid-type-scale/)
- **oklch Colors**: [Evil Martians](https://evilmartians.com/chronicles/oklch-in-css-why-quit-rgb-hsl)
- **Container Queries**: [MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_container_queries)
- **Scroll Animations**: [Chrome Developers](https://developer.chrome.com/articles/scroll-driven-animations/)
- **:has() Selector**: [MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/:has)

---

**Status:** ✅ Complete and ready to use
**File:** `src/sunwell/interface/chirp/static/css/design-system.css`
**Integration:** Loaded in `pages/_layout.html`
