# Resonance design: warm vinyl

The visual source of truth for the Resonance Help Desk page (spec 0003). Token values live as CSS custom properties in `web/index.html`; this file records the direction and the rules.

## Direction

Warm, friendly, and music flavoured, tuned for a classroom projector and a phone: dark plum ink on a warm off white background, with a coral highlight used only as decoration. Light theme only. Everything is self contained, with no web fonts, CDNs, or remote images.

## Tokens

| Token | Value | Use |
|---|---|---|
| `--bg` | `#FBF7F2` | page background |
| `--surface` | `#FFFFFF` | cards |
| `--ink` | `#2A2233` | body text |
| `--muted` | `#6B6170` | secondary text, counter, meta line |
| `--border` | `#E9E1D8` | card and input borders |
| `--accent` | `#5B2A86` | plum: primary button, links, focus ring, chip text |
| `--accent-soft` | `#F1EAF7` | chip background, loading tint |
| `--highlight` | `#FF6B5A` | coral: logo label ring and small accents only, never text |
| `--danger` | `#B42318` | error text and border |

- Type: `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`; base 17 px, line height 1.6; title 28 px semibold.
- Spacing: 8 px scale (8, 16, 24, 32).
- Shape: cards 16 px radius with a soft shadow; chips fully rounded; inputs 12 px radius.
- Layout: single column, max width 760 px, 16 px side gutter on small screens.
- Motion: only the three pulsing loading dots; disabled under `prefers-reduced-motion`.

## Components

- **Header**: 40 px inline SVG vinyl logo, title, one line subtitle.
- **Card**: surface, border, 16 px radius, shadow, 24 px padding (16 px on phones).
- **Textarea**: labelled, 3 rows, counter right aligned below it.
- **Primary button** (Ask): plum fill, white text; hover darkens; disabled is 45% opacity with `not-allowed` cursor.
- **Chip button** (example questions): accent soft fill, plum text, fully rounded; same disabled rule.
- **Chip label** (sources): same look as chip button but not interactive.
- **Loading line**: text plus three pulsing dots.
- **Error**: danger text with a danger tinted left border.
- **Answer body**: paragraphs, bold, and bullet lists only.

## Do and don't

- Do set every untrusted string with `textContent`; the answer is escaped before mini markdown.
- Do keep a visible 3 px plum focus ring on every control.
- Don't use coral for text (it fails contrast on white).
- Don't add external assets; the page must render fully offline.
