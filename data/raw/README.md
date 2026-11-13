# Raw Data

This directory is reserved for the raw CSV datasets used by the **Spotify Analytics Business Intelligence Capstone**.

## Why the CSV files are not included

The full datasets and extracted chart files are large. To keep the GitHub repository manageable and avoid GitHub's regular Git file-size limits, the raw CSV files are **not committed to this repository**. This directory contains documentation only.

The absence of CSV files does not mean the project uses generated or sample data. Analyses and dashboard results originate from the Spotify chart datasets described below, subject to the documented extraction and cleaning rules.

## Data source and expected files

**Source:** Kaggle, *Spotify Charts Daily Updated*, maintained by Gonzalo López Gil. Locate the source dataset on Kaggle and review its license and usage terms before downloading or redistributing any files.

The following filenames are expected by the project after the one-year extraction step:

| File | Description |
| --- | --- |
| `charts_songs_daily_365D.csv` | Daily song chart observations for the selected 365-day period |
| `charts_artists_daily_365D.csv` | Daily artist chart observations within the selected 365-day calendar period |
| `charts_albums_weekly_52W.csv` | Weekly album chart observations for the selected 52 weekly dates |
| `artists.csv` | Artist reference or master data |

The project's currently documented daily analysis window is **November 11, 2025, through November 10, 2026**. The daily artist source contains observations on **353 distinct dates**, despite using a 365-day calendar window. Weekly album charts use their own weekly date field and period; do not assume daily and weekly start dates match.

## Reproducing the extracts

1. Obtain the source files from the Kaggle dataset through an authorized download or Kaggle notebook environment.
2. Open the project's **Kaggle extraction notebook** (recommended location: `etl/extraction/`).
3. Check its input dataset paths, date boundaries, filenames, and output directory before running the cells.
4. Run the extraction notebook to produce the bounded daily-song, daily-artist, and weekly-album CSVs. Retain the original artist reference file as specified by the notebook.
5. Place the resulting CSV files in this `data/raw/` directory using the expected filenames above.
6. Continue with the notebooks in `etl/eda/` and `etl/cleaning/`, followed by the project's staging and warehouse load scripts.

**Note:** The extraction notebook must be added separately to the repository. The path above is a recommended location, not a guarantee the notebook is already present. Read its instructions to confirm the exact source dataset version and export paths. The source and extraction dates should be recorded for reproducibility.

## Git tracking

The project root `.gitignore` should exclude raw data files while allowing this README to remain in Git:

```gitignore
/data/raw/*
!/data/raw/README.md
```

If CSV files were previously staged, unstage them before committing:

```powershell
git restore --staged -- data/raw/
git add data/raw/README.md
```

If raw files were already committed, changing `.gitignore` will not remove them from Git history. Review the repository history before publishing.

## Data handling

Do not commit Kaggle API credentials, local environment variables, MySQL passwords, database exports, or restricted source files. Cite the upstream dataset and the extraction notebook in academic documentation. The data warehouse is a local database created by the ETL process, not part of this Git repository.
