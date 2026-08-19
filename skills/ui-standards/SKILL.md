---
name: ui-standards
description: Stack-agnostic UI/UX rules — accessibility (contrast, focus, aria, alt text), touch target sizing, responsive breakpoints, typography, animation timing, light/dark mode contrast, icon and layout conventions, plus a pre-delivery checklist. Use when designing, building, reviewing or fixing any user interface, in React, Next.js, Flutter or plain HTML/Tailwind.
---

# UI/UX Standards

Stack-agnostic interface rules. They apply to React, Next.js, Flutter and plain HTML/Tailwind
alike, and are deliberately short enough to actually get checked.

---

## Priority Order

| # | Category | Impact |
|---|---|---|
| 1 | Accessibility | CRITICAL |
| 2 | Touch & interaction | CRITICAL |
| 3 | Performance | HIGH |
| 4 | Layout & responsive | HIGH |
| 5 | Typography & color | MEDIUM |
| 6 | Animation | MEDIUM |
| 7 | Style consistency | MEDIUM |

---

## 1. Accessibility (CRITICAL)

- Minimum **4.5:1** contrast ratio for normal text
- Visible focus rings on every interactive element
- `aria-label` on icon-only buttons
- Descriptive `alt` text on meaningful images; empty `alt=""` on decorative ones
- Tab order matches visual order
- Form inputs always have an associated label
- Colour is never the only indicator of state

## 2. Touch & Interaction (CRITICAL)

- Minimum **44×44px** touch targets
- `cursor-pointer` on every clickable element, cards included
- Disable buttons during async operations
- Error messages appear next to the field that caused them
- Primary interactions on click/tap — hover is an enhancement, never a requirement

## 3. Performance (HIGH)

- WebP images with `srcset` and lazy loading
- Respect `prefers-reduced-motion`
- Reserve space for async content — no layout jumping

## 4. Layout & Responsive (HIGH)

- `viewport-meta`: `width=device-width, initial-scale=1`
- Minimum **16px** body text on mobile
- No horizontal scroll at any viewport
- Test at **375px, 768px, 1024px, 1440px**
- Define a z-index scale (10, 20, 30, 50) — no ad-hoc `z-999`
- Floating navbars get `top-4 left-4 right-4`, not `top-0`
- Pad content for fixed navbar height — never let content hide behind it
- One consistent container width (`max-w-6xl` or `max-w-7xl`), not a mix

## 5. Typography & Color (MEDIUM)

- Line height **1.5–1.75** for body text
- Line length **65–75 characters**
- Heading and body fonts must match in personality

### Light/dark mode contrast

| Rule | Do | Don't |
|---|---|---|
| Glass cards, light mode | `bg-white/80` or higher | `bg-white/10` — invisible |
| Body text, light mode | `#0F172A` (slate-900) | `#94A3B8` (slate-400) |
| Muted text, light mode | `#475569` (slate-600) minimum | gray-400 or lighter |
| Borders | `border-gray-200` in light mode | `border-white/10` — invisible |

## 6. Animation (MEDIUM)

- **150–300ms** for micro-interactions; >500ms feels broken
- Animate `transform` / `opacity`, never `width` / `height`
- Skeleton screens or spinners for loading states
- Hover uses colour/opacity transitions — scale transforms that shift layout are out

## 7. Icons & Style (MEDIUM)

- **No emoji as icons** — use SVG sets (Heroicons, Lucide, Simple Icons)
- Consistent icon sizing: fixed 24×24 viewBox, rendered `w-6 h-6`
- Brand logos verified from Simple Icons, never guessed
- Same visual style across all pages
- Use theme colours directly (`bg-primary`), not `var()` wrappers

---

## Pre-Delivery Checklist

**Visual**
- [ ] No emojis used as icons
- [ ] Icons from one consistent set
- [ ] Hover states cause no layout shift

**Interaction**
- [ ] All clickable elements have `cursor-pointer`
- [ ] Hover states give clear visual feedback
- [ ] Transitions 150–300ms
- [ ] Focus states visible for keyboard navigation

**Light/Dark**
- [ ] Light mode text contrast ≥ 4.5:1
- [ ] Glass/transparent elements visible in light mode
- [ ] Borders visible in both modes
- [ ] Both modes tested

**Layout**
- [ ] Floating elements spaced from edges
- [ ] No content hidden behind fixed navbars
- [ ] Responsive at 375 / 768 / 1024 / 1440
- [ ] No horizontal scroll on mobile

**Accessibility**
- [ ] All images have alt text
- [ ] Form inputs have labels
- [ ] Colour is not the only indicator
- [ ] `prefers-reduced-motion` respected
