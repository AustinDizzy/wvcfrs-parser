import argparse
import pytesseract
import pdf2image
from tqdm import tqdm
import re

if __name__ == "__main__":
    argparser = argparse.ArgumentParser(
        description="(Attempt to) Locate the page ranges in a PDF file where certain sections start and end using OCR"
    )
    argparser.add_argument("--input", type=str, help="Input file", required=True)
    argparser.add_argument(
        "--dump-content",
        action="store_true",
        help="Dump PDF content to console during parse",
    )
    args = argparser.parse_args()
    images = pdf2image.convert_from_path(args.input)

    page_ranges: dict[int, tuple[int, int]] = {}
    for i, image in tqdm(enumerate(images), desc="Locating sections..."):
        pg_text = pytesseract.image_to_string(image).replace("\n", "")
        section_1 = any(
            [
                re.match(
                    r"^State of West Virginia Campaign Financial Statement", pg_text
                ),
                re.match(
                    r"TOTAL CONTRIBUTIONS ELECTION YEAR-TO-DATE(.*?)TOTAL EXPENDITURES ELECTION YEAR-TO-DATE",
                    pg_text,
                ),
            ]
        )
        if section_1:
            page_ranges[1] = (i,)
        section_2 = any(
            [
                re.match(r"^Section 2CONTRIBUTIONS OF\$250 OR LESSDATE", pg_text),
                re.match(r"^Contributions ofSection 2 \$250", pg_text),
                re.match(r"^Contributions of\$250 or LessSection 2", pg_text),
            ]
        )
        if section_2:
            if 2 in page_ranges.keys():
                page_ranges[2] = (page_ranges[2][0], i)
            else:
                page_ranges[2] = (i,)
        section_4 = any(
            [
                re.match(r"^Section 4(.*?)FUNDRAISING EVENTS", pg_text),
                re.match(r"^FUNDRAISING EVENTS(.*?)Section 4", pg_text),
                re.match(
                    r"Contributions of \$250 or Less Contributions of More than \$250",
                    pg_text,
                ),
            ]
        )
        if section_4 and not any([section_2, section_1]):
            if 4 in page_ranges.keys():
                page_ranges[4] = (page_ranges[4][0], i)
            else:
                page_ranges[4] = (i,)
        section_5 = any(
            [
                re.match(r"^Section 5(.*?)OTHER INCOME: INTEREST", pg_text),
                re.match(r"^OTHER INCOME: INTEREST(.*?)Section 5", pg_text),
            ]
        )
        if section_5 and not any([section_2, section_1]):
            if 5 in page_ranges.keys():
                page_ranges[5] = (page_ranges[5][0], i)
            else:
                page_ranges[5] = (i,)
        section_6 = any(
            [
                re.match(r"Section 6 LOANS", pg_text),
            ]
        )
        if section_6 and not any([section_2, section_5, section_1]):
            if 6 in page_ranges.keys():
                page_ranges[6] = (page_ranges[6][0], i)
            else:
                page_ranges[6] = (i,)
        section_7 = any(
            [
                re.match(r"^Section 7(.*?)ITEMIZED EXPENDITURES", pg_text),
                re.match(r"^ITEMIZED EXPENDITURES(.*?)Section 7", pg_text),
                re.match(r"Total Expenditures:", pg_text),
            ]
        )
        if section_7 and not any([section_2, section_5, section_1]):
            if 7 in page_ranges.keys():
                page_ranges[7] = (page_ranges[7][0], i)
            else:
                page_ranges[7] = (i,)
        section_8 = any(
            [
                re.match(r"Section 8 RECEIPT OF", pg_text),
            ]
        )
        if section_8 and not any([section_2, section_5, section_1]):
            if 8 in page_ranges.keys():
                page_ranges[8] = (page_ranges[8][0], i)
            else:
                page_ranges[8] = (i,)
        section_9 = any(
            [
                re.match(r"Section 9 UNPAID BILLS", pg_text),
            ]
        )
        if section_9 and not any([section_2, section_5, section_1]):
            if 9 in page_ranges.keys():
                page_ranges[9] = (page_ranges[9][0], i)
            else:
                page_ranges[9] = (i,)
        section_3 = any(
            [
                re.match(r"^Section 3CONTRIBUTIONS OFMORE THAN \$250DATE", pg_text),
                re.match(r"^CONTRIBUTIONS OFSection 3MORE THAN \$250DATE", pg_text),
                re.match(r"Subtotal of all contributions of \$250 or less \(from page 2\)", pg_text),
                re.match(
                    r"(?:\d{1,2}\/\d{1,2}\/\d{4})?(.*?)Employer\/Occupation\: (?:\d{1,2}\/\d{1,2}\/\d{4})?",
                    pg_text,
                ),
            ]
        )
        if section_3 and not any([section_1, section_2, section_4, section_5]) and not (i >= page_ranges.get(4, (9999,))[0]):
            print(f"Found section 3 in {i + 1}")
            if 3 in page_ranges.keys():
                page_ranges[3] = (page_ranges[3][0], i)
            else:
                page_ranges[3] = (i,)
        if args.dump_content:
            print(f"Page {i + 1}:\n{pg_text}\n" + "=" * 80)

    print(page_ranges)
