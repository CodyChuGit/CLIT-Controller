# AgentFlow Studio — Design Language

The reference surface is the **Explorer tab**: rigid, rectangular, edge-to-edge panels divided by
hairline borders. It reads like a serious IDE (VS Code / Zed), not a marketing site. Every new
surface should look like it belongs next to the Explorer.

## Philosophy

- **Panels, not floating cards.** Structure comes from 1px borders and background shifts, never
  from drop shadows or big rounded corners. If a container needs `shadow-lg`, redesign it.
- **Dense and quiet.** Small type, tight spacing, lots of information per pixel — but only
  information the user acts on. Detail lives behind expanders, drawers, and hovers.
- **Mono for machine names.** Provider ids, paths, branches, model names, task ids, commands:
  always `font-mono`. Prose stays in the sans stack.
- **Color is a signal, not decoration.** Neutral surfaces; color only for status, diffs, focus,
  and the single blue accent.

## Tokens

### Radius (rigid scale)
| Use | Class |
|---|---|
| Panels, sections, cards | `rounded-lg` (8px) — never larger |
| Buttons, inputs, selects | `rounded-md` (6px) |
| Chips, tiny controls | `rounded` (4px) or `rounded-md` |
| File-type icon badges | `rounded-[3px]` |
| Status dots, health dots, count pills | `rounded-full` (dots/pills only) |

`rounded-xl`/`rounded-2xl` are banned. The softness budget is spent on `rounded-full` dots.

### Color
- Canvas: `bg-surface` (light `#f5f5f7`) / `dark:bg-neutral-950`
- Panel: `bg-white dark:bg-neutral-900`; sunken areas (gutters, tab strip, mono blocks):
  `bg-neutral-50 dark:bg-neutral-950`
- Border: `border-neutral-200 dark:border-neutral-800` — one hairline everywhere
- Accent: `accent` (#2563eb) — selection, primary buttons, active indicators, focus rings
- Status: emerald = ok/added · amber = warn/modified/conserve · rose = error/deleted/red ·
  blue = running/info · violet = artifacts & production-code chips · neutral = idle/unknown
- Never convey state by color alone — pair with a label or letter (badges include text).

### Typography
| Role | Classes |
|---|---|
| Page title (sparingly) | `text-xl font-semibold` |
| Section header | `text-[11px] font-semibold uppercase tracking-wide text-neutral-500` |
| Body / rows | `text-xs` or `text-[13px]` |
| Meta / hints | `text-[10px]`–`text-[11px] text-neutral-400/500` |
| Machine text | `font-mono`, sizes as above |
| Numbers in data rows | add `tabular-nums` |

### Spacing
4px rhythm. Rows `py-0.5`–`py-1.5`, panel padding `p-2.5`–`p-4`, section gaps `space-y-4`.
Edge-to-edge layouts (Explorer, Tasks console) own their scroll areas; centered content uses
`max-w-4xl`.

## Layout primitives

- **App shell:** activity bar (48px icon rail, left) · main content · chat dock (resizable, right) ·
  status bar (24px, bottom — quiet neutral strip; offline state signals in rose text, never a
  colored banner). Panels are solid surfaces separated by hairline borders; centered pages
  use `max-w-5xl p-6`.
- **Panel section** (Explorer sidebar pattern): collapsible header row — chevron + uppercase
  micro-label + optional mono badge + right-aligned icon actions — then content, then
  `border-b`. No outer margin; sections stack flush.
- **Output/terminal panel:** bottom-docked, `border-t`, collapsible, 32px header.
- **Editor:** tab strip (`h-8`, sunken `bg-surface`, active tab = panel bg + accent top-line
  overlay, FileTypeIcon badges) — the one tab-strip pattern shared with the chat dock;
  breadcrumb row, sticky line-number gutter on sunken bg.

## Composition primitives (frontend/src/components/ui.tsx)

Every page and panel composes these — do not hand-roll their patterns:

- **PageShell** — scrollable canvas, centered `max-w-5xl p-6` column, `h1` + right-aligned
  actions row. All centered pages use it (Tasks keeps its custom sticky header).
- **Card** — bordered panel; a string `title` renders the canonical header strip
  (`.section-title` left, actions right, `px-3 py-1.5 border-b`); `pad` adds the p-4 body.
- **EmptyState** — muted icon + one `text-xs` line, optional extra content below.
- **`.section-title`** — the only section-heading style (11px semibold uppercase neutral-500).
- **`.select`** — compact native select that sits flush with `.btn` rows.

## Components

- **Buttons:** `.btn-primary` (accent) / `.btn-secondary` (bordered) / `.btn-danger`; add `.btn-xs`
  for compact row actions. One primary action per view.
- **Icon buttons:** use `.icon-btn` (hover square, focus ring), always with `title` + `aria-label`.
- **Segmented control** (mutually exclusive modes): bordered `rounded-md` strip of `text-xs`
  segments, selected = `bg-blue-50 text-blue-700`; hints go in `title` tooltips, not body text.
- **Status badge:** dot + lowercase label pill (`StatusBadge`). Health = three-dot
  traffic light (`UsageHealthBadge`).
- **Chips:** `.chip` for provider/meta; artifact chips are bordered minis (`text-[10px]
  font-mono`), emerald + ✓ once real, violet for special targets (production code, git diff).
- **File rows** (tree + source control): `FileTypeIcon` badge · filename (`text-xs`) · dimmed
  dir path · right-aligned color-coded status letter (M amber, A/U emerald, D rose, R blue).
  Hover reveals row actions; whole row is the click target.
- **File-type icons:** 14px `rounded-[3px]` letter badges per extension (TS blue, JS yellow,
  PY sky, MD sky, JSON amber, HTML orange, CSS indigo, SH neutral…); generic outline file icon
  as fallback. Same icon set in every file listing.
- **Icons:** single Lucide-style stroke family (`icons.tsx`), 1.8 stroke, `aria-hidden`. Never
  emoji, never mixed sets.

## Interaction

- Hover: background shift only (`hover:bg-neutral-100 dark:hover:bg-neutral-800`), 150ms.
- Focus: every interactive element takes `.focusable` (2px accent ring). Never remove outlines.
- Press: buttons `active:scale-[0.98]`; rows don't scale.
- Cursor: `cursor-pointer` on everything clickable (Tailwind preflight strips it).
- Motion: 150ms ease-out micro-transitions only; `prefers-reduced-motion` collapses all of it.
- Live data: poll quietly; on workspace switch, reset to skeletons immediately — never show a
  previous workspace's data.

## Don't

- No drop shadows beyond `shadow-sm`, no gradients (logo tile is the only exception).
- No `rounded-xl`+, no floating card grids for dense data, no emoji icons.
- No always-visible detail that belongs in an expander (prompts, outputs, logs).
- No raw hex in components — Tailwind tokens (`surface`, `accent`, neutral scale) only.
