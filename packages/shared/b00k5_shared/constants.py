from decimal import Decimal

# Indian State Codes Mapping (GST 2-digit prefixes)
INDIAN_STATE_CODES = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan",
    "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh",
    "13": "Nagaland", "14": "Manipur", "15": "Mizoram", "16": "Tripura",
    "17": "Meghalaya", "18": "Assam", "19": "West Bengal", "20": "Jharkhand",
    "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra & Nagar Haveli and Daman & Diu", "27": "Maharashtra", "29": "Karnataka",
    "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu",
    "34": "Puducherry", "35": "Andaman & Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh",
    "38": "Ladakh"
}

# Statutory Deadlines & Fine Rates under Companies Act 2013
MCA_DAILY_LATE_FEE_INR = Decimal("100.00")
BOARD_MEETING_MAX_INTERVAL_DAYS = 120
DIR3_KYC_DEADLINE_MONTH = 9
DIR3_KYC_DEADLINE_DAY = 30

# S3 Bucket Names (Phase 0)
BUCKET_STATEMENTS = "b00k5-statements"
BUCKET_RECEIPTS = "b00k5-receipts"
BUCKET_STATUTORY = "b00k5-statutory"
