# Deploying the Landing Page

The whole site is one HTML file. Deploy in 5 minutes.

## Option A — Cloudflare Pages (recommended, free, fastest DNS)

1. Push `C:\governor\site\` to a GitHub repo (can be the same Governor repo, in a `site/` subdirectory).
2. Cloudflare Pages dashboard → Create project → Connect to Git → pick repo → set build output directory to `site`.
3. Add custom domain in the Pages project settings.

Cost: $0. Custom domain works in ~5 min after DNS update.

## Option B — Vercel (also free, simplest if you already use Vercel)

```bash
cd C:/governor/site
npx vercel --prod
```

Follow the prompts. Custom domain via Vercel dashboard.

## Option C — GitHub Pages (free, slightly slower DNS)

1. Push to a `gh-pages` branch or set `site/` as Pages source in repo settings.
2. Add CNAME file with your custom domain.

## Before going live — required edits

The `index.html` has 3 placeholders to replace:

1. `https://formspree.io/f/REPLACE_WITH_YOUR_FORM_ID` — sign up at https://formspree.io (free tier: 50 submissions/month) and paste your form ID.
2. `https://github.com/REPLACE/governor` (appears twice) — your actual GitHub repo URL.
3. `PAPER.html` — either:
   - convert `MASTER_RESEARCH_PAPER.md` to HTML and place at `site/PAPER.html` (use `pandoc -s -o site/PAPER.html C:/consoledia/MASTER_RESEARCH_PAPER.md`), or
   - link to a GitHub-hosted markdown view.

## Domain name suggestions (check availability before deciding)

Easy to remember, available .dev/.ai are realistic:

- `gov.dev` — taken
- `governor.dev` — likely taken, check
- `governor-proxy.com` — likely available
- `governorai.com` — likely available
- `runlattice.com` — leverages Lattice brand
- `tierproxy.com` — descriptive
- `boundaryproxy.com` — descriptive, ties to research
- `lattice-router.com` — descriptive
- `cheaperllm.com` — direct
- `routegov.dev` — short

Cost: $10–15/yr at Cloudflare Registrar (no markup) or Namecheap.

## Sanity check after deploy

- [ ] Page loads in under 1 second
- [ ] Mobile renders cleanly (open on phone)
- [ ] Form submits and you get the email
- [ ] All 3 placeholders are replaced
- [ ] No console errors in browser devtools
- [ ] Open Graph preview looks right (paste URL in Slack or Discord to test)

If all six pass, you're shipped.
