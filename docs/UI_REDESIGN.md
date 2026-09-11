# One HMS — Enterprise UI Polish

The application UI was redesigned without changing the clinical workflows or API contract.

## Design goals

- Restrained healthcare-enterprise visual language rather than a decorative dashboard
- Stronger hierarchy and information density for hospital staff
- Clear, consistent primary/secondary actions
- Improved table readability and status recognition
- Cleaner forms, dialogs and configuration controls
- Persistent desktop navigation with a real mobile/tablet navigation drawer
- Responsive layouts for desktop, tablet and phone widths
- Better focus states, touch targets and reduced-motion support

## Responsive verification

The dedicated `backend/tests/responsive_ui_e2e.py` suite verifies desktop (1440px), tablet (820px) and mobile (390px) layouts. It checks login rendering, page overflow, dashboard cards, navigation behavior, mobile modal sizing, stacked mobile form fields and table containment.

Current result: **22/22 PASS**.

Reference screenshots are stored in `docs/ui-preview/`.
