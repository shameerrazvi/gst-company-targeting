"""Approximate industry from a company's legal and business names.

The ABN Bulk Extract has no industry code, so names are the only clue. Each rule is a list
of whole words (or word starts, marked with *) checked against the legal name and up to five
business names. Rules are checked in order and the first match wins, so the order matters:
companies that only hold assets come first, because "XYZ PROPERTY HOLDINGS" is a holding
company, not a real estate agency.

This is a deliberately simple, explainable classifier. About half of all companies have
names that say nothing about what they do (for example "BLAFIN PTY LTD"); they are left as
"Unclassified" rather than guessed.
"""
import re

import pandas as pd

RULES = [
    ("Numbered company", [r"ACN \d{9}", r"A\.C\.N\.? \d{9}", r"^\d{9} PTY"]),
    ("Holding, investment or trustee", [
        "HOLDINGS", "HOLDING", "INVESTMENT*", "INVEST", "NOMINEE*", "SUPER", "SUPERANNUATION", "SMSF",
        "SUPERFUND", "TRUSTEE*", "CUSTODIAN*", "ASSET*", "EQUITY", "EQUITIES", "CAPITAL", "FAMILY",
        "PORTFOLIO"]),
    ("Construction and trades", [
        "CONSTRUCT*", "BUILD*", "HOMES", "PLUMB*", "ELECTRIC*", "CARPENT*", "CONCRET*", "ROOF*",
        "TILING", "TILES", "PAINT*", "LANDSCAP*", "EXCAVAT*", "CIVIL", "DEMOLITION", "RENOVAT*",
        "JOINERY", "CABINET*", "FENCING", "GLAZING", "SCAFFOLD*", "WATERPROOF*", "PLASTER*",
        "BRICK*", "AIR CONDITIONING", "HVAC", "REFRIGERATION", "EARTHMOVING", "DRAINAGE", "FLOORING",
        "KITCHENS", "BATHROOMS", "CONTRACTING", "CONTRACTORS"]),
    ("Health and care", [
        "MEDICAL", "HEALTH*", "DENTAL", "DENTIST*", "CLINIC*", "PHYSIO*", "PHARMACY", "CHEMIST",
        "NDIS", "DISABILITY", "PSYCH*", "CHIRO*", "OPTOM*", "NURS*", "ALLIED", "AGED CARE",
        "CARE", "CARERS", "SUPPORT SERVICES", "THERAPY", "THERAPIES", "PATHOLOGY", "RADIOLOGY",
        "SURGERY", "SURGICAL", "MEDICINE", "VETERINARY", "VET"]),
    ("Food and hospitality", [
        "CAFE", "CAFFE", "RESTAURANT*", "FOOD*", "BAKERY", "BAKEHOUSE", "KITCHEN", "BAR", "HOTEL*",
        "CATERING", "COFFEE", "PIZZA*", "ESPRESSO", "TAKEAWAY", "DINING", "BREW*", "WINE*", "PUB",
        "TAVERN", "BISTRO", "GRILL", "SUSHI", "BURGER*", "CHICKEN", "DUMPLING*", "THAI", "KEBAB*",
        "EATERY", "HOSPITALITY", "LIQUOR", "BOTTLE SHOP", "DISTILL*", "MOTEL", "DONUT*", "CAKES",
        "PATISSERIE", "GELATO", "NOODLE*", "BUTCHER*", "SEAFOOD*"]),
    ("Transport and logistics", [
        "TRANSPORT*", "LOGISTIC*", "FREIGHT", "TRUCK*", "HAULAGE", "COURIER*", "DELIVER*",
        "CARRIER*", "REMOVAL*", "TAXI*", "AVIATION", "CARTAGE", "HAULING", "TOWING", "TOW",
        "SHIPPING", "EXPRESS", "FORWARDING", "WAREHOUS*"]),
    ("Property and real estate", [
        "PROPERTY", "PROPERTIES", "REALTY", "REAL ESTATE", "DEVELOPMENT*", "DEVELOPER*", "ESTATE*",
        "LAND", "STRATA", "CONVEYANC*", "APARTMENTS"]),
    ("IT and digital", [
        "TECH", "TECHNOLOG*", "SOFTWARE", "DIGITAL", "IT", "SYSTEMS", "DATA", "CYBER", "CLOUD",
        "WEB", "APPS", "AI", "COMPUTER*", "NETWORK*", "ONLINE", "INTERNET", "ANALYTICS", "LABS",
        "ROBOTICS", "TELECOM*"]),
    ("Professional services", [
        "CONSULT*", "ACCOUNT*", "ADVISORY", "ADVISERS", "ADVISORS", "LAWYERS", "LAW", "LEGAL",
        "SOLICITOR*", "BARRISTER*", "ARCHITECT*", "DESIGN*", "MARKETING", "STRATEGY", "STRATEGIC",
        "RECRUIT*", "STAFFING", "TAX", "TAXATION", "BOOKKEEPING", "AUDIT*", "SURVEY*", "PLANNING",
        "DRAFTING", "ENGINEERS", "ADVERTISING", "PROJECT MANAGEMENT", "PARTNERS", "ASSOCIATES"]),
    ("Finance and insurance", [
        "FINANCE", "FINANCIAL", "LENDING", "LOANS", "MORTGAGE*", "INSURANCE", "WEALTH", "FUNDING",
        "BROKER*", "CREDIT"]),
    ("Retail and wholesale", [
        "RETAIL", "STORE*", "SHOP", "TRADING", "TRADERS", "IMPORT*", "EXPORT*", "WHOLESALE*",
        "SUPPLIES", "SUPPLY", "DISTRIBUT*", "MARKET", "MART", "FASHION", "CLOTHING", "JEWELLERY",
        "FLORIST", "FLOWERS", "FURNITURE", "MERCHANT*", "BOUTIQUE", "COMMERCE", "E-COMMERCE",
        "ECOMMERCE", "AGENCIES", "SALES", "SUPERMARKET*", "GROCER*", "NEWSAGENCY",
        "PHARMACY WAREHOUSE", "TOBACCONIST"]),
    ("Automotive", [
        "AUTO", "AUTOMOTIVE", "AUTOS", "MOTOR", "MOTORS", "MECHANICAL", "MECHANIC*", "SMASH*",
        "PANEL", "TYRE*", "CARS", "CAR", "VEHICLE*", "DETAILING"]),
    ("Beauty, fitness and personal", [
        "BEAUTY", "HAIR*", "SALON", "NAIL*", "BARBER*", "LASH*", "SPA", "FITNESS", "GYM", "YOGA",
        "PILATES", "MASSAGE", "COSMETIC*", "SKIN", "AESTHETIC*", "TATTOO", "WELLNESS", "PERSONAL TRAINING"]),
    ("Education and childcare", [
        "EDUCATION*", "TRAINING", "ACADEMY", "TUTOR*", "LEARNING", "SCHOOL*", "COLLEGE", "CHILDCARE",
        "CHILD CARE", "EARLY LEARNING", "KINDER*", "COACHING", "INSTITUTE"]),
    ("Cleaning, security and facilities", [
        "CLEAN*", "FACILITY", "FACILITIES", "PEST*", "SECURITY", "MAINTENANCE", "GARDEN*", "MOWING",
        "WASTE", "RUBBISH", "SKIP", "HYGIENE", "PROPERTY SERVICES"]),
    ("Manufacturing and engineering", [
        "MANUFACTUR*", "ENGINEERING", "FABRICAT*", "STEEL", "METAL*", "INDUSTRIES", "INDUSTRIAL",
        "PRINT*", "MACHIN*", "WELDING", "PLASTICS", "PACKAGING", "PRODUCTS", "EQUIPMENT"]),
    ("Agriculture", [
        "FARM*", "PASTORAL", "AGRI*", "GRAZING", "ORCHARD*", "CATTLE", "VINEYARD*", "DAIRY",
        "HORTICULTUR*", "LIVESTOCK", "POULTRY", "AQUACULTURE", "FISHING", "PRODUCE"]),
    ("Mining and energy", [
        "MINING", "MINERALS", "RESOURCES", "ENERGY", "SOLAR", "OIL", "GAS", "EXPLORATION",
        "QUARRY*", "DRILLING", "POWER", "BATTER*"]),
    ("Media, creative and events", [
        "MEDIA", "FILM*", "PRODUCTION*", "STUDIO*", "PHOTOGRAPH*", "MUSIC", "ENTERTAINMENT", "EVENTS",
        "EVENT", "CREATIVE*", "PUBLISHING", "RECORDS", "ART", "ARTS", "GALLERY", "TRAVEL", "TOURS",
        "TOURISM"]),
]

UNCLASSIFIED = "Unclassified"
SECTORS = [name for name, _ in RULES] + [UNCLASSIFIED]
PASSIVE = {"Numbered company", "Holding, investment or trustee"}


def _pattern(words):
    parts = []
    for w in words:
        if w.startswith(("ACN", "A\\.", "^")):
            parts.append(w)                         # already a regex
        elif w.endswith("*"):
            parts.append(r"\b" + re.escape(w[:-1]) + r"\w*")
        else:
            parts.append(r"\b" + re.escape(w) + r"\b")
    return re.compile("|".join(parts))


COMPILED = [(name, _pattern(words)) for name, words in RULES]


def classify_one(name: str, business_names: str = "") -> str:
    return classify(pd.Series([name]), pd.Series([business_names])).iloc[0]


def _first_match(text: pd.Series, rules) -> pd.Series:
    out = pd.Series(UNCLASSIFIED, index=text.index, dtype=object)
    left = pd.Series(True, index=text.index)
    for name, pattern in rules:
        hit = left & text.str.contains(pattern)
        out[hit] = name
        left &= ~hit
    return out


def classify(names: pd.Series, business_names: pd.Series) -> pd.Series:
    """Classify every company from its legal name and business names.

    1. An operating industry in the legal name wins ("SMITH PLUMBING PTY LTD").
    2. Otherwise an operating industry in a business name ("SMITH FAMILY HOLDINGS PTY LTD"
       trading as "Smith Plumbing" is a plumbing business).
    3. Otherwise a holding, trustee or numbered company if the legal name says so.
    4. Otherwise Unclassified."""
    legal = _first_match(names.fillna("").str.upper(), COMPILED)
    trading = _first_match(business_names.fillna("").str.upper(),
                           [(n, p) for n, p in COMPILED if n not in PASSIVE])
    operating_legal = ~legal.isin(PASSIVE | {UNCLASSIFIED})
    out = legal.where(operating_legal, trading)
    use_passive = ~operating_legal & (trading == UNCLASSIFIED) & legal.isin(PASSIVE)
    return out.where(~use_passive, legal)
