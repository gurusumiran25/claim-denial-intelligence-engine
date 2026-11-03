# Runs every SQL file in sql\eda against BigQuery and saves the results in docs\eda_results\.
# Run from the project root (PowerShell, venv not required, gcloud must be logged in):
#     .\scripts\run_eda.ps1
New-Item -ItemType Directory -Force docs\eda_results | Out-Null
Get-ChildItem sql\eda\*.sql | Sort-Object Name | ForEach-Object {
    Write-Host "Running $($_.Name) ..."
    $out = "docs\eda_results\$($_.BaseName).txt"
    Get-Content $_.FullName -Raw | bq query --use_legacy_sql=false --max_rows=100 | Out-File -Encoding utf8 $out
}
Write-Host "Done. Results are in docs\eda_results"
