# %%
# Import important library
import requests
import pandas as pd
import os

# %%
# CONFIGURATION
# Include required fields
FIELDS = [
    'cusip', 'issueDate', 'securityType', 'securityTerm', 'auctionDateYear', 'issueDate', 'maturityDate', 'datedDate', 'maturingDate',
    'auctionFormat', 'closingTimeCompetitive', 'offeringAmount', 'allocationPercentage', 'totalTendered', 'totalAccepted', 'bidToCoverRatio',
    'interestRate', 'highYield', 'lowYield', 'averageMedianYield', 'highDiscountRate', 'lowDiscountRate', 'highInvestmentRate', 'lowInvestmentRate',
    'highPrice', 'lowPrice', 'pricePer100', 'updatedTimestamp'
]

# Excel file to keep updating
CSV_FILE = "fetch_data/US_Auction_Data.csv"
# Treasury Direct API
API_URL = "https://www.treasurydirect.gov/TA_WS/securities/jqsearch"

# %%
# Fetch the data
def get_data():
    # FETCH API DATA
    response = requests.get(API_URL)
    new_records = response.json()

    # SELECTED REQUIRED FIELDS ONLY
    df = pd.DataFrame(new_records['securityList'])
    # check if required field existed in the API response
    required_fields = [field for field in FIELDS if field in df.columns]
    new_df = df[required_fields]

    # HANDLE NEW RECORDS AND ADD TO EXISTING EXCEL FILE (ONLY IF AVAILABLE)
    if os.path.exists(CSV_FILE):
        existing_df = pd.read_csv(CSV_FILE)
        # using CUSIP as unique ID, ensuring no same auction added
        new_df['unique_id'] = new_df['cusip'].astype('str')
        existing_df['unique_id'] = existing_df['cusip'].astype('str')
        # filter the data, only keep new/non-existing records
        records_to_add = new_df[~new_df['unique_id'].isin(existing_df['unique_id'])]
        # remove the helper column
        records_to_add = records_to_add.drop(columns=['unique_id'])
        
        # add new data to the current csv file
        if not records_to_add.empty:
            final_df = pd.concat([records_to_add, existing_df], ignore_index=True) # old one first, new one after
            final_df.to_csv(CSV_FILE, index=False)
            print('There are {} new records!'.format(len(records_to_add)))
        else:
            print('No new records found!')
    else:
        # create new csv file if not existed
        new_df.to_csv(CSV_FILE, index=False)
        print('New CSV file created!')

# %%
get_data()


