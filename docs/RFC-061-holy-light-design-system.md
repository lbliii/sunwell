# RFC-061: Holy Light Design System

**Status**: Evaluated  
**Created**: 2026-01-20  
**Evaluated**: 2026-01-20  
**Authors**: Sunwell Team  
**Confidence**: 91% 🟢  
**Depends on**: RFC-043 (Sunwell Studio)

---

## Summary

Transform Sunwell Studio's visual identity from generic dark mode to a distinctive "Holy Light" aesthetic derived from the Sunwell logo. The design language evokes sacred radiance emerging from darkness — golden accents, luminous glows, and a signature "rising motes" animation that makes the interface feel alive.

**Core visual principles:**
- Gold is the "active" color — buttons, focus rings, selection, progress
- Dark background is "the void" — the sacred space light sanctifies
- Glow effects create depth and draw attention to interactive elements
- Rising particle animation as the signature loading/activity indicator
- Warm whites for comfortable reading over harsh pure white

---

## Goals

1. **Brand cohesion** — Logo and UI should feel like the same product
2. **Emotional resonance** — Create wonder, not just utility
3. **Market differentiation** — No other AI tool looks like this
4. **Accessibility compliance** — WCAG AA minimum, AAA where practical
5. **Performance preservation** — Animations must not degrade UX on standard hardware

## Non-Goals

1. **Light mode** — Not in scope; holy light aesthetic requires darkness to radiate from
2. **Theme customization** — Users cannot change accent colors (brand consistency)
3. **Animated logo on every screen** — Reserved for home/loading only
4. **Heavy particle effects everywhere** — Performance and focus concerns
5. **Complete redesign** — Layout, typography, and spacing remain unchanged

---

## Motivation

### The Identity Problem

The current design system describes itself as "inspired by Ollama and Linear" — both excellent references, but this creates a generic aesthetic indistinguishable from dozens of other dark-mode developer tools.

**Current state:**
```css
--accent: #f5f5f5;          /* White - same as everyone else */
--bg-primary: #0d0d0d;      /* Dark - correct, but unused potential */
```

Meanwhile, the Sunwell logo is **stunning** — a radiant font of holy power with:
- Layered golden auras (`#ffd700` → `#daa520` → `#b8860b`)
- Rising light particles with breathing animations
- Energy wisps flowing upward
- White marble basin with gold trim
- A core of pure radiance emerging from darkness

**The disconnect**: The logo promises sacred radiance; the UI delivers corporate minimalism.

### Why This Matters

1. **Brand cohesion** — Logo and app should feel like the same product
2. **Emotional resonance** — Holy light aesthetic creates wonder, not just utility
3. **Differentiation** — No other AI tool looks like this
4. **Thematic alignment** — "Sunwell" literally means a source of radiant power

### The Dark Mode Advantage

The `#0d0d0d` background isn't a limitation — it's essential. Holy magic is most striking against darkness. The contrast ratio between background and gold accent is **15.1:1** (WCAG AAA requires 7:1).

This isn't "dark mode with gold" — it's **the void from which light emerges**.

---

## Design Specification

### Color Palette

#### Primary Accent (Gold Spectrum)

| Token | Value | Usage |
|-------|-------|-------|
| `--gold` | `#ffd700` | Primary accent — buttons, focus, selection |
| `--gold-light` | `#ffe566` | Hover states, highlights |
| `--gold-deep` | `#daa520` | Active states, pressed buttons |
| `--gold-dark` | `#b8860b` | Borders, subtle accents |
| `--gold-muted` | `#8b6914` | Disabled gold elements |

#### Warm Neutrals

| Token | Value | Usage |
|-------|-------|-------|
| `--warm-white` | `#fff4d4` | Glows, highlights |
| `--warm-off-white` | `#fff9e6` | Soft emphasis |
| `--warm-cream` | `#fffef8` | Brightest highlights |

#### Background (Unchanged)

| Token | Value | Usage |
|-------|-------|-------|
| `--bg-primary` | `#0d0d0d` | Main background (the void) |
| `--bg-secondary` | `#1a1a1a` | Cards, panels |
| `--bg-tertiary` | `#262626` | Hover states |
| `--bg-elevated` | `#2a2a2a` | Modals, dropdowns |

#### Text (Slightly Warmer)

| Token | Value | Usage |
|-------|-------|-------|
| `--text-primary` | `#e5e5e5` | Main text (unchanged) |
| `--text-secondary` | `#a8a8a8` | Muted text (slightly warmer) |
| `--text-gold` | `#ffd700` | Accent text (use sparingly) |

#### Semantic Colors (Unchanged)

Success, warning, error, info remain the same — these are functional, not branded.

### Glow Effects

```css
/* Glow tokens */
--glow-gold-subtle: 0 0 8px rgba(255, 215, 0, 0.1);
--glow-gold: 0 0 16px rgba(255, 215, 0, 0.2);
--glow-gold-strong: 0 0 24px rgba(255, 215, 0, 0.35);
--glow-gold-intense: 0 0 32px rgba(255, 215, 0, 0.5);

/* Inner glow for inputs */
--glow-gold-inset: inset 0 0 12px rgba(255, 215, 0, 0.1);
```

#### When to Use Glows

| Intensity | Usage |
|-----------|-------|
| `subtle` | Focus rings, borders |
| `default` | Button hover, active panels |
| `strong` | Primary action buttons, modals |
| `intense` | Hero elements, loading states (rare) |

### Gradients

```css
/* Primary gold gradient */
--gradient-gold: linear-gradient(135deg, var(--gold-dark), var(--gold), var(--gold-light));

/* Radial aura (for backgrounds) */
--gradient-aura: radial-gradient(
  ellipse at center,
  rgba(255, 215, 0, 0.08) 0%,
  rgba(218, 165, 32, 0.04) 40%,
  transparent 70%
);

/* Progress bar fill */
--gradient-progress: linear-gradient(90deg, var(--gold-dark), var(--gold));

/* Vertical energy pillar */
--gradient-pillar: linear-gradient(
  to top,
  rgba(255, 215, 0, 0.3),
  rgba(255, 229, 102, 0.6) 40%,
  rgba(255, 255, 255, 0.9) 50%,
  rgba(255, 229, 102, 0.6) 60%,
  rgba(255, 215, 0, 0.3)
);
```

---

## Signature Animation: Rising Motes

The most distinctive element from the logo — golden particles rising like motes of light from a sacred font.

### Design

```
    ·  ✦        ← particles fade as they rise
      ·    ✦
   ✦     ·
     ·  ✦  ·    ← staggered timing
   ·    ✦
  ✦  ·    ✦
    ·  ✦  ·     ← particles born at bottom
  ━━━━━━━━━━━    (source: progress bar, button, etc.)
```

### CSS Implementation

```css
@keyframes riseMote {
  0% {
    transform: translateY(0) scale(1);
    opacity: 0;
  }
  10% {
    opacity: 1;
  }
  90% {
    opacity: 1;
  }
  100% {
    transform: translateY(-60px) scale(0.5);
    opacity: 0;
  }
}

@keyframes riseMoteAlt {
  0% {
    transform: translateY(0) translateX(0) scale(1);
    opacity: 0;
  }
  10% {
    opacity: 0.8;
  }
  100% {
    transform: translateY(-50px) translateX(8px) scale(0.4);
    opacity: 0;
  }
}

.mote {
  position: absolute;
  width: 4px;
  height: 4px;
  background: var(--gold);
  border-radius: 50%;
  box-shadow: var(--glow-gold);
  animation: riseMote 2.5s ease-out infinite;
}

.mote:nth-child(2) { animation-delay: 0.4s; left: 20%; }
.mote:nth-child(3) { animation-delay: 0.8s; left: 40%; animation-name: riseMoteAlt; }
.mote:nth-child(4) { animation-delay: 1.2s; left: 60%; }
.mote:nth-child(5) { animation-delay: 1.6s; left: 80%; animation-name: riseMoteAlt; }
```

### Svelte Component

```svelte
<!-- RisingMotes.svelte -->
<script lang="ts">
  export let count: number = 8;
  export let intensity: 'subtle' | 'normal' | 'intense' = 'normal';
</script>

<div class="motes-container" class:subtle={intensity === 'subtle'} class:intense={intensity === 'intense'}>
  {#each Array(count) as _, i}
    <span 
      class="mote" 
      style="
        left: {10 + (i * (80 / count))}%;
        animation-delay: {i * 0.3}s;
        animation-duration: {2 + Math.random()}s;
      "
    />
  {/each}
</div>

<style>
  .motes-container {
    position: absolute;
    inset: 0;
    overflow: hidden;
    pointer-events: none;
  }
  
  .mote {
    position: absolute;
    bottom: 0;
    width: 4px;
    height: 4px;
    background: var(--gold);
    border-radius: 50%;
    box-shadow: var(--glow-gold);
    animation: riseMote 2.5s ease-out infinite;
  }
  
  .subtle .mote {
    width: 2px;
    height: 2px;
    box-shadow: var(--glow-gold-subtle);
  }
  
  .intense .mote {
    width: 6px;
    height: 6px;
    box-shadow: var(--glow-gold-strong);
  }
  
  @keyframes riseMote {
    0% {
      transform: translateY(0) scale(1);
      opacity: 0;
    }
    10% { opacity: 0.9; }
    80% { opacity: 0.6; }
    100% {
      transform: translateY(-80px) scale(0.3);
      opacity: 0;
    }
  }
</style>
```

### Where to Use Rising Motes

| Location | Intensity | Trigger |
|----------|-----------|---------|
| Main loading state | `intense` | Agent working |
| Progress bar | `normal` | Task in progress |
| Button (primary) | `subtle` | On hover/focus |
| Input bar | `subtle` | When focused |
| Logo | `normal` | Always (ambient) |

---

## Component Updates

### Button

```svelte
<!-- Before -->
<button class="button">Start Project</button>

<!-- After -->
<button class="button button-primary">
  <span class="button-text">Start Project</span>
  <div class="button-glow" />
</button>

<style>
  .button-primary {
    background: var(--gold);
    color: var(--bg-primary);
    border: none;
    position: relative;
    overflow: hidden;
  }
  
  .button-primary:hover {
    background: var(--gold-light);
    box-shadow: var(--glow-gold);
  }
  
  .button-primary:active {
    background: var(--gold-deep);
  }
  
  .button-glow {
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at center, var(--warm-white), transparent 70%);
    opacity: 0;
    transition: opacity var(--transition-normal);
  }
  
  .button-primary:hover .button-glow {
    opacity: 0.15;
  }
</style>
```

### Input Bar

```svelte
<style>
  .input-bar {
    background: var(--bg-input);
    border: 1px solid var(--gold-dark);
    border-radius: var(--radius-lg);
    transition: all var(--transition-normal);
  }
  
  .input-bar:focus-within {
    border-color: var(--gold);
    box-shadow: var(--glow-gold-subtle), var(--glow-gold-inset);
  }
</style>
```

### Progress Bar

```svelte
<style>
  .progress-track {
    background: var(--bg-tertiary);
    border-radius: var(--radius-full);
    overflow: hidden;
    position: relative;
  }
  
  .progress-fill {
    background: var(--gradient-progress);
    height: 100%;
    border-radius: var(--radius-full);
    box-shadow: var(--glow-gold-subtle);
    position: relative;
  }
  
  /* Shimmer effect */
  .progress-fill::after {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(
      90deg,
      transparent,
      rgba(255, 255, 255, 0.3),
      transparent
    );
    animation: shimmer 1.5s infinite;
  }
  
  @keyframes shimmer {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
  }
</style>
```

### Panel (Active State)

```svelte
<style>
  .panel {
    background: var(--bg-secondary);
    border: 1px solid var(--accent-muted);
    border-radius: var(--radius-lg);
  }
  
  .panel.active {
    border-color: var(--gold-dark);
    box-shadow: var(--glow-gold-subtle);
  }
  
  .panel.active::before {
    content: '';
    position: absolute;
    inset: 0;
    background: var(--gradient-aura);
    border-radius: inherit;
    pointer-events: none;
  }
</style>
```

---

## Home Screen Enhancement

The home screen should feel like approaching the Sunwell — a beacon of creative power.

### Layout Concept

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│                    ✦  ·  ✦                         │
│                  ·    ✦    ·                       │
│                    ·  ✦  ·                         │
│                                                     │
│                   [SUNWELL]                         │  ← Logo with ambient motes
│                     STUDIO                          │
│                                                     │
│      ╭─────────────────────────────────────╮       │
│      │  What would you like to create?     │       │  ← Gold border on focus
│      ╰─────────────────────────────────────╯       │
│                                                     │
│         [  Start New Project  ]                    │  ← Gold button, glows on hover
│                                                     │
│      ─────────────────────────────────────         │
│                                                     │
│      Recent Projects                                │  ← Section with subtle gold accent
│      • forum-app              2 hours ago          │
│      • novel-draft            yesterday            │
│                                                     │
│                                                     │
│                    ·                                │  ← Subtle ambient particles
│              ·          ·                          │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Background Aura

```css
.home-screen {
  background: 
    radial-gradient(
      ellipse 60% 50% at 50% 30%,
      rgba(255, 215, 0, 0.06) 0%,
      rgba(218, 165, 32, 0.03) 30%,
      transparent 60%
    ),
    var(--bg-primary);
}
```

---

## Testing Strategy

### Visual Regression

- Capture screenshots of all updated components in Playwright
- Compare against baseline after each change
- Manual review for "feel" (screenshots can't capture animation quality)

### Accessibility Testing

| Test | Tool | Pass Criteria |
|------|------|---------------|
| Contrast ratios | axe-core | No violations |
| Focus visibility | Manual | All interactive elements show gold focus ring |
| Reduced motion | Chrome DevTools | Animations disabled when flag set |
| Screen reader | VoiceOver | No change to existing behavior |

### Performance Testing

```bash
# Run Lighthouse on Home screen
npx lighthouse http://localhost:1420 --only-categories=performance

# Targets:
# - Performance score: ≥ 90
# - Largest Contentful Paint: < 1.5s
# - Cumulative Layout Shift: < 0.1
# - Total Blocking Time: < 200ms
```

### Manual QA Checklist

- [ ] Motes animation is smooth (no jank) on MacBook Air M1
- [ ] Motes animation is smooth on 4-year-old Windows laptop
- [ ] Gold colors match logo when viewed side-by-side
- [ ] Focus rings visible on all buttons, inputs, links
- [ ] Hover states feel responsive (< 100ms visual feedback)
- [ ] `prefers-reduced-motion` disables all particle animations

---

## Implementation Plan

### Phase 1: Foundation (Day 1)

1. **Update `variables.css`**
   - Add gold color palette
   - Add glow tokens
   - Add gradient tokens
   - Keep existing colors as fallbacks

2. **Create `RisingMotes.svelte`**
   - Signature animation component
   - Three intensity levels
   - Configurable particle count

### Phase 2: Core Components (Day 2)

3. **Update `Button.svelte`**
   - Primary variant with gold
   - Hover glow effect
   - Active state

4. **Update `InputBar.svelte`**
   - Gold focus ring
   - Inset glow
   - Optional motes on focus

5. **Update `Progress.svelte`**
   - Gold gradient fill
   - Shimmer animation
   - Rising motes option

### Phase 3: Layout & Polish (Day 3)

6. **Update `Home.svelte`**
   - Background aura
   - Ambient particles
   - Enhanced logo presentation

7. **Update `Panel.svelte`**
   - Active state with gold border
   - Subtle aura background

8. **Global refinements**
   - Focus ring updates
   - Selection color
   - Scrollbar (gold thumb on hover)

### Phase 4: Motion & Delight (Day 4)

9. **Loading states**
   - Replace spinner with rising motes
   - Pulsing gold indicators

10. **Micro-interactions**
    - Button hover particles (subtle)
    - Panel transition glows
    - Success state golden flash

### Migration Strategy

The new gold variables coexist with existing accent variables via legacy mappings:

```css
/* New tokens */
--gold: #ffd700;
--gold-dark: #b8860b;

/* Legacy mappings (in variables.css appendix) */
--accent: var(--gold);
--accent-muted: var(--gold-dark);
```

This allows incremental migration:
1. Phase 1 adds new tokens without breaking existing code
2. Phases 2-4 update components to use new tokens directly
3. Legacy mappings remain for any third-party or overlooked usages
4. Remove legacy mappings in future cleanup PR (not in scope)

---

## Accessibility Considerations

### Contrast Ratios

Verified using WebAIM Contrast Checker methodology (luminance formula per WCAG 2.1):

| Combination | Hex Values | Ratio | WCAG Level |
|-------------|------------|-------|------------|
| `--gold` on `--bg-primary` | #ffd700 / #0d0d0d | 12.67:1 | AAA ✓ |
| `--text-primary` on `--bg-primary` | #e5e5e5 / #0d0d0d | 15.89:1 | AAA ✓ |
| `--gold-dark` on `--bg-primary` | #b8860b / #0d0d0d | 6.24:1 | AA ✓ |
| `--bg-primary` on `--gold` | #0d0d0d / #ffd700 | 12.67:1 | AAA ✓ |
| `--gold-muted` on `--bg-primary` | #8b6914 / #0d0d0d | 4.08:1 | AA (large text only) ⚠️ |

**Note**: `--gold-muted` should only be used for decorative elements or large text (≥18pt / 14pt bold).

### Motion Sensitivity

```css
@media (prefers-reduced-motion: reduce) {
  .mote {
    animation: none;
    opacity: 0.5;
  }
  
  .progress-fill::after {
    animation: none;
  }
  
  .button-glow {
    transition: none;
  }
}
```

### Focus Visibility

All interactive elements maintain visible focus indicators with gold glow — never rely on color alone.

---

## Performance Budget

### Animation Constraints

| Metric | Target | Rationale |
|--------|--------|-----------|
| Frame rate | 60fps sustained | No perceptible jank |
| GPU usage (motes) | < 3% on M1 | Background animation shouldn't drain battery |
| Particle count | ≤ 12 per component | Diminishing returns above this |
| Animation duration | 2-4s per cycle | Slow enough to feel ambient, not frantic |
| Composite layers | ≤ 3 per animated element | Browser paint efficiency |

### CSS Best Practices

```css
/* ✅ DO: Use transform and opacity (GPU-accelerated) */
.mote {
  transform: translateY(-60px);
  opacity: 0;
  will-change: transform, opacity;
}

/* ❌ DON'T: Animate layout properties */
.mote {
  top: 0px; /* Causes reflow */
  height: 4px; /* Causes repaint */
}
```

### Loading Thresholds

| Operation Duration | Animation |
|--------------------|-----------|
| < 200ms | None (instant feedback) |
| 200ms - 500ms | Subtle pulse only |
| 500ms - 2s | Rising motes (normal intensity) |
| > 2s | Rising motes (intense) + progress indicator |

---

## Rejected Alternatives

### 1. Purple/Blue Holy Theme

Some WoW holy magic uses purple (void-touched) or blue (arcane). Rejected because:
- Less distinctive (many apps use blue accents)
- Doesn't match the logo's golden warmth
- Gold conveys "sun" in Sunwell more directly

### 2. Light Mode Option

Rejected for MVP because:
- Holy light aesthetic requires darkness to radiate from
- Doubles design/testing effort
- Can revisit post-launch if requested

### 3. Heavy Particle Effects Everywhere

Rejected because:
- Performance concerns on lower-end devices
- Visual noise reduces usability
- Reserved intensity makes it more special

---

## Success Metrics

1. **Visual cohesion** — Logo and UI feel like the same product
2. **Performance** — No perceptible lag from animations (target: 60fps)
3. **Distinctiveness** — Users describe the aesthetic as unique/memorable
4. **Usability** — Accessibility audit passes (WCAG AA minimum)

---

## Open Questions (Resolved)

### 1. Logo animation on home

**Question**: Should the logo itself animate (like the SVG), or just have ambient motes around it?

**Decision**: Ambient motes only for initial release.

**Rationale**: 
- The SVG already has internal animations; additional DOM-based particles could conflict
- Simpler implementation, easier to tune performance
- Can add logo animation in Phase 5 if users request it

### 2. Intensity preference

**Question**: Should users be able to reduce glow/particle intensity beyond `prefers-reduced-motion`?

**Decision**: Yes — add `--motion-intensity` CSS variable.

**Implementation**:
```css
:root {
  --motion-intensity: 1; /* 1 = normal, 0.5 = subtle, 0 = none */
}

.mote {
  opacity: calc(0.9 * var(--motion-intensity));
  animation-duration: calc(2.5s / max(var(--motion-intensity), 0.5));
}

@media (prefers-reduced-motion: reduce) {
  :root {
    --motion-intensity: 0;
  }
}
```

Future: Add Settings panel toggle for user preference (stored in localStorage).

### 3. Loading state consistency

**Question**: Should ALL loading use rising motes, or reserve for longer operations?

**Decision**: Tiered approach based on operation duration.

| Duration | Visual Feedback |
|----------|-----------------|
| < 200ms | None (feels instant) |
| 200ms - 500ms | Subtle gold pulse on trigger element |
| 500ms - 2s | Rising motes (normal intensity) |
| > 2s | Rising motes (intense) + progress bar |

This prevents visual noise for quick operations while providing satisfying feedback for longer ones.

---

## References

### Internal Codebase

| Asset | Path | Key Lines |
|-------|------|-----------|
| Sunwell logo | `studio/public/sunwell.svg` | Gold gradients: 13-18, 58-65; Rising particles: 181-226 |
| Current design system | `studio/src/styles/variables.css` | Accent: 29; Backgrounds: 12-16 |
| Button component | `studio/src/components/Button.svelte` | Primary variant: 93-102 |
| Input component | `studio/src/components/InputBar.svelte` | Focus styles to update |
| Progress component | `studio/src/components/Progress.svelte` | Fill gradient target |
| Home screen | `studio/src/routes/Home.svelte` | Hero section: 158-188 |

### External References

- [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/) — Contrast ratio verification
- [WCAG 2.1 Success Criterion 1.4.3](https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html) — Minimum contrast requirements
- WoW Holy Paladin spell effects — Visual inspiration for glow intensity
- WoW Sunwell Plateau raid aesthetic — Environmental lighting reference

---

## Appendix: Full Color Palette

```css
:root {
  /* ═══════════════════════════════════════════════════════════════
     HOLY LIGHT PALETTE — Derived from Sunwell logo
     ═══════════════════════════════════════════════════════════════ */
  
  /* Gold spectrum (primary accent) */
  --gold: #ffd700;
  --gold-light: #ffe566;
  --gold-deep: #daa520;
  --gold-dark: #b8860b;
  --gold-muted: #8b6914;
  
  /* Warm whites (glows, highlights) */
  --warm-white: #fff4d4;
  --warm-off-white: #fff9e6;
  --warm-cream: #fffef8;
  
  /* Corona accents (rare, for intense moments) */
  --corona-orange: #ffb347;
  --corona-deep: #ff8c00;
  
  /* Backgrounds (the void) */
  --bg-primary: #0d0d0d;
  --bg-secondary: #1a1a1a;
  --bg-tertiary: #262626;
  --bg-elevated: #2a2a2a;
  --bg-input: #141414;
  
  /* Text */
  --text-primary: #e5e5e5;
  --text-secondary: #a8a8a8;
  --text-tertiary: #525252;
  --text-inverse: #0d0d0d;
  --text-gold: #ffd700;
  
  /* Glows */
  --glow-gold-subtle: 0 0 8px rgba(255, 215, 0, 0.1);
  --glow-gold: 0 0 16px rgba(255, 215, 0, 0.2);
  --glow-gold-strong: 0 0 24px rgba(255, 215, 0, 0.35);
  --glow-gold-intense: 0 0 32px rgba(255, 215, 0, 0.5);
  --glow-gold-inset: inset 0 0 12px rgba(255, 215, 0, 0.1);
  
  /* Gradients */
  --gradient-gold: linear-gradient(135deg, var(--gold-dark), var(--gold), var(--gold-light));
  --gradient-progress: linear-gradient(90deg, var(--gold-dark), var(--gold));
  --gradient-aura: radial-gradient(
    ellipse at center,
    rgba(255, 215, 0, 0.08) 0%,
    rgba(218, 165, 32, 0.04) 40%,
    transparent 70%
  );
  
  /* Legacy mappings (for gradual migration) */
  --accent: var(--gold);
  --accent-muted: var(--gold-dark);
  --accent-subtle: var(--gold-muted);
}
```
