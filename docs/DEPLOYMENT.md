# Production deployment

The frontend builds to a static bundle. Any static host that can also
reverse-proxy `/replicate-api/*` to `api.replicate.com` will work; this
guide uses nginx (the setup used in production on Hostinger).

## Build the static bundle

```bash
cd frontend && npm install && npm run build
# output: frontend/dist/
```

## nginx configuration

```nginx
server {
  listen 443 ssl http2;
  server_name your-domain.example;

  root /var/www/tribe-virality/dist;
  index index.html;

  # SPA fallback
  location / {
    try_files $uri /index.html;
  }

  # Transparent proxy to Replicate. Never log Authorization or request bodies.
  location /replicate-api/ {
    proxy_pass https://api.replicate.com/;
    proxy_set_header Host api.replicate.com;
    proxy_ssl_server_name on;

    # Stream uploads up to 100 MB.
    client_max_body_size 110m;
    proxy_request_buffering off;
    proxy_buffering off;

    # Strip our hop's logging of credentials.
    access_log off;
  }
}
```

The proxy adds zero application logic — it only forwards requests so the
browser's same-origin policy is satisfied. The user's API token is set as
the `Authorization` header by the browser and passes through untouched.

## Building & pushing the cog model

The image bakes gated model weights (Llama-3.2-3B) at build time, so the push
needs a HuggingFace **read** token passed as a build secret. See
[`../cog/README.md`](../cog/README.md) for the full instructions; the short form:

```bash
echo -n "hf_yourReadTokenHere" > /tmp/hf_token
cog push --secret id=HUGGING_FACE_HUB_TOKEN,src=/tmp/hf_token \
  r8.im/prakhar-bhartiya/meta-tribev2-social-media-content-signal
rm /tmp/hf_token
```
