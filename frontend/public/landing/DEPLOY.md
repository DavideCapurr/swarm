# Deploy the SWARM landing page (one command)

The landing is a single self-contained static file (`index.html`) — no build,
no backend. Pick any host below; all are free for this.

**Before you publish:** open `index.html` and replace `[your-contact-email]`
(two spots: the `mailto:` link + the placeholder note) with your real address.

## Option A — Vercel (fastest, recommended)

```
npm i -g vercel        # once
cd frontend/public/landing
vercel --prod          # follow the prompts; first run links/creates the project
```
You'll get a `https://<name>.vercel.app` URL in ~20s. That's your YC "product
link." Add a custom domain later in the Vercel dashboard if you want.

## Option B — Netlify

```
npm i -g netlify-cli   # once
cd frontend/public/landing
netlify deploy --prod --dir .
```

## Option C — GitHub Pages (no CLI)

Push the repo, then in GitHub → Settings → Pages, serve from the branch and
set the folder to `/frontend/public/landing` (or copy `index.html` to a `docs/`
or `gh-pages` root). URL: `https://<user>.github.io/<repo>/`.

## Local preview (sanity check before deploy)

```
python3 -m http.server 4173 --directory frontend/public
# open http://localhost:4173/landing/
```

> Hosting needs *your* account — I won't create accounts or deploy on your
> behalf. Once it's live, drop the URL into the YC application's product-link
> field and the demo video description.
