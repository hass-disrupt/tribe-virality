#!/usr/bin/env bash
# Bake all model weights (TRIBE + Llama-3.2-3B + V-JEPA-2 + whisperx) into
# the cog image at build time so cold starts don't pay a multi-GB download.
#
# Invoked from cog.yaml's `run:` step with the HuggingFace token mounted
# at /run/secrets/HUGGING_FACE_HUB_TOKEN. The token is present only during
# build; it is NOT embedded in the final image.
set -euo pipefail

if [[ ! -f /run/secrets/HUGGING_FACE_HUB_TOKEN ]]; then
  echo "ERROR: HUGGING_FACE_HUB_TOKEN secret not mounted." >&2
  echo "Push with: cog push --secret HUGGING_FACE_HUB_TOKEN=hf_xxx r8.im/..." >&2
  exit 1
fi

export HUGGING_FACE_HUB_TOKEN
HUGGING_FACE_HUB_TOKEN=$(cat /run/secrets/HUGGING_FACE_HUB_TOKEN)

python -c "from tribev2.demo_utils import TribeModel; TribeModel.from_pretrained('facebook/tribev2', cache_folder='/src/cache')"

echo "Weights baked into /src/cache:"
du -sh /src/cache 2>/dev/null || true
