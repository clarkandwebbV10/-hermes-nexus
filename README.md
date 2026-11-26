# Hidden Viper — verify what AI agents actually finished

**Your AI says it finished. Hidden Viper checks.**

Hidden Viper is a small, provider-agnostic verifier for AI-agent completion claims. Instead of trusting an agent's final message or a successful tool call, it compares a specific claim with independently observable filesystem or network state and produces a JSON evidence receipt.

**Developer preview · Python 3.11+ · no model, API key, or cloud account required for the local demo.**

## Try it in one minute

```bash
git clone https://github.com/clarkandwebbV10/-hermes-nexus.git hidden-viper-demo
cd hidden-viper-demo
python viper/viper.py demo
```

The demo creates a temporary file, checks its existence and contents, and deliberately checks for a file that was **not** created. It prints three receipts with expected statuses:

```text
VERIFIED
VERIFIED
CONTRADICTED
```

These are expected results, **not** a live benchmark or a claim that an outside agent was controlled. Each full JSON receipt records the claim, observed state, timestamp, and digest. The demo removes its temporary file afterward.

### What can it verify?

| Claim type | Independent observation |
| --- | --- |
| `file_exists` | Whether a path exists |
| `file_sha256` | The file's actual SHA-256 digest |
| `file_contains` | Whether specified text is present |
| `tcp_listen` | Whether a TCP connection can be established |
| `http_status` | Whether an HTTP endpoint returns the expected status |

Verdicts are **VERIFIED**, **CONTRADICTED**, or **UNVERIFIED**. Unknown or malformed claims should never be treated as successful work. This initial public verifier deliberately **does not execute arbitrary shell commands**.

## Next: verify a claim from your own workflow

[Follow the Hidden Viper quick start](./viper/README.md) to inspect a claim envelope and run the `verify` or JSONL `stream` command. A useful first test is an agent claiming it created a file: check the path separately instead of accepting its response.

- [Source and CLI](./viper/)
- [Architecture and limitations](./viper/docs/ARCHITECTURE.md)
- [Sample evidence receipts](./viper/DEMO_RECEIPTS.json)
- [Reproducible tests / CI](./.github/workflows/viper-ci.yml)
- [Signed provenance commitment](./viper/provenance/PORTFOLIO_COMMITMENT.json)
- [Contributing](./viper/CONTRIBUTING.md) · [Security disclosures](./viper/SECURITY.md)

### Release status and trust boundary

The public `main` branch is **not yet a production safety gate**. [PR #3](https://github.com/clarkandwebbV10/-hermes-nexus/pull/3) addresses a known boolean-validation bug (string `"false"` could be interpreted as true) and version-metadata inconsistency. The correction must be independently verified and merged before claiming that behavior is fixed in `main`.

**Claim is not state.** A VERIFIED receipt only supports the specific property checked, at the time and from the vantage point of the verifier. It does not prove an agent is reliable in general or that an entire deployment is safe.

**License:** Source-visible developer preview; copyright reserved. The [current license](./viper/LICENSE.md) does not grant general production, redistribution, or commercial use rights. Third-party components retain their respective licenses.

---

## Hermes Nexus dashboard

This repository also includes a Hermes project dashboard built with React + TypeScript + Vite, deployed to Cloudflare Workers. It is a separate component from the Hidden Viper local verifier.

### Development

```bash
npm install
npm run dev
```

### Build and deploy

```bash
npm run build
npx wrangler deploy
```

Requires `wrangler login` (OAuth). API tokens may be subject to provider restrictions.
