import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ingestion import export_for_bigquery as ex


def write_bene_csvs(raw):
    raw.mkdir(parents=True, exist_ok=True)
    cols = list(ex.BENE_RENAME)
    for year in ex.YEARS:
        row = dict.fromkeys(cols, "1")
        row.update(DESYNPUF_ID="B1", BENE_BIRTH_DT="19400101", BENE_DEATH_DT=None)
        row.update(SP_STATE_CODE="05", BENE_COUNTY_CD="100")
        pd.DataFrame([row, {**row, "DESYNPUF_ID": "B2", "BENE_DEATH_DT": "20090303"}]).to_csv(
            raw / f"DE1_0_{year}_Beneficiary_Summary_File_Sample_1.csv", index=False
        )


def test_bene_year_types_and_values(tmp_path):
    raw = tmp_path / "raw"
    write_bene_csvs(raw)
    out = tmp_path / "out"
    out.mkdir()
    assert ex.export_bene_year(out, raw) == 6
    table = pq.read_table(out / "bene_year.parquet")
    assert table.schema.field("birth_dt").type == pa.date32()
    assert table.schema.field("death_dt").type == pa.date32()
    df = table.to_pandas()
    assert set(df["year"]) == {2008, 2009, 2010}
    assert df["death_dt"].isna().sum() == 3
    assert df["sp_diabetes"].notna().all()


def test_claims_dates_become_date32(tmp_path, monkeypatch):
    processed = tmp_path / "processed"
    processed.mkdir()
    df = pd.DataFrame(
        {
            "claim_id": ["a", "b"],
            "from_dt": pd.to_datetime(["2009-01-02", "2010-05-06"]),
            "thru_dt": pd.to_datetime(["2009-01-03", None]),
            "amount": [10.0, 20.0],
        }
    )
    df.to_parquet(processed / "claims_unified.parquet", index=False)
    monkeypatch.setattr(ex, "PROCESSED", processed)
    out = tmp_path / "out"
    out.mkdir()
    assert ex.export_claims(out) == 2
    table = pq.read_table(out / "claims_unified.parquet")
    assert table.schema.field("from_dt").type == pa.date32()
    assert table.schema.field("thru_dt").type == pa.date32()
    assert table["thru_dt"].null_count == 1
