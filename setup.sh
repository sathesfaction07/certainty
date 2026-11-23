#!/usr/bin/env bash
set -e

VENV_DIR=".venv"

detect_os() { case "$(uname -s)" in Linux*) OS="linux";; Darwin*) OS="macos";; MINGW*|MSYS*|CYGWIN*) OS="windows";; *) OS="unknown";; esac; echo "Detected OS: $OS"; }
find_python() { for cmd in python3.12 python3.11 python3 python; do if command -v "$cmd" &>/dev/null; then PYTHON="$cmd"; echo "Using: $PYTHON"; return 0; fi; done; echo "ERROR: Python 3.11+ not found."; exit 1; }

setup_venv() {
    [ -d "$VENV_DIR" ] && echo "Venv exists — reusing." || $PYTHON -m venv "$VENV_DIR"
    if [ "$OS" = "windows" ]; then source "$VENV_DIR/Scripts/activate"; else source "$VENV_DIR/bin/activate"; fi
    pip install --upgrade pip --quiet && pip install -e ".[dev]" --quiet
    echo "Dependencies installed."
}

select_cloud() {
    echo ""
    echo "  Certainty uses an LLM to read certificates."
    echo "  Choose backend:"
    echo "  1) AWS (Bedrock Claude + optional Textract)"
    echo "  2) Google Cloud (Document AI + optional Gemini)"
    echo "  3) Skip (configure manually)"
    read -p "Selection [1/2/3]: " CHOICE
    case "$CHOICE" in 1) setup_aws;; 2) setup_gcp;; *) echo "Skipping.";; esac
}

setup_aws() {
    read -p "AWS Account ID: " ACCT
    read -p "Region [us-east-1]: " REGION; REGION=${REGION:-us-east-1}
    ROLE="Certainty-AppRole"

    POLICY=$(cat <<EOF
{"Version":"2012-10-17","Statement":[
  {"Effect":"Allow","Action":["bedrock:InvokeModel"],"Resource":"arn:aws:bedrock:${REGION}::foundation-model/*"},
  {"Effect":"Allow","Action":["textract:DetectDocumentText","textract:AnalyzeDocument"],"Resource":"*"}
]}
EOF
)
    TRUST="{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Principal\":{\"AWS\":\"arn:aws:iam::${ACCT}:root\"},\"Action\":\"sts:AssumeRole\"}]}"

    aws iam get-role --role-name "$ROLE" &>/dev/null 2>&1 || aws iam create-role --role-name "$ROLE" --assume-role-policy-document "$TRUST" --output text --query 'Role.Arn'
    aws iam put-role-policy --role-name "$ROLE" --policy-name "Certainty-Access" --policy-document "$POLICY" 2>/dev/null
    echo "AWS role configured."
    echo "CERT_VALIDATOR_BACKEND=claude" > .env
    echo "AWS_DEFAULT_REGION=${REGION}" >> .env
}

setup_gcp() {
    read -p "GCP Project ID: " PROJECT
    gcloud config set project "$PROJECT" --quiet
    gcloud services enable documentai.googleapis.com --quiet 2>/dev/null
    pip install "certainty[google]" --quiet
    echo "CF_BACKEND=google" > .env
    echo "Google Document AI enabled."
}

main() {
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║            Certainty — Setup                             ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    detect_os; find_python; setup_venv; select_cloud
    echo ""; echo "Ready. Run: certainty data/sample_certs/ --category toys"
}

main "$@"
