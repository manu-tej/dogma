# Dogma Design System — Canonical Reference

> **This is the single source of truth for the visual language of the `frontend/` app.**
> Surface/page-redesign agents treat this file as **read-only law**. Do not restyle by
> introducing new colors, fonts, radii, or shadows — compose the tokens and primitives
> below. If something you need is genuinely missing, flag it; do not hardcode around it.
>
> **Canonical file:** `frontend/src/guidelines/DESIGN-SYSTEM.md` (this file).
> The sibling `frontend/src/guidelines/Guidelines.md` is an empty Figma-Make template
> stub (all content commented out) — it is **not** authoritative; ignore it.
>
> **Token source of truth:** `frontend/src/index.css` (Tailwind v4, CSS-first — there is
> **no** `tailwind.config.js`). All tokens are CSS custom properties exposed to Tailwind
> via the `@theme inline { … }` block. Do not add a Tailwind config file.

---

## 0. Aesthetic in one line

**"Northern Blot": graphite instrument surfaces with a single surgical phosphor-green
signal accent.** Dark-first. Depth comes from a 3-step surface ladder + a lit-bevel
shadow. The accent **emits light** (a glow) rather than filling large areas — green is a
scalpel, not a paint bucket.

---

## 1. Color tokens

Colors are defined as CSS variables in `:root, .dark` and re-exported as Tailwind color
utilities through `--color-*` in `@theme inline`. **Reference every color by its Tailwind
utility** (`bg-*`, `text-*`, `border-*`, `ring-*`, `fill-*`, `stroke-*`) — or, inside raw
CSS / inline `style`, by the raw `var(--token)`. Never write a hex, `rgb()`, or a stock
Tailwind palette color (`slate-*`, `blue-*`, `emerald-*`, …).

### Surfaces & foreground (the "surface ladder")
Depth is expressed by stepping **up** the ladder, not by shadows alone.

| Token (CSS var) | Tailwind utility | Value (oklch) | Use for |
|---|---|---|---|
| `--background` | `bg-background` | `0.155 0.006 264` | app canvas / page base (darkest) |
| `--surface-1` | `bg-surface-1` | `0.205 0.007 264` | cards, inputs, first raised layer (= `--card`) |
| `--surface-2` | `bg-surface-2` | `0.255 0.008 264` | popovers, hover fills, raised-on-raised (= `--popover`) |
| `--foreground` | `text-foreground` | `0.97 0.004 264` | primary text/icons |
| `--card` / `--card-foreground` | `bg-card` / `text-card-foreground` | `= surface-1` / `= foreground` | card body + its text |
| `--popover` / `--popover-foreground` | `bg-popover` / `text-popover-foreground` | `= surface-2` / `= foreground` | floating surfaces (dialog, dropdown, tooltip) |

### The signal (brand accent — use sparingly)
| Token | Tailwind utility | Value | Use for |
|---|---|---|---|
| `--signal` | `bg-signal` / `text-signal` | `0.82 0.19 150` (phosphor green) | the ONE active/brand emphasis; primary buttons; active tab text; links |
| `--signal-2` | `bg-signal-2` / `text-signal-2` | `0.88 0.13 175` (teal-green) | secondary accent / gradients only |
| `--signal-foreground` | `text-signal-foreground` | `0.18 0.04 150` | text/icon **on** a filled signal surface |

### Action & neutral roles
| Token | Tailwind utility | Use for |
|---|---|---|
| `--primary` / `--primary-foreground` | `bg-primary` / `text-primary-foreground` | primary action (aliases the signal; carries `.glow-signal`) |
| `--secondary` / `--secondary-foreground` | `bg-secondary` / `text-secondary-foreground` | secondary buttons (= `surface-2`) |
| `--muted` / `--muted-foreground` | `bg-muted` / `text-muted-foreground` | muted fills; **`text-muted-foreground` = all secondary/caption text** |
| `--accent` / `--accent-foreground` | `bg-accent` / `text-accent-foreground` | subtle **hover** surface (shadcn "accent" — NOT the brand; = `surface-2`) |

### Status
| Token | Tailwind utility | Use for |
|---|---|---|
| `--destructive` / `--destructive-foreground` | `bg-destructive` / `text-destructive` | errors, destructive actions (red) |
| `--positive` | `bg-positive` / `text-positive` | success / "up" state (green). ⚠️ no `-foreground` defined |
| — | — | ⚠️ **no warning/amber token exists** — see §7 gap |

### Lines & controls
| Token | Tailwind utility | Use for |
|---|---|---|
| `--border` | `border-border` | default hairline border (applied globally to `*` in base layer) |
| `--border-strong` | `border-border-strong` | emphasized / hover border |
| `--input` | `border-input` | input border |
| `--input-background` | `bg-input-background` | input fill |
| `--switch-background` | `bg-switch-background` | switch track |
| `--ring` | `ring-ring` / `outline-ring` | focus ring (= signal) |

### Data-viz (charts)
`--chart-1 … --chart-5` → `bg-chart-1`/`text-chart-1`/`fill-chart-1`/`stroke-chart-1` …
Sequential phosphor→teal→blue magnitude ramp (`chart-1..3`) plus reserved up/down-
regulation hues (`chart-4` amber, `chart-5` red). Always color series through these, never
raw hex. Recharts is wired via the `components/ui/chart.tsx` `ChartContainer`/`ChartConfig`.

### Sidebar / nav rail (own sub-scale)
`--sidebar`, `--sidebar-foreground`, `--sidebar-primary(-foreground)`,
`--sidebar-accent(-foreground)`, `--sidebar-border`, `--sidebar-ring`
→ `bg-sidebar`, `text-sidebar-foreground`, `bg-sidebar-primary`, `bg-sidebar-accent`,
`border-sidebar-border`, …. The nav rail sits **inset/darker** than the page
(`--sidebar` = `0.145` < `--background` = `0.155`). Use these for nav chrome only.

### Light vs dark
See §5. Today **`:root` and `.dark` hold identical values → there is only one (dark)
palette.** Still, always go through tokens: when a real light palette lands, token-based
UI recolors for free.

---

## 2. Typography

**Family** (self-hosted Geist variable fonts, imported in `index.css`):
| Token | Tailwind utility | Stack |
|---|---|---|
| `--font-sans` | `font-sans` (default on `body`) | `"Geist Variable", ui-sans-serif, system-ui, …` |
| `--font-display` | `font-display` | same Geist family — used on `h1`/`h2` with tighter tracking |
| `--font-mono` | `font-mono` | `"Geist Mono Variable", ui-monospace, …` — **use for IDs, gene/protein symbols, params, code, numeric/tabular data** (base layer turns on `tnum`+`ss01`) |

**Root size:** `--font-size: 15px` set on `html`. ⚠️ Consequence: **all `rem`-based Tailwind
utilities (`text-*`, `p-*`, `gap-*`, `rounded-*`) compute against 15px, not 16px.** So
`text-base` = 1rem = **15px**, `p-4` = 1rem = **15px**.

**Weights:** `--font-weight-normal: 400`, `--font-weight-medium: 500`,
`--font-weight-semibold: 600`. Use `font-normal` / `font-medium` / `font-semibold`. **Do
not use `font-bold`/700+** — the ceiling is semibold.

**Scale** = Tailwind v4 default `--text-*` (rem), rendered at the 15px root:
| Utility | rem | ≈ px @15 root | Typical use |
|---|---|---|---|
| `text-xs` | 0.75 | 11.25 | badges, micro-labels, timestamps |
| `text-sm` | 0.875 | 13.1 | body-secondary, buttons, labels, inputs (`md:text-sm`) |
| `text-base` | 1.0 | 15 | default body / paragraphs |
| `text-lg` | 1.125 | 16.9 | `h3`, dialog titles |
| `text-xl` | 1.25 | 18.75 | `h2` |
| `text-2xl` | 1.5 | 22.5 | `h1` / page titles |

**How to apply:** bare `h1–h4`, `p`, `label`, `button`, `input` get sensible defaults from
the base layer **only when no `text-*` class is present** (see the `@layer base` block).
In practice, **set typography explicitly with `text-*` + `font-*` classes** on your
elements (that is the de-facto pattern across pages). Reserve `font-display` +
`tracking-tight`/`-0.02em` for large headings.

---

## 3. Spacing, radius, border, elevation, motion

### Spacing
Tailwind default 4-step scale (`--spacing` = 0.25rem). Stick to the scale (`gap-2`,
`p-4`, `px-6`, `space-y-8`). De-facto rhythm: **cards pad `p-6`, page scroll regions pad
`p-6`, compact rows `p-3`, control gaps `gap-2`.** Don't invent arbitrary padding
(`p-[7px]`).

### Radius
`--radius: 0.7rem`. Exposed as:
| Utility | Formula | Use |
|---|---|---|
| `rounded-sm` | `radius − 4px` | inner chips, tiny controls |
| `rounded-md` | `radius − 2px` | badges, menu items, small buttons |
| `rounded-lg` | `radius` | **default**: buttons, inputs, most controls |
| `rounded-xl` | `radius + 4px` | cards, dialogs, tab lists (large surfaces) |
Use `rounded-full` only for avatars/dots/pills.

### Border
Every element gets `border-border` by default (base layer `* { @apply border-border … }`).
Escalate to `border-border-strong` on hover/emphasis. **Borders are how surfaces separate —
prefer a border + a ladder step over a heavy shadow.**

### Elevation (utilities in `@layer utilities`, not raw `shadow-*`)
| Utility | What it is | Use |
|---|---|---|
| `.elev` | close definition shadow + soft ambient (`--shadow-lg`) + lit top bevel (`--bevel`) | **cards, dialogs, popovers, any raised panel** |
| `.elev-sm` | `--shadow-sm` + bevel | small raised chips/controls |
| `.glow-signal` | signal-colored ring + glow (`--glow-signal`) | the ONE emphasized/active/brand element (primary button already has it) |
Raw shadow tokens `--shadow-sm/md/lg` and `--bevel` exist but prefer the `.elev*` utilities.

### Signature motion & effect utilities
| Utility | Effect |
|---|---|
| `.trace-band` | glowing 2px signal bar on the left edge — marks the **single active** row/item |
| `.signal-sweep` | luminous band migrating L→R (`dogma-sweep`) — loading/active |
| `.shimmer` | skeleton shimmer (`dogma-shimmer`) — used by `<Skeleton>` |
| `.stagger` | entrance-stagger helper; pair with `tw-animate-css` `animate-in` |

### Motion tokens
One clock for the whole app:
`--duration-fast: 120ms`, `--duration-base: 200ms`, `--duration-slow: 320ms`;
`--ease-out-quart` (exposed as `ease-out-quart`), `--ease-spring` (`ease-spring`).
Entrances use `tw-animate-css` (`animate-in fade-in slide-in-from-bottom-2`,
`zoom-in-95`, …). Interactive feedback: buttons `active:scale-[0.98]`, cards
`hover:-translate-y-0.5`. **Global rule:** `prefers-reduced-motion` is respected in the
base layer — never fight it. (Note: primitives currently hardcode `duration-150 ease-out`
rather than the duration tokens — when in doubt, match `duration-150 ease-out` for control
micro-interactions; see §7.)

---

## 4. Primitive components — reuse these, do NOT hand-roll

All primitives live in **`frontend/src/components/ui/*`**, are shadcn-style (Radix +
`class-variance-authority`), already token-styled, and expose a `data-slot` + `className`
override. **Rule: if a primitive exists for what you're building, use it. Never recreate
its markup with raw `<div>` + Tailwind** (e.g. do not rebuild a card out of
`bg-card border border-border elev rounded-xl` — import `<Card>`). Compose via the
`cn()` helper (`components/ui/utils.ts`) and the `className` prop; extend with variants,
don't fork.

> Import note: these files use pinned specifiers like `@radix-ui/react-slot@1.1.2` /
> `lucide-react@0.487.0` (Figma-Make export style, resolved by the Vite build). Keep that
> convention when editing a primitive; **app code imports icons as plain `lucide-react`.**

**Actions & inputs**
- `button` — `Button` + `buttonVariants`. Variants: `default` (signal + glow),
  `destructive`, `outline`, `secondary`, `ghost`, `link`. Sizes: `default`, `sm`, `lg`,
  `icon`. **All buttons go through this.**
- `input`, `textarea`, `label`, `checkbox`, `radio-group`, `switch`, `slider`,
  `input-otp`, `select`, `form` (react-hook-form), `toggle`, `toggle-group`, `calendar`.
- `badge` — `default` (signal tint), `secondary`, `destructive`, `outline`. Status pills.

**Surfaces & layout**
- `card` — `Card`/`CardHeader`/`CardTitle`/`CardDescription`/`CardAction`/`CardContent`/
  `CardFooter`. The default raised container (`bg-card`, `.elev`, `rounded-xl`, hover-lift).
- `separator`, `aspect-ratio`, `scroll-area`, `resizable`, `skeleton` (uses `.shimmer`),
  `accordion`, `collapsible`, `table`, `tabs` (active tab → `bg-card text-signal`).

**Overlays & menus**
- `dialog`, `alert-dialog`, `sheet` (side drawer — used for mobile nav), `drawer` (vaul),
  `popover`, `hover-card`, `tooltip`, `dropdown-menu`, `context-menu`, `menubar`,
  `navigation-menu`, `command` (cmdk — powers the ⌘K palette).

**Feedback & data-viz**
- `alert` (`default` / `destructive`), `progress`, `sonner` (toasts — `<Toaster>` mounted
  in `main.tsx`; call via `sonner`'s `toast()`), `chart` (Recharts wrapper — use
  `ChartContainer` + `ChartConfig`, colors from `--chart-*`).

**Nav & misc**
- `sidebar` (full sidebar framework), `breadcrumb`, `pagination`, `carousel`, `avatar`,
  `use-mobile` (hook), `utils` (`cn`).

**Shared app-level (non-`ui/`) components to reuse, not re-implement:**
`components/LoadingSpinner.tsx` (loading states — used in `AppShell` Suspense fallback),
and the app shell in `src/app/*` (`AppShell`, `NavRail`, `TopBar`, `Brand`, `Breadcrumbs`,
`CommandPalette`, `ThemeToggle`). Pages render inside `AppShell`'s `<Outlet/>` — don't
re-create nav/top-bar chrome.

**De-facto page shell pattern** (match it):
```tsx
// full-height column with a header band + scrolling body
<div className="flex h-full flex-col">
  <header className="… border-b border-border …">…</header>
  <div className="min-h-0 flex-1 overflow-y-auto p-6">…</div>
</div>
// centered reading width for content pages:
<div className="h-full overflow-y-auto">
  <div className="mx-auto max-w-5xl px-6 py-12">…</div>
</div>
```

---

## 5. Theming — the exact mechanism

- **Provider:** `next-themes` `<ThemeProvider attribute="class" defaultTheme="dark"
  enableSystem>` in `src/main.tsx`. It toggles the **`.dark` class on `<html>`**.
- **Variant hook:** `index.css` declares `@custom-variant dark (&:is(.dark *))`, so
  Tailwind `dark:` utilities key off that class.
- **Toggle UI:** `src/app/ThemeToggle.tsx` (`useTheme`) and `SettingsPage.tsx`
  (dark / light / system).
- **⚠️ Current reality — dark only:** `index.css` defines `:root, .dark { … }` with **one
  shared set of values**. There is **no separate light (`:root`-only or `.light`) block**,
  so selecting "light"/"system" renders the *same dark tokens*. A real light palette is a
  deferred slice.

**The token law (non-negotiable):**
1. **All color MUST go through a token** — a Tailwind semantic utility (`bg-card`,
   `text-muted-foreground`, `text-signal`, `border-border`, `text-positive`, …) or a raw
   `var(--token)` in CSS/inline style.
2. **No raw hex, `rgb()`/`hsl()` literals, or stock Tailwind palette colors**
   (`slate-*`, `gray-*`, `zinc-*`, `blue-*`, `emerald-*`, `amber-*`, `red-*`, …) in app code.
3. **No arbitrary color values** (`bg-[#0a0a0a]`, `text-[#8f8]`).
4. When a genuinely new color/state is needed, **add a token** to `index.css` (both a
   future light block and the dark block) and map it in `@theme inline` — don't inline it.
5. Building strictly on tokens is also what makes the future light theme "just work."

---

## 6. Do / Don't

**Do**
- Compose the surface ladder (`background` → `surface-1`/`card` → `surface-2`/`popover`)
  for depth; separate with `border-border`, lift with `.elev`.
- Reserve `signal`/`primary`/`.glow-signal`/`.trace-band` for the **single** most important
  or active element per view. Green is an accent, not a background.
- Reuse `components/ui/*` primitives and the `AppShell` chrome; extend via `className`+`cn()`.
- Use `text-muted-foreground` for all secondary text; `font-mono` for IDs/symbols/numbers.
- Keep radii on-scale (`rounded-lg` default, `rounded-xl` for cards/dialogs).
- Respect the motion clock (`duration-fast/base/slow`, `ease-out-quart`) and reduced-motion.

**Don't**
- Don't use stock palette colors or hex (see §5). Route status through
  `positive` / `destructive` (and the warning token once it exists), never raw
  `emerald-*`/`red-*`/`amber-*`.
- Don't flood large areas with `signal`/green, or stack multiple glows.
- Don't hand-roll a Card/Button/Badge/Dialog out of raw divs — import the primitive.
- Don't use `font-bold` (700+) or arbitrary font sizes (`text-[13px]`) — use the scale.
- Don't add a `tailwind.config.js` or hardcode shadows — use `.elev*` and `@theme inline`.

---

## 7. Known inconsistencies & gaps — normalize toward the tokens

Surface-redesign agents should **migrate toward tokens**, not copy these:

1. **Raw palette colors bypassing tokens (biggest issue).** ~110 stock-palette utilities
   exist in app code. Most are in **dead/unrouted files** — `components/LandingPage.tsx`
   (71, `bg-slate-950`/`bg-blue-600`/`text-slate-400`, the old Figma-Make landing, not
   imported anywhere) and `examples/GeoSearchExample.tsx` (22, also unimported). **Live
   offender:** `components/hypothesis/EvaluationWorkflowPanel.tsx` (14 — `emerald`/`amber`/
   `red` for done/needs-you/failed states), plus a few in `NodePanel`, `HistorySidebar`,
   `EvidenceLedger`. → Recolor status via `positive`/`destructive`/(new `warning`); delete
   or rewrite the dead landing/example files rather than mimicking them.

2. **Hand-rolled surfaces instead of primitives.** e.g. `pages/DatasetsPage.tsx` rebuilds
   the Card look inline (`elev … rounded-lg border border-border bg-card p-3 …
   hover:-translate-y-0.5 hover:border-border-strong`) instead of `<Card>`. → Replace with
   the primitive so future Card changes propagate.

3. **Missing/half tokens.**
   - **No warning/amber semantic token** despite status UIs needing "needs-attention"
     (they reach for raw `amber-*`). → add `--warning` (+ `-foreground`).
   - **`--positive` has no `-foreground`** (unlike destructive) → text-on-positive is
     undefined; add it.
   - **Light palette not implemented** — the theme toggle is effectively a no-op. Build on
     tokens so it lands cleanly later.
   - **Motion tokens under-used** — primitives hardcode `duration-150 ease-out` instead of
     `--duration-*`/`--ease-out-quart`. New work should prefer the tokens (or at least
     match `duration-150 ease-out` consistently).
   - **Arbitrary font sizes** — ~32 `text-[NNpx]` usages bypass the type scale. → snap to
     `text-xs … text-2xl`.
