import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POWER_BI = ROOT / "powerbi"


def test_powerbi_json_files_are_valid() -> None:
    files = list(POWER_BI.rglob("*.json")) + list(POWER_BI.rglob("*.pbip")) + list(POWER_BI.rglob("*.pbir"))
    assert files
    for file in files:
        json.loads(file.read_text(encoding="utf-8"))


def test_report_pages_and_visuals_exist() -> None:
    pages_root = POWER_BI / "GameVault.Report" / "definition" / "pages"
    metadata = json.loads((pages_root / "pages.json").read_text(encoding="utf-8"))
    assert metadata["activePageName"] in metadata["pageOrder"]
    assert len(metadata["pageOrder"]) == 4
    for page_name in metadata["pageOrder"]:
        page = pages_root / page_name
        assert (page / "page.json").exists()
        assert list((page / "visuals").glob("*/visual.json")), f"{page_name} has no visuals"


def test_semantic_model_contains_directquery_tables() -> None:
    definition = POWER_BI / "GameVault.SemanticModel" / "definition"
    model = (definition / "model.tmdl").read_text(encoding="utf-8")
    tables = list((definition / "tables").glob("*.tmdl"))
    assert len(tables) >= 10
    assert "ref table Games" in model
    for table in tables:
        assert "mode: directQuery" in table.read_text(encoding="utf-8")
