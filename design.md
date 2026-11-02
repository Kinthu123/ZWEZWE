# Folio design: forest and linen

The visual source of truth for the Folio Help Desk page (spec 0003). Token values live as CSS custom properties in `web/index.html`; this file records the direction and the rules.

## Direction

Calm, natural, and bookish, tuned for a classroom projector and a phone: deep green ink on a warm linen background, a forest green accent, and a wheat highlight used only as decoration. The title uses a system serif for a printed page feel. Light theme only. Everything is self contained, with no web fonts, CDNs, or remote images.

## Tokens

| Token | Value | Use |
|---|---|---|
| `--bg` | `#F4F1E8` | linen: page background |
| `--surface` | `#FFFDF7` | paper: cards |
| `--ink` | `#22301F` | body text |
| `--muted` | `#5C6857` | secondary text, counter, meta line |
| `--border` | `#E0DBCB` | card and input borders |
| `--accent` | `#2F6B3F` | forest green: primary button, links, focus ring, chip text |
| `--accent-soft` | `#E5EEDD` | sage: chip background (hover `#D6E5CB`) |
| `--highlight` | `#C9A25B` | wheat: logo leaf and small accents only, never text |
| `--danger` | `#B42318` | error text and border |

- Type: `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`; base 17 px, line height 1.6. Title: `--serif` (`"Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif`), 30 px semibold.
- Spacing: 8 px scale (8, 16, 24, 32).
- Shape: cards 16 px radius with a soft shadow; chips fully rounded; inputs 12 px radius.
- Layout: single column, max width 760 px, 16 px side gutter on small screens.
- Motion: only the three pulsing loading dots; disabled under `prefers-reduced-motion`.

## Components

- **Header**: 40 px inline SVG logo (open book with a leaf on a green disc), title, one line subtitle.
- **Card**: surface, border, 16 px radius, shadow, 24 px padding (16 px on phones).
- **Textarea**: labelled, 3 rows, counter right aligned below it.
- **Primary button** (Ask): forest green fill, white text; hover darkens; disabled is 45% opacity with `not-allowed` cursor.
- **Chip button** (example questions): sage fill, green text, fully rounded; same disabled rule.
- **Chip label** (sources): same look as chip button but not interactive.
- **Loading line**: text plus three pulsing dots.
- **Error**: danger text with a danger tinted left border.
- **Answer body**: paragraphs, bold, and bullet lists only.

## Do and don't

- Do set every untrusted string with `textContent`; the answer is escaped before mini markdown.
- Do keep a visible 3 px forest green focus ring on every control.
- Don't use wheat for text (it fails contrast on paper).
- Don't add external assets; the page must render fully offline.
