# wvcfrs-parser

A Python tool for extracting and structuring data from West Virginia campaign finance disclosure reports (PDFs posted on the [WVSoS's Campaign Finance Reporting System](https://cfrs.wvsos.gov/); the official outputs of [West Virginia Secretary of State Official Form F-7A]()). Converts data from specific sections in the PDF reports into CSV, JSON, Excel (XLSX), or SQLite formats for easy analysis.

 Parses three key sections a campaign finance report PDF:
  - Section 2: Contributions under $250
  - Section 3: Contributions over $250
  - Section 7: Itemized Expenditures

 This tool is useful as it provides access to address information for campaign contributors provided in Section 3 that is not available in WVSoS bulk data downloads.

## Usage

```
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

The tool uses [`pytesseract`](https://pypi.org/project/pytesseract/), [`opencv`](https://opencv.org/), and pattern matching techniques to extract certain data from the input PDF and save it in the specified format as structured data.

## Additional Resources

See notebook in [`./notebooks/`](./notebooks/) for some example analysis done using data parsed by this tool.

## License
GNU General Public License v3.0 (see [LICENSE](./LICENSE)).

This license only applies to the code and code assets in this repository. Other data contained in or processed by this tool is classified as public record under West Virginia Code and is released by the West Virginia Secretary of State pursuant to the W. Va. Code of State Rules.