# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** DAE Noticias
**Generated:** 2026-10-09 18:57:19
**Category:** News/Media Platform
**Design Dials:** Variance 3/10 (Centered / Minimal) | Motion 2/10 (Subtle) | Density 4/10 (Standard)

---

## Global Rules

### Color Palette

| Role | Hex | CSS Variable |
|------|-----|--------------|
| Primary | `#51466F` | `--accent` |
| On Primary | `#FFFFFF` | `--on-accent` |
| Secondary | `#3E6254` | `--sage` |
| Accent/CTA | `#51466F` | `--accent` |
| Background | `#F4F2F6` | `--bg` |
| Foreground | `#292633` | `--text` |
| Card | `#FFFFFF` | `--surface` |
| Card Foreground | `#292633` | `--text` |
| Muted Surface | `#F0EDF4` | `--surface-inset` |
| Muted Foreground | `#514C5F` | `--muted` |
| Border | `#D9D4E1` | `--border` |
| Destructive | `#813D51` | `--rose` |
| On Destructive | `#FFFFFF` | `--rose-ink` |
| Ring | `#665391` | `--focus` |
| Success | `#3E6254` | `--sage` |
| Warning | `#74501E` | `--amber` |
| Information | `#395B75` | `--info` |

**Color Notes:** Muted lavender and sage accents sit on warm grey surfaces. Rose and amber are reserved for status feedback.

### Dark Theme Tokens

| Role | Hex |
|------|-----|
| Background | `#17171E` |
| Surface | `#20202A` |
| Raised Surface | `#282832` |
| Border | `#41404D` |
| Main Text | `#F1EEF5` |
| Secondary Text | `#CBC6D4` |
| Lavender Accent | `#CDBFE8` |
| Sage Accent | `#B8D5C7` |
| Rose Status | `#EFB9C7` |
| Amber Status | `#E8C992` |

### Typography

- **Heading Font:** Georgia / system serif
- **Body Font:** Inter / system sans-serif
- **Mood:** news, editorial, journalism, trustworthy, readable, informative
- **Loading:** Local system font stacks keep reading legible without external font requests or layout shifts.

### Spacing Variables

*Density: 4/10 — Standard*

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `4px` / `0.25rem` | Tight gaps |
| `--space-sm` | `8px` / `0.5rem` | Icon gaps, inline spacing |
| `--space-md` | `16px` / `1rem` | Standard padding |
| `--space-lg` | `24px` / `1.5rem` | Section padding |
| `--space-xl` | `32px` / `2rem` | Large gaps |
| `--space-2xl` | `48px` / `3rem` | Section margins |
| `--space-3xl` | `64px` / `4rem` | Hero padding |

### Shadow Depths

| Level | Value | Usage |
|-------|-------|-------|
| `--shadow-card` | `0 8px 28px rgb(40 31 56 / 6%)` | Light-mode cards |
| `--shadow-float` | `0 14px 38px rgb(40 31 56 / 12%)` | Raised or hovered surfaces |
| Dark card | `0 10px 30px rgb(0 0 0 / 17%)` | Dark-mode cards |

---

## Component Specs

### Buttons

```css
/* Primary Button */
.button {
  background: var(--accent);
  color: var(--on-accent);
  padding: 10px 18px;
  border-radius: 10px;
  font-weight: 700;
  transition: color 180ms ease, background-color 180ms ease, border-color 180ms ease;
  cursor: pointer;
}

.button:hover {
  background: var(--accent-hover);
}

/* Secondary Button */
.button-secondary {
  background: transparent;
  color: var(--text);
  border: 1px solid var(--border-strong);
  padding: 10px 18px;
  border-radius: 10px;
  font-weight: 600;
  transition: color 180ms ease, background-color 180ms ease, border-color 180ms ease;
  cursor: pointer;
}
```

### Cards

```css
.article-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 15px;
  box-shadow: var(--shadow-card);
  transition: background-color 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
}

.article-card:hover {
  box-shadow: var(--shadow-float);
}
```

### Inputs

```css
.form-control {
  min-height: 46px;
  padding: 10px 12px;
  border: 1px solid var(--border-strong);
  border-radius: 9px;
  font-size: 16px;
  background: var(--surface-inset);
  color: var(--text);
  transition: border-color 200ms ease;
}

.form-control:focus-visible {
  border-color: var(--focus);
  outline: 3px solid var(--focus);
  outline-offset: 2px;
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--focus) 22%, transparent);
}
```

### Modals

The portal has no custom modal component. Destructive actions use a confirmation page; Django Admin retains its native controls.

---

## Style Guidelines

**Style:** Minimalism & Swiss Style

**Keywords:** Clean, simple, spacious, functional, white space, high contrast, geometric, sans-serif, grid-based, essential

**Best For:** Enterprise apps, dashboards, documentation sites, SaaS platforms, professional tools

**Key Effects:** Subtle hover (200-250ms), smooth transitions, sharp shadows if any, clear type hierarchy, fast loading

### Page Pattern

**Pattern Name:** Editorial News Front Page

- **Conversion Strategy:** Lead with a clear editorial headline and the most recent featured story, then expose the rest of the publication without promotional clutter.
- **CTA Placement:** Featured story title and a text-forward reading link.
- **Section Order:** Editorial heading > Featured story > Recent story grid > Topic navigation.

---

## Motion

Use subtle color and border transitions on controls only. Avoid scroll-triggered reveals so all news content stays immediately available to readers and crawlers.

---

## Anti-Patterns (Do NOT Use)

- ❌ Cluttered layout
- ❌ Slow loading

### Additional Forbidden Patterns

- ❌ **Emojis as icons** — Use SVG icons (Heroicons, Lucide, Simple Icons)
- ❌ **Missing cursor:pointer** — All clickable elements must have cursor:pointer
- ❌ **Layout-shifting hovers** — Avoid scale transforms that shift layout
- ❌ **Low contrast text** — Maintain 4.5:1 minimum contrast ratio
- ❌ **Instant state changes** — Always use transitions (150-300ms)
- ❌ **Invisible focus states** — Focus states must be visible for a11y

---

## Pre-Delivery Checklist

Before delivering any UI code, verify:

- [ ] No emojis used as icons (use SVG instead)
- [ ] All icons from consistent icon set (Heroicons/Lucide)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with smooth transitions (150-300ms)
- [ ] Light mode: text contrast 4.5:1 minimum
- [ ] Focus states visible for keyboard navigation
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] No content hidden behind fixed navbars
- [ ] No horizontal scroll on mobile
