from pathlib import Path

import pandas as pd

from src.reader import infer_format, load_dataset


def test_infer_format_csv() -> None:
    assert infer_format(Path("sample.csv")) == "csv"


def test_load_dataset_csv(tmp_path: Path) -> None:
    file_path = tmp_path / "data.csv"
    pd.DataFrame({"A Column": [1, 2], "B-Column": [3, 4]}).to_csv(file_path, index=False)
    data = load_dataset(tmp_path)
    assert "data" in data
    assert list(data["data"].columns) == ["a_column", "b_column"]
