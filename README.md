# Hermes Nexus

## Viper

**Your AI says it finished. Viper checks.**

The newest public project in this repository is [Viper](./viper), a local verification sidecar that checks AI-agent completion claims against observable ground state and emits evidence receipts.

- [Viper quick start](./viper/README.md)
- [Architecture](./viper/docs/ARCHITECTURE.md)
- [Demo receipts](./viper/DEMO_RECEIPTS.json)
- [Signed provenance commitment](./viper/provenance/PORTFOLIO_COMMITMENT.json)

---

## Hermes Nexus dashboard

Hermes project dashboard built with React + TypeScript + Vite, deployed to Cloudflare Workers.

### Development

```bash
npm install
npm run dev
```

### Build

```bash
npm run build
```

### Deploy

```bash
npm run build
npx wrangler deploy
```

Requires `wrangler login` (OAuth). API tokens may be subject to provider restrictions.
