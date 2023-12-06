from matplotlib.lines import lineStyles
import requests
import json
import pandas as pd
import time
from datetime import datetime
from sec_api import QueryApi
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Constants
api_key = 'api_key_here'
xbrl_converter_api_endpoint = 'https://api.sec-api.io/xbrl-to-json'

# Function to get XBRL-JSON for a given accession number with retry logic
def get_xbrl_json(accession_no, retry=0):
    request_url = f"{xbrl_converter_api_endpoint}?accession-no={accession_no}&token={api_key}"
    try:
        response = requests.get(request_url)
        return json.loads(response.text)
    except:
        if retry > 5:
            raise Exception('API error')
        time.sleep(0.5)
        return get_xbrl_json(accession_no, retry + 1)

# Function to extract balance sheet data from XBRL-JSON
def get_balance_sheet(xbrl_json):
    balance_sheet_store = {}
    for usGaapItem in xbrl_json['BalanceSheets']:
        values, indices = [], []
        for fact in xbrl_json['BalanceSheets'][usGaapItem]: 
            if 'segment' not in fact:
                index = fact['period']['instant']
                if index not in indices:
                    value = fact['value'] if "value" in fact else 0
                    values.append(value)
                    indices.append(index)
        balance_sheet_store[usGaapItem] = pd.Series(values, index=indices)
    return pd.DataFrame(balance_sheet_store).T

# Function to clean the balance sheet DataFrame
def clean_balance_sheet(balance_sheet):
    balance_sheet = balance_sheet.dropna(axis=1, thresh=5)  # Drop columns with more than 5 NaNs
    balance_sheet.columns = pd.to_datetime(balance_sheet.columns).date  # Convert index to datetime
    return balance_sheet.sort_index(axis=1)  # Sort by date

# Function to convert XBRL-JSON of income statement to pandas dataframe
def get_income_statement(xbrl_json):
    income_statement_store = {}
    for usGaapItem in xbrl_json['StatementsOfIncome']:
        values, indices = [], []
        for fact in xbrl_json['StatementsOfIncome'][usGaapItem]:
            if 'segment' not in fact:
                index = fact['period']['startDate'] + '-' + fact['period']['endDate']
                if index not in indices:
                    values.append(fact['value'])
                    indices.append(index)
        income_statement_store[usGaapItem] = pd.Series(values, index=indices)
    return pd.DataFrame(income_statement_store).T

# Fetching all 10-Q and 10-K filings for a company and building comprehensive balance sheet
def fetch_and_process_financial_statements(ticker):
    query_api = QueryApi(api_key=api_key)
    query = {
        "query": {
            "query_string": {
                "query": f"(formType:\"10-Q\" OR formType:\"10-K\") AND ticker:{ticker}"
            }
        },
        "from": "0",
        "size": "20",
        "sort": [{"filedAt": {"order": "desc"}}]
    }

    query_result = query_api.get_filings(query)
    accession_numbers = [filing['accessionNo'] for filing in query_result['filings']]

    balance_sheet_final = pd.DataFrame()
    income_statement_final = pd.DataFrame()

    for accession_no in accession_numbers:
        xbrl_json_data = get_xbrl_json(accession_no)
        
        # Process Balance Sheet
        balance_sheet = get_balance_sheet(xbrl_json_data)
        balance_sheet_cleaned = clean_balance_sheet(balance_sheet)
        balance_sheet_final = balance_sheet_final.combine_first(balance_sheet_cleaned)
        
        # Process Income Statement
        income_statement = get_income_statement(xbrl_json_data)
        income_statement_final = income_statement_final.combine_first(income_statement)

    return balance_sheet_final, income_statement_final

# example usage
ticker = 'AAPL'
balance_sheet, income_statement = fetch_and_process_financial_statements(ticker)

if balance_sheet.empty:
    print(f'No financial statements found for {ticker}')

# find the most recent date in the balance sheet and income statement
balance_sheet_date = balance_sheet.columns[-1]
income_statement_date = income_statement.columns[-1]

# Interpretation of the Most Recent Balance Sheet
print(f"Balance Sheet as of {balance_sheet_date}:")
print(balance_sheet[balance_sheet_date])

# Function to convert string values to numeric
def convert_to_numeric(value):
    try:
        return float(value)
    except ValueError:
        return value

print("\n")

print(f"Income Statement for the period ending on {income_statement_date}:")
print(income_statement[income_statement_date])
print("\n")

# Convert string values to numeric in the DataFrames
balance_sheet = balance_sheet.apply(pd.to_numeric, errors='coerce', axis=1)
income_statement = income_statement.apply(pd.to_numeric, errors='coerce', axis=1)

latest_balance_date = balance_sheet.columns[-1]
latest_income_date = income_statement.columns[-1]

#print(balance_sheet.index)

#print(income_statement.index)


# Ratio Calculations
# Liquidity Ratios
current_ratio = balance_sheet.loc['AssetsCurrent', latest_balance_date] / balance_sheet.loc['LiabilitiesCurrent', latest_balance_date]
quick_ratio = (balance_sheet.loc['AssetsCurrent', latest_balance_date] - balance_sheet.loc['InventoryNet', latest_balance_date]) / balance_sheet.loc['LiabilitiesCurrent', latest_balance_date]

# Profitability Ratios
net_income = income_statement.loc['NetIncomeLoss', latest_income_date]
revenue = income_statement.loc['RevenueFromContractWithCustomerExcludingAssessedTax', latest_income_date]
net_profit_margin = net_income / revenue
return_on_equity = net_income / balance_sheet.loc['StockholdersEquity', latest_balance_date]

# Solvency Ratio
debt_to_equity_ratio = balance_sheet.loc['Liabilities', latest_balance_date] / balance_sheet.loc['StockholdersEquity', latest_balance_date]

# Efficiency Ratio
asset_turnover_ratio = revenue / balance_sheet.loc['Assets', latest_balance_date]

# Printing Ratios
print("Financial Ratios as of latest dates:")
print(f"Current Ratio: {current_ratio:.2f}")
print(f"Quick Ratio: {quick_ratio:.2f}")
print(f"Net Profit Margin: {net_profit_margin:.2%}")
print(f"Return on Equity: {return_on_equity:.2%}")
print(f"Debt to Equity Ratio: {debt_to_equity_ratio:.2f}")
print(f"Asset Turnover Ratio: {asset_turnover_ratio:.2f}")









