from tkinter import Image
import cv2
import argparse
import pytesseract
import numpy as np
import sqlite3
import re
from pdf2image import convert_from_path, convert_from_bytes
from tqdm import tqdm
from abc import ABC, abstractmethod
from typing import List, Dict

__pytesseract_config = r"--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ,.\-\:\#\&\ \$\/\""


def process_image_cells(image) -> list[str]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    adaptive_thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 4
    )
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    detect_horizontal = cv2.morphologyEx(
        adaptive_thresh, cv2.MORPH_OPEN, horizontal_kernel, iterations=2
    )
    contours_horizontal, _ = cv2.findContours(
        detect_horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    contours_horizontal = sorted(
        contours_horizontal, key=lambda ctr: cv2.boundingRect(ctr)[1]
    )

    row_texts = []
    try:
        for i in range(len(contours_horizontal) - 1):
            x1, y1, w1, h1 = cv2.boundingRect(contours_horizontal[i])
            x2, y2, _, _ = cv2.boundingRect(contours_horizontal[i + 1])

            row = adaptive_thresh[y1 + h1 : y2, 0 : image.shape[1]]

            vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
            detect_vertical = cv2.morphologyEx(
                row, cv2.MORPH_OPEN, vertical_kernel, iterations=2
            )
            contours_vertical, _ = cv2.findContours(
                detect_vertical, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            contours_vertical = sorted(
                contours_vertical, key=lambda ctr: cv2.boundingRect(ctr)[0]
            )

            cell_texts = []
            for j in range(len(contours_vertical) - 1):
                x1, y1, w1, h1 = cv2.boundingRect(contours_vertical[j])
                x2, y2, _, _ = cv2.boundingRect(contours_vertical[j + 1])
                cell = row[:, x1 + w1 : x2]

                scale_percent = 200
                width = int(cell.shape[1] * scale_percent / 100)
                height = int(cell.shape[0] * scale_percent / 100)
                dim = (width, height)
                resized_cell = cv2.resize(cell, dim, interpolation=cv2.INTER_LINEAR)

                text = pytesseract.image_to_string(
                    resized_cell,
                    config=__pytesseract_config,
                )
                cell_texts.append(text.strip())

            row_texts.append(cell_texts)
    except Exception as e:
        print(f"Error processing image: {e}")

    return row_texts


def process_images(images : List[Image]) -> list[str]:
    row_texts = []
    for image in tqdm(images, desc="Reading PDF pages..."):
        image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        row_texts = process_image_cells(image_cv)
        row_texts.extend(row_texts)
    return row_texts

def read_pdf_path(input):
    print(f"Processing PDF file: {input}\n" + "=" * (len(input) + 21))
    return process_images(convert_from_path(input))

def read_pdf_bytes(input):
    print(f"Processing {len(input)} bytes of PDF data\n")
    return process_images(convert_from_bytes(input))

class SectionParser(ABC):
    def __init__(self, file_path: str = None, file_bytes : bytes = None):
        if any([file_path, file_bytes]):
            self.images = convert_from_bytes(file_path) if file_bytes else convert_from_path(file_bytes)
            self.row_texts = [
                    row
                    for row in (read_pdf_bytes(file_path) if file_bytes else read_pdf_path(file_path))
                    if len(row) >= 4 and row[0].strip().upper() != "DATE"
            ]
        return

    @abstractmethod
    def parse(row_text: list[str]) -> Dict:
        pass

    @abstractmethod
    def insert_rows_to_db(self, rows: List[Dict], db_path: str):
        pass

    def parse_all(self, rows: List[Dict] = None) -> List[Dict]:
        return [self.parse(row) for row in (rows or self.row_texts)]


class ContributionsUnder250Parser(SectionParser):
    def parse(self, row_text: str) -> dict:
        return {
            "date": row_text[0],
            "name": row_text[1],
            "election_type": row_text[2]
            if row_text[2] in ["Primary", "General"]
            else "",
            "amount": (
                row_text[-1].replace("$", "").replace(",", "")
                if re.match(r"\$[\d,.]+", row_text[-1])
                else "0"
            ),
        }

    def insert_rows_to_db(self, rows, output):
        conn = sqlite3.connect(output)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS contributions_under_250 (
            date TEXT NOT NULL,
            name TEXT NOT NULL,
            election_type TEXT NOT NULL,
            amount REAL NOT NULL
        )
        """)

        for row in tqdm(rows, desc="Writing rows to database..."):
            cursor.execute(
                """
            INSERT INTO contributions_under_250 (
                date, name, election_type, amount
            ) VALUES (:date, :name, :election_type, :amount)
            """,
                row,
            )

        conn.commit()
        conn.close()


class ContributionsOver250Parser(SectionParser):
    def parse(self, row_text: list[str]) -> dict:
        date = row_text[0]

        name_regex = r"Name: (.*?)[\n\s]+(?:Mailing )?Address:"
        name_match = re.search(name_regex, row_text[1], flags=re.DOTALL)
        if name_match:
            row_text[1] = (
                row_text[1][: name_match.start(1) - 6].strip()
                + row_text[1][name_match.end(1) :].strip()
            )

        mailing_address_regex = r"Mailing Address: (.*?)[\n\s]+Employer"
        mailing_address_match = re.search(mailing_address_regex, row_text[1])
        mailing_address = (
            mailing_address_match.group(1).replace("\n", " ").strip()
            if mailing_address_match
            else ""
        )
        if mailing_address_match:
            row_text[1] = (
                row_text[1][: mailing_address_match.start(1) - 17].strip()
                + row_text[1][mailing_address_match.end(1) :].strip()
            )

        address_regex = r"Address: (.*?)[\n\s]*(?:Employer|Mailing|$)"
        address_match = re.search(address_regex, row_text[1], flags=re.DOTALL)
        address = (
            address_match.group(1).replace("\n", " ").strip() if address_match else ""
        )
        if address_match:
            row_text[1] = (
                row_text[1][: address_match.start(1) - 9].strip()
                + row_text[1][address_match.end(1) :].strip()
            )

        emp_regex = r"Employer/Occupation: (.*?)[\n\s]*$"
        emp_match = re.search(emp_regex, row_text[1], flags=re.DOTALL)
        employer_occupation = (
            emp_match.group(1).replace("\n", "").strip() if emp_match else ""
        )

        amount = (
            row_text[-1].replace("$", "").replace(",", "")
            if re.match(r"\$[\d,.]+", str(row_text[-1]))
            else "0"
        )

        return {
            "date": date,
            "name": name_match.group(1).replace("\n", " ").strip() if name_match else "",
            "address": address,
            "mailing_address": mailing_address if mailing_address else None,
            "employer_occupation": employer_occupation if employer_occupation else None,
            "election_type": row_text[2] if row_text[2] in ["Primary", "General"] else "",
            "amount": amount,
        }

    def insert_rows_to_db(self, rows, output):
        conn = sqlite3.connect(output)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS contributions_over_250 (
            date TEXT NOT NULL,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            mailing_address TEXT,
            employer_occupation TEXT,
            election_type TEXT NOT NULL,
            amount REAL NOT NULL
        )
        """)

        for row in tqdm(rows, desc="Writing rows to database..."):
            cursor.execute(
                """
            INSERT INTO contributions_over_250 (
                date, name, address, mailing_address, employer_occupation, election_type, amount
            ) VALUES (:date, :name, :address, :mailing_address, :employer_occupation, :election_type, :amount)
            """,
                row,
            )

        conn.commit()
        conn.close()


class ItemizedExpenditures(SectionParser):
    def parse(self, row_text: list[str]) -> dict:
        vendor_name = row_text[1].split("\n")[0]
        vendor_address = (
            ", ".join(row_text[1].split("\n")[1:])
            if len(row_text[1].split("\n")) > 1
            else ""
        )
        return {
            "date": row_text[0],
            "vendor_name": vendor_name,
            "vendor_address": vendor_address,
            "expense_description": row_text[2],
            "amount": (
                row_text[-1].replace("$", "").replace(",", "")
                if re.match(r"\$[\d,.]+", row_text[-1])
                else "0"
            ),
        }

    def insert_rows_to_db(self, rows: List[Dict], output: str):
        conn = sqlite3.connect(output)
        c = conn.cursor()

        c.execute("""
        CREATE TABLE IF NOT EXISTS itemized_expenditures (
            date TEXT NOT NULL,
            vendor_name TEXT NOT NULL,
            vendor_address TEXT,
            expense_description TEXT NOT NULL,
            amount REAL NOT NULL
        )
        """)

        for row in tqdm(rows, desc="Writing rows to database..."):
            c.execute(
                """
            INSERT INTO itemized_expenditures (
                date, vendor_name, vendor_address, expense_description, amount
            ) VALUES (:date, :vendor_name, :vendor_address, :expense_description, :amount)
            """,
                row,
            )

        conn.commit()
        conn.close()

        return


def write_to_file(data: list[dict], output, format, parser: SectionParser):
    if format == "csv":
        import csv

        with tqdm(
            open(output, "w", newline=""), desc="Writing rows to CSV..."
        ) as csvfile:
            fieldnames = data[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
    elif format == "json":
        import json

        with tqdm(open(output, "w"), desc="Writing rows to JSON...") as jsonfile:
            json.dump(data, jsonfile, indent=4)
    elif format == "sqlite":
        parser.insert_rows_to_db(data, output)
    elif format == "xlsx":
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "Contributions over $250"

        ws.append(data.keys())
        [
            ws.append(list(row.values()))
            for row in tqdm(data, desc="Writing rows to Excel file...")
        ]

        wb.save(output)
    elif format == "print":
        for row in data:
            print(row)


def main():
    argparser = argparse.ArgumentParser(
        description="Parse WVSoS's campaign finance report PDFs into structured data"
    )
    argparser.add_argument(
        "--section",
        type=int,
        help="Section number to parse, read documentation for more information",
        default=3,
        choices=[2, 3, 7],
    )
    argparser.add_argument("--input", type=str, help="Input file", required=True)
    argparser.add_argument("--output", type=str, help="Output file")
    argparser.add_argument(
        "--format",
        type=str,
        help="Output format",
        default="csv",
        choices=["csv", "json", "sqlite", "xlsx", "print"],
    )
    args = argparser.parse_args()
    parsers: dict[int, SectionParser] = {
        2: ContributionsUnder250Parser,
        3: ContributionsOver250Parser,
        7: ItemizedExpenditures,
    }
    parser = parsers[args.section](file_path=args.input)
    output = (
        args.output
        if args.output
        else args.input.removesuffix("pdf")
        + (args.format if args.format != "sqlite" else "sqlite3")
    )

    write_to_file(parser.parse_all(), output, args.format, parser)


if __name__ == "__main__":
    main()
