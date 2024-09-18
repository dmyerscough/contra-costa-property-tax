import argparse
import io
import locale

import requests
from prettytable import PrettyTable
from PyPDF2 import PdfReader

CONTRA_COSTA_URL = 'https://taxcolp.cccttc.us/api/lookup/address?street={address}&suffix={suffix}&city={city}'

TAX_YEARS = {
    0: {'id': '1920', 'year': '2019-2020'},
    1: {'id': '2021', 'year': '2020-2021'},
    2: {'id': '2122', 'year': '2021-2022'},
    3: {'id': '2223', 'year': '2022-2023'},
    4: {'id': '2324', 'year': '2023-2024'},
    5: {'id': 'Current', 'year': 'Current'},
}

SUFFIX_CHOICES = [
    'AVE',
    'BLVD',
    'CIR',
    'CT',
    'DR',
    'HTS',
    'HWY',
    'LN',
    'LOOP',
    'PATH',
    'PKWY',
    'PL',
    'PT',
    'RD',
    'SQ',
    'ST',
    'TER',
    'WAY'
]

CITY_CHOICES = [
    'ALAMO',
    'AMVAL',
    'ANT',
    'BAYPT',
    'BRINS',
    'BTHIS',
    'BRTWD',
    'BYRON',
    'CANYN',
    'CLYTN',
    'CLYDE',
    'CNCD',
    'CWELL',
    'CRCKT',
    'DAN',
    'DBLO',
    'DISBY',
    'DBLN',
    'ELCER',
    'ELSOB',
    'HERC',
    'KNSTN',
    'KNTSN',
    'LAF',
    'LIVAL',
    'MRTNZ',
    'MRGA',
    'OKLY',
    'ORNDA',
    'PACH',
    'PNOLE',
    'PITTS',
    'PLHL',
    'PLSTN',
    'PTCHI',
    'PTCOS',
    'RMVAL',
    'RCHMD',
    'RODEO',
    'SNPAB',
    'SNRMN',
    'SELBY',
    'STMRY',
    'WALCR',
]


DATA_FIELDS = {
    'IMPROVEMENTS': 'improvements',
    'PERSONAL PROP': 'personal_prop',
    'GROSS VALUE': 'gross_value',
    'EXEMPTIONS': 'exemptions',
    'NET VALUE': 'net_value',
}


def grab_tax_details(address: str, suffix: str, city: str):
    """ """
    taxes = {}

    resp = requests.get(CONTRA_COSTA_URL.format(address=address, suffix=suffix, city=city))

    if resp.status_code != 200:
        raise

    tax_details = resp.json()

    account_number = tax_details['details']['apn'].replace('-', '')[:-1]

    for idx in TAX_YEARS:
        year = TAX_YEARS[idx]['year']

        taxes[year] = {}

        if TAX_YEARS[idx]['id'] == 'Current':
            pdf_resp = requests.get(f'https://taxcolp.cccttc.us/PTS_TaxbillsPdfCY?APN={account_number}')
        else:
            pdf_resp = requests.get(f'https://taxcolp.cccttc.us/PTS_TaxbillsPdfPYHist?taxyear={TAX_YEARS[idx]["id"]}&apn={account_number}')

        pdf_content = io.BytesIO(pdf_resp.content)

        pdf = PdfReader(pdf_content)

        for line in pdf.pages[0].extract_text().splitlines():
            for field in DATA_FIELDS:
                if line.startswith(field):
                    taxes[year][DATA_FIELDS[field]] = float(line.split(' ')[-1].replace(",", "").replace("$", ""))

            # The current tax return shows a summary of what both installments add upto
            if line.startswith('To pay both installments by'):
                taxes[year]['amount'] = float(line.split(' ')[-1].replace(",", "").replace("$", ""))

            # Historical tax returns dont show what both installments add upto
            if line.startswith('$'):
                taxes[year].setdefault('amount', 0)
                taxes[year]['amount'] += float(line.replace(",", "").replace("$", ""))

        if idx > 0:
            for field in list(DATA_FIELDS.values()) + ['amount']:
                # Calculate absolute change
                taxes[year][f'{field}_abs_change'] = taxes[year][field] - taxes[TAX_YEARS[idx - 1]['year']][field]

                # Calculate percentage change
                try:
                    taxes[year][f'{field}_pct_change'] = (taxes[year][f'{field}_abs_change'] / taxes[TAX_YEARS[idx - 1]['year']][field]) * 100
                except ZeroDivisionError:
                    taxes[year][f'{field}_pct_change'] = 0.0

    return taxes


if __name__ == '__main__':

    locale.setlocale(locale.LC_ALL, '')

    parser = argparse.ArgumentParser(prog='Contra Costa Property Tax', description='Query Contra Costa Property Tax History')

    parser.add_argument('-a', '--address', required=True)
    parser.add_argument('-s', '--suffix', choices=SUFFIX_CHOICES, required=True),
    parser.add_argument('-c', '--city', choices=CITY_CHOICES, required=True)

    args = parser.parse_args()

    taxes = grab_tax_details(args.address, args.suffix.upper(), args.city.upper())

    tbl = PrettyTable(
        [
            'Tax Year',
            'Improvements',
            'Improvements Pct',
            'Personal Prop',
            'Personal Prop Pct',
            'Gross Value',
            'Gross Value Pct',
            'Exemptions',
            'Exemptions Pct',
            'Net Value',
            'Net Value Pct',
            'Amount',
            'Amount Pct'
        ]
    )

    for idx in taxes:
        tbl.add_row(
            [
                idx,
                locale.currency(taxes[idx]['improvements'], grouping=True),
                f'{taxes[idx].get("improvements_pct_change", 0.0):.2f}%',
                locale.currency(taxes[idx]['personal_prop'], grouping=True),
                f'{taxes[idx].get("personal_prop_pct_change", 0.0):.2f}%',
                locale.currency(taxes[idx]['gross_value'], grouping=True),
                f'{taxes[idx].get("gross_value_pct_change", 0.0):.2f}%',
                locale.currency(taxes[idx]['exemptions'], grouping=True),
                f'{taxes[idx].get("exemptions_pct_change", 0.0):.2f}%',
                locale.currency(taxes[idx]['net_value'], grouping=True),
                f'{taxes[idx].get("net_value_pct_change", 0.0):.2f}%',
                locale.currency(taxes[idx]['amount'], grouping=True),
                f'{taxes[idx].get("amount_pct_change", 0.0):.2f}%',
            ]
        )

    print(tbl)
