"""
b00k5 - Comprehensive Indian Expense Auto-Categorizer
Compliant with Schedule III of the Companies Act, 2013 and standard Indian startup operations.
"""

from typing import Dict, Any, List

CATEGORIZATION_RULES = [
    # 1. Cloud, Hosting & Software (SaaS)
    {
        "category": "Software & Cloud Infrastructure",
        "account_code": "5010",
        "description": "Cloud Servers, APIs & Developer Tooling",
        "keywords": [
            "AMAZON WEB SERVICES", "AWS", "GOOGLE CLOUD", "GCP", "MICROSOFT AZURE",
            "DIGITALOCEAN", "CLOUDFLARE", "GITHUB", "GITLAB", "VERCEL", "NETLIFY",
            "SUPABASE", "MONGODB", "DATADOG", "SENTRY", "NEW RELIC", "POSTMAN",
            "OPENAI", "ANTHROPIC", "SCALEWAY", "HETZNER", "HEROKU", "RENDER"
        ]
    },
    {
        "category": "SaaS & Productivity Tools",
        "account_code": "5015",
        "description": "Office Collaboration & Productivity Software",
        "keywords": [
            "GOOGLE WORKSPACE", "GSUITE", "MICROSOFT 365", "OFFICE 365", "SLACK",
            "ZOOM", "ATLASSIAN", "JIRA", "CONFLUENCE", "TRELLO", "NOTION",
            "FIGMA", "MIRO", "CANVA", "ADOBE", "DOCUSIGN", "DROPBOX", "1PASSWORD",
            "LINEAR", "LOOM", "CALENDLY", "AIRTABLE", "HUBSPOT", "MAILCHIMP"
        ]
    },
    # 2. Payment Gateways, Banking & Finance Charges
    {
        "category": "Payment Gateway Processing Fees",
        "account_code": "5020",
        "description": "Merchant Gateway Commissions & Processing Charges",
        "keywords": [
            "RAZORPAY", "CASHFREE", "PAYU", "STRIPE", "CCAVENUE", "PHONEPE",
            "PAYTM MERCHANT", "INSTAMOJO", "BILLDESK", "PINE LABS"
        ]
    },
    {
        "category": "Bank Charges & Processing Fees",
        "account_code": "5025",
        "description": "Bank Account Maintenance, FX Markup & Ledger Fees",
        "keywords": [
            "BANK CHARGES", "ANNUAL CARD FEE", "FOLIO CHARGES", "IMPS CHARGES",
            "NEFT CHARGES", "RTGS CHARGES", "FOREX MARKUP", "CONSOLIDATED CHARGES",
            "MINIMUM BALANCE CHARGE", "DEBIT INTEREST", "PROCESSING FEE"
        ]
    },
    # 3. Statutory, Legal & ROC Charges
    {
        "category": "Statutory & Legal Charges",
        "account_code": "5030",
        "description": "ROC Filing Fees, Stamp Duty & Government Portal Charges",
        "keywords": [
            "MINISTRY OF CORPORATE AFFAIRS", "MCA", "ROC", "REGISTRAR OF COMPANIES",
            "BHARATKOSH", "STAMP DUTY", "CHALLAN", "E-CHALLAN", "PATENT OFFICE",
            "TRADEMARK REGISTRY", "MSME REGISTRATION", "INSPECTION FEE"
        ]
    },
    {
        "category": "Professional, CA & Legal Retainers",
        "account_code": "5035",
        "description": "Auditor, Secretarial & Legal Advisory Fees (Sec 194J)",
        "keywords": [
            "CHARTERED ACCOUNTANT", "COMPANY SECRETARY", "LEGAL ADVOCATE",
            "AUDIT FEES", "TAX ADVISORY", "CONSULTING CHARGES", "RETAINER FEE"
        ]
    },
    # 4. E-Commerce, Selling & Logistics
    {
        "category": "Selling & Marketplace Fees",
        "account_code": "5040",
        "description": "Marketplace Commissions, FBA & Platform Levies",
        "keywords": [
            "AMAZON SELLER", "AMAZON SERVICES", "FLIPKART INTERNET", "MEESHO",
            "MYNTRA", "BLINKIT COMMERCE", "ZEPTO RETAIL", "SWIGGY INSTAMART",
            "ZOMATO HYPERPURE", "SELLER COMMISSION", "MARKETPLACE FEE"
        ]
    },
    {
        "category": "Logistics, Courier & Shipping",
        "account_code": "5045",
        "description": "Freight, Domestic Logistics & Courier Services",
        "keywords": [
            "DELHIVERY", "BLUE DART", "DTDC", "SHIPROCKET", "PORTER", "DUNZO",
            "FEDEX", "DHL EXPRESS", "SHADOWFAX", "EKART", "SPEED POST",
            "BORZO", "WEFAST", "PROFESSIONAL COURIERS"
        ]
    },
    # 5. Travel, Hotels & Conveyance
    {
        "category": "Travel & Conveyance",
        "account_code": "5050",
        "description": "Employee Cab Rides, Fuel, Flights & Local Travel",
        "keywords": [
            "UBER", "OLA CABS", "RAPIDO", "IRCTC", "MAKEMYTRIP", "EASEMYTRIP",
            "INDIGO", "AIR INDIA", "VISTARA", "AKASA AIR", "SPICEJET", "YATRA",
            "CLEARTRIP", "FASTAG", "HPCL", "BPCL", "IOCL", "PETROL PUMP"
        ]
    },
    {
        "category": "Lodging & Business Accommodation",
        "account_code": "5055",
        "description": "Hotel Stays & Conference Lodging",
        "keywords": [
            "OYO ROOMS", "TREEBO", "LEMON TREE", "TAJ HOTELS", "MARRIOTT",
            "HYATT", "ACCOR", "AIRBNB", "HOTEL RESERVATION"
        ]
    },
    # 6. Food, Refreshments & Staff Welfare
    {
        "category": "Staff Welfare & Refreshments",
        "account_code": "5060",
        "description": "Office Meals, Snacks, Pantry Supplies & Team Outings",
        "keywords": [
            "SWIGGY", "ZOMATO", "STARBUCKS", "CAFE COFFEE DAY", "CHAAYOS",
            "CHAI POINT", "BLINKIT", "ZEPTO", "BIGBASKET", "INSTAMART",
            "LUNCH BOX", "HALDIRAM", "TEAM LUNCH", "PANTRY SUPPLIES"
        ]
    },
    # 7. Rent, Co-Working & Office Utilities
    {
        "category": "Rent & Workspace Infrastructure",
        "account_code": "5070",
        "description": "Office Leases & Managed Co-Working Desks (Sec 194I)",
        "keywords": [
            "WEWORK", "AWFIS", "INNOV8", "INDIQUBE", "91SPRINGBOARD",
            "TABLE SPACE", "SMARTWORKS", "COWORK", "OFFICE RENT", "LEASE RENT"
        ]
    },
    {
        "category": "Telecom, Internet & Broadband",
        "account_code": "5075",
        "description": "Office Fiber Connections & Corporate SIM Lines",
        "keywords": [
            "AIRTEL", "JIO", "VODAFONE IDEA", "VI", "ACT FIBERNET",
            "TATA TELESERVICES", "HATHWAY", "BSNL", "BROADBAND", "INTERNET LEASED"
        ]
    },
    {
        "category": "Electricity, Water & Utilities",
        "account_code": "5080",
        "description": "State Electricity Board Bills & Maintenance Dues",
        "keywords": [
            "BESCOM", "MSEDCL", "TPDDL", "TATA POWER", "ADANI ELECTRICITY",
            "CESC", "WATER BOARD", "MAINTENANCE CHARGES", "UTILITY BILL"
        ]
    },
    # 8. Advertising & Digital Marketing
    {
        "category": "Advertising & Digital Marketing",
        "account_code": "5085",
        "description": "Paid Ads, Social Media Campaigns & Sponsorships",
        "keywords": [
            "META ADS", "FACEBOOK ADS", "GOOGLE ADS", "LINKEDIN ADS",
            "TWITTER ADS", "X CORP ADS", "REDDIT ADS", "INFLUENCER",
            "ADWORDS", "CAMPAIGN PROMOTION"
        ]
    },
    # 9. Office Equipment & Capital Assets
    {
        "category": "Office Equipment & Hardware",
        "account_code": "1020",
        "description": "Laptops, Monitors, Mobile Devices & Workstations",
        "keywords": [
            "APPLE INDIA", "DELL INDIA", "LENOVO", "HP INDIA", "CROMA",
            "RELIANCE DIGITAL", "VIJAY SALES", "AMAZON RETAIL LAPTOP",
            "MONITOR", "DESKTOP", "MACBOOK", "SERVER HARDWARE"
        ]
    }
]

def auto_classify_expense(merchant_name: str, raw_ocr_text: str = "") -> Dict[str, str]:
    """
    Classifies a vendor bill or expense based on merchant name and OCR context.
    Matches against standard Schedule III rules.
    """
    combined = f"{merchant_name} {raw_ocr_text}".upper()
    for rule in CATEGORIZATION_RULES:
        if any(keyword in combined for keyword in rule["keywords"]):
            return {
                "category": rule["category"],
                "account_code": rule["account_code"],
                "suggested_narration": rule["description"]
            }
    return {
        "category": "General & Administrative Expense",
        "account_code": "5099",
        "suggested_narration": "Miscellaneous Operational Expense"
    }

def get_category_by_code(code: str) -> Dict[str, str]:
    for rule in CATEGORIZATION_RULES:
        if rule["account_code"] == code:
            return rule
    return {
        "category": "General & Administrative Expense",
        "account_code": "5099",
        "description": "Miscellaneous Operational Expense"
    }
