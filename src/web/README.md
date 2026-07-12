# Diligence OS — marketing site

Informational landing page for Diligence OS (`/` only — no auth, no app).
Next.js App Router, fully static, Tailwind CSS v4.

## Develop

```bash
npm install
npm run dev        # http://localhost:3000
npm run test       # Jest + React Testing Library
npm run lint
npm run build      # static production build
```

## Structure

- `app/page.tsx` — the landing page (single server component; copy lives in
  data arrays at the top of the file)
- `app/layout.tsx` — fonts (Inter + Fraunces via `next/font`) and site metadata
- `app/globals.css` — design tokens (Tailwind `@theme`): `ink` (navy),
  `verify` (green, matches the report's palette), `flag` (red), `paper`
- `app/robots.ts`, `app/sitemap.ts` — SEO conventions

## Config

- `NEXT_PUBLIC_SITE_URL` — canonical URL used in metadata/robots/sitemap
  (defaults to the Vercel placeholder). Set in Vercel project settings.
- Contact email for the early-access CTA is `CONTACT_EMAIL` in `app/page.tsx`.

## Deploy

Intended for Vercel with the project root set to `src/web`. The build is
fully static; no server-side environment variables are required.
