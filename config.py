import os

# --- LLM API Settings (LM Studio) ---
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "lm-studio")
SELECTED_MODEL = os.environ.get("SELECTED_MODEL", "qwen2.5-coder-7b-instruct")

# --- Paper hyperparameters (Section 5.1 of V-SQL Paper) ---
TEMPERATURE = 0.0
TOP_P = 1.0
MAX_TOKENS = 800

# --- Database & Paths ---
SQL_DIALECT = "SQLite"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_ROOT = os.path.join(BASE_DIR, "mini_dev_databases")
DEFAULT_DATA_PATH = os.path.join(DATA_DIR, "mini_dev_sqlite.json")
DATA_PATH = DEFAULT_DATA_PATH
TEST_DATA_PATH = os.path.join(DATA_DIR, "Test.json")
VIEWS_DIR = os.path.join(BASE_DIR, "views")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")

# --- Execution mode ---
VIEW_MODE = "manual"  # "manual" | "auto"