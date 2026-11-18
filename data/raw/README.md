# Raw Data: Acquiring the Spotify Chart Datasets

This directory (`data/raw/`) holds **local input CSVs** for the Spotify Analytics capstone. The CSVs are **not uploaded to GitHub** because of their size. This README stays in the repository so another researcher can reproduce the input files.

## Original source

- **Platform:** Kaggle
- **Dataset:** *Spotify Charts Daily Updated*
- **Attributed creator:** Gonzalo López Gil
- **Original CSV filenames:** `charts_songs_daily.csv`, `charts_artists_daily.csv`, `charts_albums_weekly.csv`, `artists.csv`

Search Kaggle for the exact dataset title and verify the creator and attached files before using the source. Review the dataset's license and terms. A Kaggle login and access to the dataset might be required. Record the source URL, download/extraction date and dataset version in your research notes.

## Expected local files

| Local file | Extraction rule | Used by |
| --- | --- | --- |
| `charts_songs_daily_365D.csv` | Most recent 365-day window, based on the latest valid date in the song source | Song EDA and cleaning |
| `charts_artists_daily_365D.csv` | Most recent 365-day window, based on the latest valid date in the daily artist source | Artist-chart EDA and cleaning |
| `charts_albums_weekly_52W.csv` | Latest 52 **distinct observed chart dates** in the weekly album source | Weekly album EDA and cleaning |
| `artists.csv` | Unmodified copy of artist master CSV | Artist reference EDA and cleaning |

The extracted daily date windows are chosen **independently** for the song and artist charts. The weekly extract selects 52 available chart dates rather than forcing weekly dates to equal daily boundaries. A 365-day interval might contain fewer than 365 observed artist-chart dates.

## Option A: Reproduce the extracts in Kaggle (recommended)

1. Sign in to [Kaggle](https://www.kaggle.com/) and locate **Spotify Charts Daily Updated** by Gonzalo López Gil.
2. Open **Code → New Notebook** on Kaggle, or create a Kaggle notebook from your account.
3. Import/upload the repository's extraction notebook, `etl/extracting/spotify_daily_charts_extraction.ipynb`. The reference extractor is also known as `spotify_capstone_kaggle_extractor.ipynb` in project materials; use whichever is actually committed under `etl/extracting/`.
4. Choose **Add Input / Add Data** and attach the exact dataset. The notebook searches under `/kaggle/input/` and prefers an input folder containing `spotify-charts-daily-updated`.
5. Verify the input contains the four original CSV filenames listed above. If Kaggle renamed the dataset directory, the notebook searches recursively; if multiple matches exist, choose the correct input rather than selecting one at random.
6. Run the notebook cells from top to bottom. It processes the large charts in **100,000-row chunks**, avoiding a full-file read into memory.
7. Check the printed row counts and date ranges. The extractor writes results to `/kaggle/working/data/raw/`.
8. Check `extraction_manifest.json` for output file names, retained row counts, start/end dates and invalid-date counts. **For weekly albums**, it also records `chart_weeks`.
9. Download the generated `/kaggle/working/spotify_capstone_raw_data.zip` from notebook outputs. The archive includes the four CSVs and the manifest.
10. Extract the ZIP locally and copy the four CSVs into `<project root>/data/raw/`. Keep `extraction_manifest.json` alongside them, or archive a dated copy for reproducibility.

**Kaggle output paths are not Windows paths.** Do not leave the output files inside a downloaded archive; the local notebooks read CSVs from `data/raw/`.

## Option B: Download source data and run an extraction notebook

If you download the original large CSVs directly from Kaggle, retain their exact filenames. The supplied extraction notebook specifically uses `/kaggle/input/` and `/kaggle/working/`, so running it unchanged on Windows will **not** work. Run it in Kaggle, or explicitly adapt the input/output paths before running a local copy. Preserve its 365-day and 52-observed-week selection rules.

## Verify the local files

From the project root, verify the folder contains:

```text
data/raw/
├── README.md
├── charts_songs_daily_365D.csv
├── charts_artists_daily_365D.csv
├── charts_albums_weekly_52W.csv
├── artists.csv
└── extraction_manifest.json       # Recommended, local-only
```

Open each EDA notebook and confirm the printed resolved source path points to this folder. Restart the Jupyter kernel and run all cells when replacing source CSVs. The weekly cleaned **MySQL** table uses `week_start_date` even though the *source extraction notebook* reads the weekly source's `date` column.

## Moving from acquisition to ETL

Follow [`../../etl/README.md`](../../etl/README.md) for the complete refresh procedure. In brief: inspect the extracts with EDA, run cleaning and staging loads, validate staging, then refresh/rebuild the warehouse and verify the website.

## Reproducible research and data policy

- Record the Kaggle dataset URL/version, extraction timestamp, `extraction_manifest.json`, source date coverage and row counts.
- Keep a frozen dated copy of the dataset used in the submitted capstone. A later rolling-window extraction will produce different results.
- Do not put the large CSVs or extracted ZIPs in Git. Keep the source notebook and this README in Git.
- If you share an external Drive archive, configure Viewer access and verify downloading is permitted, subject to source licensing.
- Do not commit Kaggle keys, `.env`, MySQL credentials or copies of data you lack permission to redistribute.

## Git ignore configuration

```gitignore
/data/raw/*
!/data/raw/README.md
```

Git tracks this README but ignores local CSVs and the extraction manifest under `data/raw/`.
