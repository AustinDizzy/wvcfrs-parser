import argparse
from datetime import datetime
import pytz
import io
from re import sub
import requests
import urllib.parse
from tqdm import tqdm
from parse import ContributionsOver250Parser, read_pdf_bytes
import csv
from typing import List, Dict
from prompt_toolkit.shortcuts import radiolist_dialog, input_dialog, message_dialog


from fuzzywuzzy import fuzz
from sentence_transformers import SentenceTransformer
import numpy as np


__cfrs_api_host = "https://cfrs.wvsos.gov"
model = SentenceTransformer('all-MiniLM-L6-v2')

def get_name() -> str:
    return input_dialog(
        title="Enter candidate name",
        text="Please enter the name of the candidate you are searching for:",
    ).run()


def search_candidate(name: str) -> List[Dict]:
    name = urllib.parse.quote_plus(name.strip())
    response = requests.get(
        f"{__cfrs_api_host}/CFIS_APIService/api/Search/GetPublicSiteBasicSearchResult?searchText={name}&searchType=ALL&pageNumber=1&pageSize=50",
        verify=False,
    )
    response.raise_for_status()
    return response.json().get("CandidateInformationslist", [])


def select_candidate(candidates: List[Dict]) -> Dict:
    selected = radiolist_dialog(
        title="Select a candidate",
        text="Choose a candidate from the list:",
        values=[
            (
                c["IDNumber"],
                "\n\t".join(
                    [
                        c["CandidateName"].strip() + f" ({c['Party']})",
                        c["OfficeName"]
                        + f" ({c['ElectionYear']}{'' if c['Status'] == 'Active' else ' - ' + c['Status']})",
                    ]
                ),
            )
            for c in sorted(candidates, key=lambda c: c["ElectionYear"], reverse=True)
        ],
    ).run()

    return next((c for c in candidates if c["IDNumber"] == selected), None)


def get_candidate_info(candidate_id: int) -> Dict:
    response = requests.get(
        f"{__cfrs_api_host}/CFIS_APIService/api/Organization/GetCandidatesInformation?memberId={candidate_id}",
        verify=False,
    )
    response.raise_for_status()
    return response.json()


def get_candidate_filings(candidate: Dict) -> List[Dict]:
    cid = candidate["IDNumber"]
    oid = candidate["OfficeId"]
    yr = candidate["ElectionYear"]
    did = candidate["DistrictId"]
    eid = candidate["ElectionId"]

    response = requests.get(
        f"https://cfrs.wvsos.gov/CFIS_APIService/api/Filing/GetFilings?officeID={oid}&committeeID={cid}&electionYear={yr}&districtId={did}&electionId={eid}&pageNumber=1&pageSize=50",
        verify=False,
    )
    response.raise_for_status()
    return response.json()


def timestr_to_local(timestr: str) -> str:
    """
    Formats a timestr "2024-04-08T23:20:57.533" into a more human-readable "Apr 08, 2024 at 11:20PM"
    """
    return (
        datetime.strptime(timestr, "%Y-%m-%dT%H:%M:%S.%f")
        .astimezone(pytz.timezone("US/Eastern"))
        .strftime("%b %d, %Y at %I:%M%p")
    )


def select_filing(filings: List[Dict]) -> Dict:
    selected = radiolist_dialog(
        title="Select a filing",
        text="Choose a filing from the list:",
        values=[
            (
                f["ReportFileName"],
                f"{f["ReportName"]} (filed on {timestr_to_local(f["FiledDate"]) + "" if f["Status"] == "Filed" else " - "+f["Status"]}",
            )
            for f in sorted(filings, key=lambda f: f["FiledDate"], reverse=True)
        ],
    ).run()

    return next((f for f in filings if f["ReportFileName"] == selected), None)

def fetch_report(report_filename: str) -> io.BytesIO:
    response = requests.get(
        f"{__cfrs_api_host}/CFIS_APIService/ReportsOutput/{report_filename.strip()}",
        verify=False,
    )
    response.raise_for_status()
    return io.BytesIO(response.content)

def get_all_con_csv(year : int) -> List[Dict]:
    response = requests.get(
        f"https://cfrs.wvsos.gov/CFIS_APIService/api/DataDownload/GetCSVDownloadReport?year={year}&transactionType=CON&reportFormat=csv&fileName=CON_{year}.csv",
        verify=False,
    )
    response.raise_for_status()
    csvreader = csv.DictReader(io.StringIO(response.text))
    return list(csvreader)

def find_best_match(csv_row, db_rows):
    best_match = None
    highest_score = 0

    for db_row in db_rows:
        # Fuzzy match for name
        csv_name = csv_row['Last Name'] if csv_row['Middle Name'].strip() + csv_row['Suffix'].strip() != 0 else f"{csv_row['First Name']} {csv_row['Last Name']}"
        name_score = fuzz.ratio(csv_name.upper(), db_row['name'].upper())

        # Fuzzy match for employer/occupation
        csv_emp = (
            "" if any([csv_row['Employer'] is None, csv_row['Employer'] == ""]) else
            csv_row['Employer'] if csv_row['Occupation'] == "Other" else f"{csv_row['Employer']} {csv_row['Occupation']}"
        )

        db_emp = (
            "" if db_row['employer_occupation'] is None else
            "RETIRED" if db_row['employer_occupation'] == "RETIRED RETIRED" else db_row['employer_occupation']
        )

        employer_occupation_score = fuzz.ratio(csv_emp.upper(), db_emp.upper())

        # Date comparison
        csv_date = datetime.strptime(csv_row['Receipt Date'], '%m/%d/%Y %I:%M:%S %p')
        db_date = datetime.strptime(db_row['date'], '%m/%d/%Y')  # Adjust format if needed
        date_diff = abs((csv_date - db_date).days)
        date_score = 100 if date_diff == 0 else max(0, 100 - date_diff * 5)  # 20 points off for each day difference

        # Amount comparison
        csv_amount = float(csv_row['Receipt Amount'])
        db_amount = float(db_row['amount'])
        amount_diff = abs(csv_amount - db_amount)
        amount_score = 100 if amount_diff == 0 else max(0, 100 - amount_diff * 10)  # 10 points off for each dollar difference

        # Combine scores (adjust weights as needed)
        total_score = (
            0.5 * name_score + 
            0.1 * employer_occupation_score + 
            0.2 * date_score + 
            0.2 * amount_score
        )

        if total_score > highest_score:
            highest_score = total_score
            best_match = db_row

    return best_match, highest_score

def main():
    argparser = argparse.ArgumentParser(
        description="Fetch & merge bulk contribution data from candidate filings reported to the WV Secretary of State",
    )
    argparser.add_argument("--name", type=str, help="Name of the candidate to search for")
    argparser.add_argument("--output", type=str, help="Output file (.csv) of merged data to write")
    argparser.add_argument("--database", type=str, help="Path to the SQLite database file")
    args = argparser.parse_args()

    candidate_name = (args.name if args.name else get_name()).strip()

    results = search_candidate(candidate_name)
    if not results:
        message_dialog(
            title="No candidates found",
            text=f'No candidates found for "{candidate_name}"',
        ).run()
        return

    candidate = select_candidate(results)
    data = []
    merged_data = []
    candidate_con = []

    # if we've already parsed the data, use the results of that
    if args.database:
        candidate_con = [
            row for row in get_all_con_csv(candidate["ElectionYear"]) 
            if int(row["OrgID"]) == candidate["IDNumber"]
        ]
        import sqlite3
        conn = sqlite3.connect(args.database)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM contributions_over_250")
        parsed_data = [{k: item[k] for k in item.keys()} for item in cur.fetchall()]
        conn.close()
    else:
        # otherwise, fetch & parse the data live from a specified candidate filing  
        candidate_filings = get_candidate_filings(candidate)
        if not candidate_filings:
            message_dialog(
                title="No filings found",
                text=f'No filings found for candidate "{candidate["CandidateName"]}"',
            ).run()
            return

        filing = select_filing(candidate_filings)
        candidate_con = [
            row for row in get_all_con_csv(candidate["ElectionYear"]) 
            if int(row["OrgID"]) == candidate["IDNumber"] and row["Report Name"] == filing["ReportName"]
        ]
        filing_pdf = fetch_report(filing["ReportFileName"])
        data = read_pdf_bytes(filing_pdf)
        parsed_data = ContributionsOver250Parser().parse_all(data)
        print("from api")

    # for every row in the bulk CSV download ...
    for row_csv in tqdm(candidate_con, desc="Merging data...", unit="row"):
        match, _ = find_best_match(row_csv, parsed_data)
        if match:
            print(f"Matched {row_csv['Last Name']} ({row_csv['Receipt Date'].split(' ')[0]}) {row_csv['Receipt Amount']} to {match['name']} ({match['date']}) {match['amount']}")
            # merged_data.append({
            #     **row_csv,
            #     'Address1': utils.extract_addr(match['address']),
            #     'City': utils.extract_city(match['address']),
            #     'State': utils.extract_state(match['address']),
            #     'Zip': utils.extract_zip(match['address']),
            # })



        # create a Levenshtein distance mapping for each row in our parsed data
        # lm : Dict[int, int]  = {}
        # # create a str of known fields to compare to our other parsed data
        # fullname_parts = [row_csv["First Name"], row_csv["Middle Name"].strip(), row_csv["Last Name"]]
        # fullname = " ".join(part for part in fullname_parts if part).replace("  ", " ")
        # fullname += f" {row_csv['Suffix']}" if row_csv['Suffix'] else ""

        # str_1 = " ".join([
        #     row_csv["Receipt Date"].split(" ")[0],
        #     fullname.strip(),
        #     row_csv["Receipt Amount"].strip(),
        #     row_csv["Employer"].strip(),
        #     row_csv["Occupation"].strip(),
        # ])
        # # for every row in our parsed data ...
        # for (i, row_data) in enumerate(parsed_data):
        #     # create a str of known fields to compare to bulk CSV data
        #     if row_data["employer_occupation"] is None:
        #         continue

        #     str_2 = " ".join([
        #         row_data["date"],
        #         row_data["name"],
        #         "{:.4f}".format(float(row_data["amount"])),
        #         row_data["employer_occupation"].strip(),
        #     ])
        #     # calculate the Levenshtein distance between the two strings and save back to parsed_data
        #     print("%s | %s", str_1, str_2)
        #     lm[i] = edit_distance(str_1, str_2)

        # # find the row in parsed_data with the minimum Levenshtein distance, which will likely be the best match
        # min_lev = min(lm, key=lm.get)
        # # merge updated row information to merged, update Address1,Address2,City,State,Zip
        # merged_data.append(row_csv.update({
        #     'Address1': utils.extract_addr(parsed_data[min_lev]['address']),
        #     'City': utils.extract_city(parsed_data[min_lev]['address']),
        #     'State': utils.extract_state(parsed_data[min_lev]['address']),
        #     'Zip': utils.extract_zip(parsed_data[min_lev]['address']),
        # }))

    # write the merged data to a CSV file
    output = args.output if args.output else f"{sub(r'[^\w_]', '', sub(r'[\s-]+', '_', candidate['CandidateName'].lower()))}_{candidate['ElectionYear']}_merged.csv"
    with open(output, "w") as f:
        writer = csv.DictWriter(f, fieldnames=merged_data[0].keys())
        writer.writeheader()
        writer.writerows(merged_data)

    print("TODO: need to merge merged_data (basically employer info and names) with contributions_over_250 data")

if __name__ == "__main__":
    main()
