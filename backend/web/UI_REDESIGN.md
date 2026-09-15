# NEOVAM HMS — UI/UX Redesign Notes

Implementation of the "NEOVAM Clinical Command Center" refresh.

## Design philosophy
- **Clarity over decoration.** Every component communicates one thing. Density is managed with spacing, not clutter.
- **Token-driven theming.** All colour, typography, spacing, radius, motion and shadow live as CSS custom properties in
  `:root` (`styles.css`), so a future theme/white-label change is a token edit, not a stylesheet archaeology project.
- **System status at a glance.** The dashboard is the operating picture: KPIs count up, alerts pin to a welcome
  banner, trends and sparklines show direction, and activity renders as a timeline.
- **Quiet by default.** Neutral surfaces, one accent family (NEOVAM Blue → Cyan), motion only where it aids
  understanding, and full `prefers-reduced-motion` support.

## Design tokens
| Token | Value | Use |
|---|---|---|
| `--primary` | `#215BD0` (NEOVAM Blue) | Primary actions, active states, links |
| `--accent` | `#13B9D6` (Cyan) | Highlights, focus, secondary brand |
| `--deep` | `#123B8F` | Depth/gradient partner for brand surfaces |
| `--navy-*` | `#08172F / #0B2147 / #102D62` | Sidebar, top bar, page header bands |
| `--ink / --ink-2 / --muted / --subtle` | neutral text ramp | Typography hierarchy |
| `--surface / --surface-2 / --surface-3` | grey ramp | Card, hover, inset backgrounds |
| `--success / --warning / --danger` | status ramp | Badges, trends, alerts |
| `--primary-soft / --accent-soft / --success-bg …` | tinted fills | Icon chips, banners, pills |
| `--font-sans` | Montserrat | Primary UI typeface (Google Fonts, loaded in `index.html`) |
| Spacing | `--sp-1 … --sp-8` (4–64 px) | 4 px modular scale |
| Radius | `--r-sm … --r-xl` (8/10/16/20/24) + `999px` pills | Control/card/modal hierarchy |
| Shadow | `--shadow-xs … --shadow-lg` | Resting/hover/elevated surfaces |
| Motion | `--dur-fast 150ms · --dur 220ms · --dur-slow 420ms`, `--ease-out` | Micro-interactions |
| Breakpoints | 1180 / 1000 / 900 / 860 / 640 / 430 px | Layout reflow |
| `prefers-reduced-motion: reduce` | forces `.01ms` transitions & animations | Accessibility |

## Components & page UX
- **App shell (`shell()` in `app.js`)** — grouped sidebar navigation: **Overview**, **Clinical**,
  **Financial**, **Administration**; each item carries a 24 px stroke SVG icon, an active/current indicator and
  `aria-current`. Top bar shows the page title, facility + live date, quick patient search, notifications
  (unread dot), role-category tag and avatar. Roles with *Specialist Modules* get their own Clinical group
  entry. `patient_journey.js` keeps injecting its Workflow entry after the first sidebar button — the grouped
  shell preserves that hook.
- **Dashboard** — welcome/brand panel with time-of-day greeting, facility eyebrow and live date; 4-count KPI
  grid (icon chip, label, value, sub-label, trend chip, optional sparkline) with a respectful count-up animation;
  *Needs action* cards that deep-link to the owning page (`data-gopage`); activity rendered as a timeline with
  connecting dots.
- **Login** — split screen (brand visual + proof points) on desktop, collapsed on mobile; "Remember me" persists
  the email locally, a "Forgot password?" hint routes to the administrator, and a show/hide password toggle is
  provided. Demo credentials remain pre-filled for evaluation.
- **Loading** — `render()` now paints a skeleton shell (title + KPI grid + panels with shimmer) before each page
  resolves, so navigation feels instant instead of blank.
- **Lists/tables** — sticky headers, clean multiline cells, row hover, `lowStock` tint in inventory, and a
  friendly empty state.
- **Responsive** — sidebar becomes a fixed drawer with overlay ≤860 px; KPI grids collapse 4 → 2 → 1; modals
  become bottom sheets ≤640 px; touch-friendly hit areas throughout.
- **Motion** — page enter, panel fade/up, modal drop-in and toast slide use the shared timing/easing tokens only.

## Accessibility
- Semantic buttons/navigation with `aria-label`, `aria-current`, `aria-busy` on loading screens.
- Contrast-safe text ramp; status is never colour-only (trends also carry direction via text; badges carry text).
- Full keyboard reachability retained (all nav/search bindings unchanged); focus styles rely on `:focus-visible`.
- `prefers-reduced-motion` disables count-up, shimmer, and entrance animations.

## Implementation notes
- **No business logic touched.** All changes are presentational; API shapes and RBAC were left identical and the
  entire backend suite re-ran green after the redesign.
- Files: `backend/web/index.html` (fonts + meta), `backend/web/styles.css` (token system + components),
  `backend/web/app.js` (`shell`, dashboard, login, skeleton). `patient_journey.css/js` and `care_pathways.js`
  remain untouched.
- Figma/Adobe deliverables are not producible from this environment; this document + the CSS token map are the
  single source of truth for the system.