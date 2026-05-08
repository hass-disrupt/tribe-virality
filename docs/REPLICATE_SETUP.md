# Setting up your Replicate API token

This app runs predictions on Replicate using your own account. Follow these
steps once.

## 1. Create a Replicate account

Go to [replicate.com](https://replicate.com) and sign up. GitHub login works.

## 2. Add credits

Visit [replicate.com/account/billing](https://replicate.com/account/billing)
and add a payment method. You don't need to add credits up-front — Replicate
charges as you go. Predictions for this tool typically cost $0.05–$0.20 each.

## 3. Create an API token

Go to [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens)
and click **New token**. Name it something like "tribe-virality". Click
**Create token** and copy the value (it starts with `r8_`).

## 4. Paste the token in the app

When you open Tribe Virality for the first time, you'll be prompted for the
token. Paste it and click **Continue**. The app validates the token by
calling `GET /v1/account`; no credits are used by validation.

## Security

- The token is stored only in browser memory.
- It is sent only to `api.replicate.com`, transiting a thin nginx
  reverse-proxy on the host (Replicate's API doesn't permit direct browser
  CORS). The proxy is configuration-only and does not log credentials or
  bodies.
- It is **not** stored in `localStorage`, `sessionStorage`, cookies, or any
  database.
- Refreshing the page or closing the tab clears the token; you'll be asked
  to paste it again next time.

If you ever want to revoke the token, return to
[replicate.com/account/api-tokens](https://replicate.com/account/api-tokens)
and click the trash icon.
