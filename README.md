# Hermes Nexus

Hermes project dashboard built with React + TypeScript + Vite, deployed to Cloudflare Workers.

## Development

```bash
npm install
npm run dev
```

## Build

```bash
npm run build
```

## Deploy (Cloudflare Workers)

```bash
npm run build
npx wrangler deploy
```

Requires `wrangler login` (OAuth) — API tokens are restricted by Cloudflare geo-blocking.
