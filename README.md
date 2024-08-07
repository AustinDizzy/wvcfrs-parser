# wvcfrs-parser

> This project is currently a work in progress.

A Python tool for extracting and structuring data from West Virginia campaign finance disclosure reports (PDFs posted on the [WVSoS's Campaign Finance Reporting System](https://cfrs.wvsos.gov/); the official outputs of [West Virginia Secretary of State Official Form F-7A]()). Converts data from specific sections in the PDF reports into CSV, JSON, Excel (XLSX), or SQLite formats for easy analysis.

Currently parses three key sections a campaign finance report PDF:
  - Section 2: Contributions under $250
  - Section 3: Contributions over $250
  - Section 7: Itemized Expenditures

 This tool is useful as it provides access to address information for campaign contributors provided in Section 3 that is not available in WVSoS bulk data downloads.

## Usage

### `parse.py`

```
$ parse.py --help
usage: parse.py [-h] [--section {2,3,7}] --input INPUT [--output OUTPUT] [--format {csv,json,sqlite,xlsx,print}]

Parse WVSoS's campaign finance report PDFs into structured data

options:
  -h, --help            show this help message and exit
  --section {2,3,7}     Section number to parse, read documentation for more information
  --input INPUT         Input file
  --output OUTPUT       Output file
  --format {csv,json,sqlite,xlsx,print}
                        Output format
```

This tool uses [`pytesseract`](https://pypi.org/project/pytesseract/), [`opencv`](https://opencv.org/), and pattern matching techniques to extract certain data from an input PDF and parse it into a specified format (SQLite, Excel, CSV, JSON) as structured data.

### `merge.py` (WIP)

**Note:** This is currently a work-in-progress and may have errors.

```
$ merge.py --help
usage: merge.py [-h] [--name NAME] [--output OUTPUT] [--database DATABASE]

Fetch & merge bulk contribution data from candidate filings reported to the WV Secretary of State

options:
  -h, --help           show this help message and exit
  --name NAME          Name of the candidate to search for
  --output OUTPUT      Output file (.csv) of merged data to write
  --database DATABASE  Path to the SQLite database file
```

This tool (attempts to) use a variety of methods to combine data from the WVSOS bulk data downloads (CSV) and the data parsed by [`parse.py`](#parsepy) into a single merged dataset, including a general transformer model using [Sentence Transformers](https://huggingface.co/sentence-transformers) and computing the [Levenshtein distance](https://en.wikipedia.org/wiki/Levenshtein_distance).

### `locate-pages.py`

```
$ locate-pages.py --help
usage: locate-pages.py [-h] --input INPUT [--dump-content]

(Attempt to) Locate the page ranges in a PDF file where certain sections start and end using OCR

options:
  -h, --help      show this help message and exit
  --input INPUT   Input file
  --dump-content  Dump PDF content to console during parse
```

Uses known string patterns to attempt to locate the page ranges for certain sections. This would be useful for attempting to automatically parse an entire PDF without having to first cut out the target section.

## Additional Resources

See notebook in [`./notebooks/`](./notebooks/) for some example analysis done using data parsed by this tool, and a [`morrisey-2024.sqlite3`](./notebooks/morrisey-2024.sqlite3) SQLite(3) database with data parsed by this tool from campaign filings produced by the Patrick Morrisey for WV Governor 2024 campaign.

## License
GNU General Public License v3.0 (see [LICENSE](./LICENSE)).

This license only applies to the code and code assets in this repository. Other data contained in or processed by this tool is classified as public record under West Virginia Code and is released by the West Virginia Secretary of State pursuant to the W. Va. Code of State Rules.