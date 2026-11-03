from pathlib import Path

import pandas as pd
import pytest

from ingestion.build_claims_unified import build

BENE_COLS = [
    "DESYNPUF_ID",
    "BENE_BIRTH_DT",
    "BENE_DEATH_DT",
    "BENE_SEX_IDENT_CD",
    "BENE_HI_CVRAGE_TOT_MONS",
    "BENE_SMI_CVRAGE_TOT_MONS",
]
FAC_COLS = [
    "DESYNPUF_ID",
    "CLM_ID",
    "SEGMENT",
    "CLM_FROM_DT",
    "CLM_THRU_DT",
    "PRVDR_NUM",
    "CLM_PMT_AMT",
    "AT_PHYSN_NPI",
    "ICD9_DGNS_CD_1",
    "ICD9_PRCDR_CD_1",
]
SLOTS = range(1, 14)
CAR_COLS = (
    ["DESYNPUF_ID", "CLM_ID", "CLM_FROM_DT", "CLM_THRU_DT", "ICD9_DGNS_CD_1"]
    + ["TAX_NUM_1", "PRF_PHYSN_NPI_1"]
    + [f"HCPCS_CD_{i}" for i in SLOTS]
    + [f"LINE_NCH_PMT_AMT_{i}" for i in SLOTS]
)


def frame(cols, rows):
    df = pd.DataFrame(rows)
    for c in cols:
        if c not in df:
            df[c] = None
    return df[cols]


@pytest.fixture()
def raw(tmp_path: Path) -> Path:
    d = tmp_path / "raw"
    d.mkdir()
    bene = [
        dict(DESYNPUF_ID="B1", BENE_BIRTH_DT="19400101", BENE_SEX_IDENT_CD="1"),
        dict(DESYNPUF_ID="B2", BENE_BIRTH_DT="19500101", BENE_SEX_IDENT_CD="2"),
        dict(DESYNPUF_ID="B3", BENE_BIRTH_DT="19450101", BENE_DEATH_DT="20090101"),
    ]
    for r in bene:
        r["BENE_HI_CVRAGE_TOT_MONS"] = "12"
        r["BENE_SMI_CVRAGE_TOT_MONS"] = "0" if r["DESYNPUF_ID"] == "B2" else "12"
    for year in (2008, 2009, 2010):
        frame(BENE_COLS, bene).to_csv(
            d / f"DE1_0_{year}_Beneficiary_Summary_File_Sample_1.csv", index=False
        )

    def fac(claim_id, bene_id, seg, dt, amt, proc="P1"):
        return dict(
            DESYNPUF_ID=bene_id,
            CLM_ID=claim_id,
            SEGMENT=seg,
            CLM_FROM_DT=dt,
            CLM_THRU_DT=dt,
            PRVDR_NUM="900",
            CLM_PMT_AMT=amt,
            ICD9_DGNS_CD_1="4019",
            ICD9_PRCDR_CD_1=proc,
            CLM_DRG_CD="123",
            CLM_UTLZTN_DAY_CNT="3",
        )

    ip = [
        fac("I1", "B1", "1", "20080301", "5000"),
        fac("I2", "B2", "1", "20080301", "3000"),
        fac("I3", "B1", "2", None, "100"),
        fac("I4", "B1", "1", "20071201", "100"),
        fac("I5", "B1", "1", "20090101", "0"),
        fac("I6", "B1", "1", "20090101", "-50"),
    ]
    frame(FAC_COLS + ["CLM_DRG_CD", "CLM_UTLZTN_DAY_CNT"], ip).to_csv(
        d / "DE1_0_2008_to_2010_Inpatient_Claims_Sample_1.csv", index=False
    )
    hcpcs = [f"HCPCS_CD_{i}" for i in range(1, 46)]
    op = [fac("O1", "B2", "1", "20080501", "100"), fac("O2", "B4", "1", "20080501", "100")]
    for r in op:
        r["HCPCS_CD_1"] = "99213"
    frame(FAC_COLS + hcpcs, op).to_csv(
        d / "DE1_0_2008_to_2010_Outpatient_Claims_Sample_1.csv", index=False
    )

    def car(claim_id, bene_id, dt, lines):
        r = dict(
            DESYNPUF_ID=bene_id,
            CLM_ID=claim_id,
            CLM_FROM_DT=dt,
            CLM_THRU_DT=dt,
            ICD9_DGNS_CD_1="4019",
            TAX_NUM_1="123",
            PRF_PHYSN_NPI_1="555",
        )
        for i, amt in enumerate(lines, start=1):
            r[f"HCPCS_CD_{i}"] = "99213"
            r[f"LINE_NCH_PMT_AMT_{i}"] = amt
        return r

    carrier_a = [car("C1", "B1", "20080101", ["50", "25"]), car("C2", "B3", "20090601", ["40"])]
    carrier_b = [car("C3", "B1", "20100101", []), car("C4", "B1", "20100101", ["10"])]
    frame(CAR_COLS, carrier_a).to_csv(
        d / "DE1_0_2008_to_2010_Carrier_Claims_Sample_1A.csv", index=False
    )
    frame(CAR_COLS, carrier_b).to_csv(
        d / "DE1_0_2008_to_2010_Carrier_Claims_Sample_1B.csv", index=False
    )
    return d


@pytest.fixture()
def built(raw: Path, tmp_path: Path):
    out = tmp_path / "claims.parquet"
    results = build(raw, out)
    return results, pd.read_parquet(out).set_index("claim_id")


def test_filter_counts(built):
    results, _ = built
    ip = results["inpatient"]
    assert ip["raw_rows"] == 6 and ip["dropped_segment2"] == 1
    assert ip["dropped_outside_window"] == 1
    assert ip["dropped_amount_zero"] == 1 and ip["dropped_amount_negative"] == 1
    assert ip["kept"] == 2
    assert results["outpatient"]["kept"] == 2
    assert results["carrier"]["kept"] == 3 and results["carrier"]["dropped_amount_zero"] == 1


def test_ids_unique_and_prefixed(built):
    _, df = built
    assert df.index.is_unique
    assert set(df.index) == {"I1", "I2", "O1", "O2", "C1", "C2", "C4"}
    assert df.loc["I1", "provider_id"] == "F:900"
    assert df.loc["C1", "provider_id"] == "T:123"


def test_amount_and_lines(built):
    _, df = built
    assert df.loc["C1", "amount"] == 75
    assert df.loc["C1", "n_lines"] == 2
    assert df.loc["O1", "procedure_code"] == "99213"
    assert df.loc["I1", "procedure_code"] == "P1"
    assert df.loc["I1", "drg_code"] == "123" and df.loc["I1", "los_days"] == 3


def test_coverage_logic(built):
    _, df = built
    assert bool(df.loc["I1", "coverage_active"]) is True
    assert bool(df.loc["I2", "coverage_active"]) is True  # Part A months > 0
    assert bool(df.loc["O1", "coverage_active"]) is False  # Part B months = 0
    assert bool(df.loc["O2", "coverage_active"]) is False  # member not in beneficiary files
    assert bool(df.loc["C1", "coverage_active"]) is True
    assert bool(df.loc["C2", "coverage_active"]) is False  # claim after death date


def test_age_and_schema(built):
    _, df = built
    assert abs(df.loc["I1", "age_at_claim"] - 68.2) < 0.2
    assert str(df["from_dt"].dtype).startswith("datetime64")
