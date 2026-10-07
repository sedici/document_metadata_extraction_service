#!/bin/bash
# Prepares api/app to be run with docker compose:
#   1. Ensures .env exists and required vars are set (offers to auto-generate
#      missing service tokens).
#   2. Downloads the public Hugging Face model artifacts the services need
#      (LED fine-tuned model for llm_service, sklearn classifiers for the
#      orchestrator) into the right folders.
# Does NOT run docker compose itself - it just gets you ready to do so.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ENV_FILE="$SCRIPT_DIR/.env"
ENV_EXAMPLE="$SCRIPT_DIR/.env.example"

LLM_MODEL_REPO="Nahpanigo99/fine-tuned-model-led"
SKL_MODELS_REPO="Nahpanigo99/sedici-ml-models"
LLM_MODEL_DIR="$SCRIPT_DIR/llm_service/app/models/fine-tuned-model-led"
SKL_MODELS_DIR="$SCRIPT_DIR/orchestrator/app/models"

echo "=== document_extraction_llm API - init ==="

# ---------------------------------------------------------------------------
# 1. Ensure .env exists
# ---------------------------------------------------------------------------
if [ ! -f "$ENV_FILE" ]; then
  if [ ! -f "$ENV_EXAMPLE" ]; then
    echo "[ERROR] Neither .env nor .env.example found in $SCRIPT_DIR" >&2
    exit 1
  fi
  echo "[INFO] .env not found, creating it from .env.example"
  cp "$ENV_EXAMPLE" "$ENV_FILE"
fi

get_env_var() {
  local key="$1" val
  val=$(grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | tail -n1 | sed -E "s/^${key}=//") || true
  echo "$val"
}

set_env_var() {
  local key="$1" val="$2"
  if grep -qE "^${key}=" "$ENV_FILE" 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$val" >> "$ENV_FILE"
  fi
}

# ---------------------------------------------------------------------------
# 2. Service tokens: detect missing/placeholder, offer to auto-generate
# ---------------------------------------------------------------------------
echo ""
echo "--- Checking service tokens ---"

TOKEN_KEYS=(EXTRACTOR_TOKEN LLM_LED_TOKEN LLM_DEEPANALYZE_TOKEN ORCHESTRATOR_TOKEN)
PLACEHOLDER_EXTRACTOR_TOKEN="supersecret-extractor"
PLACEHOLDER_LLM_LED_TOKEN="supersecret-led"
PLACEHOLDER_LLM_DEEPANALYZE_TOKEN="supersecret-deep"
PLACEHOLDER_ORCHESTRATOR_TOKEN="supersecret-orchestrator-token"

MISSING_TOKENS=()
for key in "${TOKEN_KEYS[@]}"; do
  current_val="$(get_env_var "$key")"
  placeholder_var="PLACEHOLDER_${key}"
  placeholder_val="${!placeholder_var}"
  if [ -z "$current_val" ] || [ "$current_val" = "$placeholder_val" ]; then
    MISSING_TOKENS+=("$key")
  fi
done

if [ ${#MISSING_TOKENS[@]} -eq 0 ]; then
  echo "[OK] All service tokens are set."
else
  echo "[WARN] These tokens are missing or still set to the example placeholder:"
  printf '       - %s\n' "${MISSING_TOKENS[@]}"
  read -rp "Auto-generate secure random tokens for them now? [y/N] " ANSWER
  if [[ "$ANSWER" =~ ^[Yy]$ ]]; then
    for key in "${MISSING_TOKENS[@]}"; do
      new_token="$(openssl rand -hex 32)"
      set_env_var "$key" "$new_token"
      echo "[OK] generated $key"
    done
  else
    echo ""
    echo "[ACTION REQUIRED] Edit $ENV_FILE and set: ${MISSING_TOKENS[*]}"
    echo "Then re-run this script (./init.sh)."
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# 3. Non-secret config vars docker-compose.yml relies on: fill in defaults
#    for anything missing, without prompting (nothing sensitive here).
# ---------------------------------------------------------------------------
echo ""
echo "--- Checking service configuration vars ---"

DEFAULTS_KEYS=(
  IDENTIFIER_PATH_MODEL
  IDENTIFIER_PATH_VECTORIZER
  IDENTIFIER_PATH_LABEL_ENCODER
  SUBJECT_IDENTIFIER_PATH_CLASSIFIER
  SUBJECT_IDENTIFIER_PATH_VECTORIZER
  SUBJECT_IDENTIFIER_PATH_LABEL_ENCODER
  MODEL_SELECTED_SERVICE1
  MODEL_PATH_SERVICE1
  MAX_TOKENS_INPUT_SERVICE1
  MAX_TOKENS_OUTPUT_SERVICE1
  TRUNACTION_SERVICE1
  SPECIAL_TOKENS_TREATMENT_SERVICE1
  ERRORS_TREATMENT_SERVICE1
  QUANTIZATION_SERVICE1
  IS_LOCAL_MODEL1
  IS_OLLAMA_MODEL1
  MODEL_SELECTED_SERVICE2
  IS_LOCAL_MODEL2
  IS_OLLAMA_MODEL2
  OLLAMA_HOST_URL
  ENABLE_QWEN_SERVICE
  MCP_DOCUMENTS_DIR
  MCP_DOCUMENTS_CONTAINER_DIR
)
DEFAULT_IDENTIFIER_PATH_MODEL="models/type_svm_classifier.pkl"
DEFAULT_IDENTIFIER_PATH_VECTORIZER="models/type_svm_vectorizer.pkl"
DEFAULT_IDENTIFIER_PATH_LABEL_ENCODER="models/type_svm_label_encoder.pkl"
DEFAULT_SUBJECT_IDENTIFIER_PATH_CLASSIFIER="models/subject_svm_classifier.pkl"
DEFAULT_SUBJECT_IDENTIFIER_PATH_VECTORIZER="models/subject_svm_vectorizer.pkl"
DEFAULT_SUBJECT_IDENTIFIER_PATH_LABEL_ENCODER="models/subject_svm_label_encoder.pkl"
DEFAULT_MODEL_SELECTED_SERVICE1="LED"
DEFAULT_MODEL_PATH_SERVICE1="models/fine-tuned-model-led"
DEFAULT_MAX_TOKENS_INPUT_SERVICE1="2048"
DEFAULT_MAX_TOKENS_OUTPUT_SERVICE1="512"
DEFAULT_TRUNACTION_SERVICE1="True"
DEFAULT_SPECIAL_TOKENS_TREATMENT_SERVICE1="True"
DEFAULT_ERRORS_TREATMENT_SERVICE1="replace"
DEFAULT_QUANTIZATION_SERVICE1="False"
DEFAULT_IS_LOCAL_MODEL1="True"
DEFAULT_IS_OLLAMA_MODEL1="False"
DEFAULT_MODEL_SELECTED_SERVICE2="qwen3:8b"
DEFAULT_IS_LOCAL_MODEL2="False"
DEFAULT_IS_OLLAMA_MODEL2="True"
DEFAULT_OLLAMA_HOST_URL="http://localhost:11434"
DEFAULT_ENABLE_QWEN_SERVICE="false"
DEFAULT_MCP_DOCUMENTS_DIR="./documents"
DEFAULT_MCP_DOCUMENTS_CONTAINER_DIR="/documents"

FILLED_DEFAULTS=()
for key in "${DEFAULTS_KEYS[@]}"; do
  current_val="$(get_env_var "$key")"
  if [ -z "$current_val" ]; then
    default_var="DEFAULT_${key}"
    default_val="${!default_var}"
    set_env_var "$key" "$default_val"
    FILLED_DEFAULTS+=("$key=$default_val")
  fi
done

if [ ${#FILLED_DEFAULTS[@]} -eq 0 ]; then
  echo "[OK] All service configuration vars are set."
else
  echo "[INFO] Filled in missing vars with defaults:"
  printf '       - %s\n' "${FILLED_DEFAULTS[@]}"
fi

# ---------------------------------------------------------------------------
# 4. Download public model artifacts from Hugging Face (no token required)
# ---------------------------------------------------------------------------
echo ""
echo "--- Checking ML / LLM model artifacts ---"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERROR] python3 not found - needed to download model files from Hugging Face." >&2
  exit 1
fi

PYTHON_BIN="python3"
if ! python3 -c "import huggingface_hub" >/dev/null 2>&1; then
  HF_VENV_DIR="$SCRIPT_DIR/.venv-hf-download"
  if [ ! -d "$HF_VENV_DIR" ]; then
    echo "[INFO] Creating a small local venv for huggingface_hub (system Python is externally managed)..."
    python3 -m venv "$HF_VENV_DIR"
  fi
  PYTHON_BIN="$HF_VENV_DIR/bin/python"
  if ! "$PYTHON_BIN" -c "import huggingface_hub" >/dev/null 2>&1; then
    echo "[INFO] Installing huggingface_hub into $HF_VENV_DIR (one-time, only used to fetch public model files)..."
    "$PYTHON_BIN" -m pip install --quiet --upgrade pip huggingface_hub
  fi
fi

mkdir -p "$LLM_MODEL_DIR" "$SKL_MODELS_DIR"

SKL_FILES=(type_svm_classifier.pkl type_svm_vectorizer.pkl type_svm_label_encoder.pkl subject_svm_classifier.pkl subject_svm_vectorizer.pkl subject_svm_label_encoder.pkl tfidf_vectorizer.pkl)
skl_missing=false
for f in "${SKL_FILES[@]}"; do
  if [ ! -f "$SKL_MODELS_DIR/$f" ]; then
    skl_missing=true
    break
  fi
done

if [ "$skl_missing" = true ]; then
  echo "[INFO] Downloading sklearn classifier models from https://huggingface.co/datasets/$SKL_MODELS_REPO (public, no token needed)..."
  "$PYTHON_BIN" - <<PYEOF
from huggingface_hub import snapshot_download
snapshot_download(repo_id="$SKL_MODELS_REPO", repo_type="dataset", local_dir="$SKL_MODELS_DIR", allow_patterns=["*.pkl"])
print("[OK] sklearn models downloaded to $SKL_MODELS_DIR")
PYEOF
else
  echo "[OK] sklearn classifier models already present in $SKL_MODELS_DIR"
fi

if [ ! -f "$LLM_MODEL_DIR/model.safetensors" ]; then
  echo "[INFO] Downloading fine-tuned LED model from https://huggingface.co/$LLM_MODEL_REPO (public, no token needed, ~650MB)..."
  "$PYTHON_BIN" - <<PYEOF
from huggingface_hub import snapshot_download
snapshot_download(repo_id="$LLM_MODEL_REPO", repo_type="model", local_dir="$LLM_MODEL_DIR")
print("[OK] LLM model downloaded to $LLM_MODEL_DIR")
PYEOF
else
  echo "[OK] fine-tuned LED model already present in $LLM_MODEL_DIR"
fi

# ---------------------------------------------------------------------------
# 5. Qwen / Ollama note (optional service, off by default)
# ---------------------------------------------------------------------------
ENABLE_QWEN="$(get_env_var ENABLE_QWEN_SERVICE)"
if [ "$ENABLE_QWEN" = "true" ]; then
  QWEN_MODEL="$(get_env_var MODEL_SELECTED_SERVICE2)"
  echo ""
  echo "--- Qwen service enabled (ENABLE_QWEN_SERVICE=true) ---"
  echo "[INFO] The qwen model is served through Ollama, not Hugging Face."
  echo "       On the host, make sure Ollama is running and the model is pulled:"
  echo "         ollama pull $QWEN_MODEL"
  echo "[WARN] OLLAMA_HOST_URL=$(get_env_var OLLAMA_HOST_URL) resolves INSIDE the"
  echo "       llm_service_qwen container, not on your host machine. To reach a"
  echo "       host-run Ollama from the container you'll need e.g. --network host"
  echo "       (Linux) or host.docker.internal (Mac/Windows) instead of localhost."
fi

# ---------------------------------------------------------------------------
# 6. Done - print next step (does not run docker compose itself)
# ---------------------------------------------------------------------------
echo ""
echo "=== Init complete ==="
echo "Environment and model artifacts are ready. To start the API:"
echo "  cd $SCRIPT_DIR"
echo "  docker compose build"
echo "  docker compose up -d"
if [ "$ENABLE_QWEN" = "true" ]; then
  echo "  docker compose --profile qwen up -d   # also start the qwen service"
fi
