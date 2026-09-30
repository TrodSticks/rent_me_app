"""Download the LFM2.5-350M model used by AI search (about 700 MB)."""
from huggingface_hub import snapshot_download

from llm_parser import MODEL_DIR, MODEL_ID

if __name__ == '__main__':
    print(f"Downloading {MODEL_ID} to {MODEL_DIR} ...")
    snapshot_download(repo_id=MODEL_ID, local_dir=MODEL_DIR)
    print("Done. AI search will use the model next time the app starts.")
