"""
Seed the database with realistic sample data for Chicago, Lincolnwood,
Sauganash, and Skokie. Used for demos and frontend development.
"""
import logging
import random
from datetime import date, timedelta
from decimal import Decimal
from app.database import SessionLocal
from app.models.property import Property
from app.models.sale import Sale
from app.models.foreclosure import Foreclosure, ForeclosureStatus
from app.models.eviction import Eviction, EvictionStatus
from app.models.bank_seizure import BankSeizure, SeizureType
from app.models.listing import Listing, PriceHistory, ListingSource, ListingStatus
from app.utils.normalize import normalize_address, to_decimal, to_coord

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


SAMPLE_PROPERTIES = [
    {"address": "1234 N Halsted St", "city": "Chicago", "zip_code": "60622", "lat": 41.9043, "lon": -87.6485, "value": 685000, "neighborhood": "Wicker Park"},
    {"address": "2150 W Roscoe St", "city": "Chicago", "zip_code": "60618", "lat": 41.9434, "lon": -87.6824, "value": 845000, "neighborhood": "Roscoe Village"},
    {"address": "5524 S Cornell Ave", "city": "Chicago", "zip_code": "60637", "lat": 41.7956, "lon": -87.5851, "value": 420000, "neighborhood": "Hyde Park"},
    {"address": "3812 N Sheffield Ave", "city": "Chicago", "zip_code": "60613", "lat": 41.9509, "lon": -87.6539, "value": 925000, "neighborhood": "Lakeview"},
    {"address": "1027 W 18th St", "city": "Chicago", "zip_code": "60608", "lat": 41.8576, "lon": -87.6529, "value": 485000, "neighborhood": "Pilsen"},
    {"address": "6748 S King Dr", "city": "Chicago", "zip_code": "60637", "lat": 41.7717, "lon": -87.6160, "value": 235000, "neighborhood": "Woodlawn"},
    {"address": "4520 N Lincoln Ave", "city": "Chicago", "zip_code": "60625", "lat": 41.9651, "lon": -87.6852, "value": 615000, "neighborhood": "Lincoln Square"},
    {"address": "1900 S State St", "city": "Chicago", "zip_code": "60616", "lat": 41.8569, "lon": -87.6276, "value": 535000, "neighborhood": "South Loop"},
    {"address": "7240 N Sheridan Rd", "city": "Chicago", "zip_code": "60626", "lat": 42.0103, "lon": -87.6647, "value": 385000, "neighborhood": "Rogers Park"},
    {"address": "3500 W Belmont Ave", "city": "Chicago", "zip_code": "60618", "lat": 41.9395, "lon": -87.7129, "value": 425000, "neighborhood": "Avondale"},
    {"address": "856 E 79th St", "city": "Chicago", "zip_code": "60619", "lat": 41.7517, "lon": -87.6027, "value": 145000, "neighborhood": "Chatham"},
    {"address": "2143 N Damen Ave", "city": "Chicago", "zip_code": "60647", "lat": 41.9211, "lon": -87.6779, "value": 725000, "neighborhood": "Bucktown"},
    {"address": "6730 N Lincoln Ave", "city": "Lincolnwood", "zip_code": "60712", "lat": 42.0064, "lon": -87.7271, "value": 495000, "neighborhood": "Lincolnwood"},
    {"address": "4242 W Pratt Ave", "city": "Lincolnwood", "zip_code": "60712", "lat": 42.0048, "lon": -87.7327, "value": 575000, "neighborhood": "Lincolnwood"},
    {"address": "7140 N Kimball Ave", "city": "Lincolnwood", "zip_code": "60712", "lat": 42.0103, "lon": -87.7155, "value": 612000, "neighborhood": "Lincolnwood"},
    {"address": "3818 W Touhy Ave", "city": "Lincolnwood", "zip_code": "60712", "lat": 42.0123, "lon": -87.7218, "value": 685000, "neighborhood": "Lincolnwood"},
    {"address": "6135 N Lemont Ave", "city": "Sauganash", "zip_code": "60646", "lat": 41.9923, "lon": -87.7521, "value": 845000, "neighborhood": "Sauganash"},
    {"address": "6428 N Kilpatrick Ave", "city": "Sauganash", "zip_code": "60646", "lat": 41.9982, "lon": -87.7427, "value": 925000, "neighborhood": "Sauganash"},
    {"address": "5841 N Forest Glen Ave", "city": "Sauganash", "zip_code": "60646", "lat": 41.9881, "lon": -87.7464, "value": 1150000, "neighborhood": "Sauganash"},
    {"address": "8132 Skokie Blvd", "city": "Skokie", "zip_code": "60077", "lat": 42.0339, "lon": -87.7385, "value": 425000, "neighborhood": "Skokie"},
    {"address": "5040 W Oakton St", "city": "Skokie", "zip_code": "60077", "lat": 42.0260, "lon": -87.7547, "value": 385000, "neighborhood": "Skokie"},
    {"address": "9210 N Kostner Ave", "city": "Skokie", "zip_code": "60076", "lat": 42.0512, "lon": -87.7402, "value": 545000, "neighborhood": "Skokie"},
    {"address": "4825 W Main St", "city": "Skokie", "zip_code": "60077", "lat": 42.0334, "lon": -87.7488, "value": 365000, "neighborhood": "Skokie"},
    {"address": "8742 N Karlov Ave", "city": "Skokie", "zip_code": "60076", "lat": 42.0451, "lon": -87.7359, "value": 495000, "neighborhood": "Skokie"},
    {"address": "5611 W Howard St", "city": "Skokie", "zip_code": "60077", "lat": 42.0185, "lon": -87.7641, "value": 415000, "neighborhood": "Skokie"},
    # Evanston
    {"address": "1620 Sherman Ave", "city": "Evanston", "zip_code": "60201", "lat": 42.0467, "lon": -87.6826, "value": 615000, "neighborhood": "Downtown Evanston"},
    {"address": "2438 Park Pl", "city": "Evanston", "zip_code": "60201", "lat": 42.0532, "lon": -87.6921, "value": 825000, "neighborhood": "Northwest Evanston"},
    {"address": "915 Hinman Ave", "city": "Evanston", "zip_code": "60202", "lat": 42.0421, "lon": -87.6790, "value": 1245000, "neighborhood": "Southeast Evanston"},
    {"address": "1730 Chicago Ave", "city": "Evanston", "zip_code": "60201", "lat": 42.0476, "lon": -87.6791, "value": 495000, "neighborhood": "Downtown Evanston"},
    {"address": "2710 Central St", "city": "Evanston", "zip_code": "60201", "lat": 42.0631, "lon": -87.7102, "value": 685000, "neighborhood": "Central Evanston"},
    {"address": "1342 Dewey Ave", "city": "Evanston", "zip_code": "60201", "lat": 42.0512, "lon": -87.6950, "value": 565000, "neighborhood": "West Evanston"},
    {"address": "844 Mulford St", "city": "Evanston", "zip_code": "60202", "lat": 42.0335, "lon": -87.6824, "value": 425000, "neighborhood": "South Evanston"},
]

SAMPLE_BANKS = ["Wells Fargo Bank N.A.", "JPMorgan Chase Bank", "Bank of America N.A.",
                "U.S. Bank National Association", "PNC Bank N.A.", "Citibank N.A.",
                "Fifth Third Bank", "BMO Harris Bank", "Mr. Cooper"]

SAMPLE_NAMES = ["Smith, John A.", "Garcia, Maria L.", "Johnson, Robert E.", "Williams, Patricia D.",
                "Brown, Michael J.", "Davis, Jennifer M.", "Miller, David W.", "Wilson, Linda S.",
                "Moore, James R.", "Taylor, Sarah K.", "Anderson, Christopher P.", "Thomas, Barbara N.",
                "Jackson, Daniel C.", "Martinez, Elizabeth A.", "White, Mark T.", "Harris, Susan G."]

LANDLORDS = ["Lakeshore Properties LLC", "Windy City Holdings Inc", "Pioneer Realty Group",
             "Northshore Residential LLC", "Loop Property Management"]

EVICTION_REASONS = ["Non-payment of rent", "Lease violation - unauthorized occupants",
                    "Holdover after lease expiration", "Property damage",
                    "Illegal activity on premises"]


def seed():
    random.seed(42)
    db = SessionLocal()
    try:
        if db.query(Property).count() > 0:
            log.info("Database already has data. Skipping seed.")
            return

        log.info("Seeding properties...")
        properties = []
        for sp in SAMPLE_PROPERTIES:
            prop = Property(
                pin=f"{random.randint(10000000000000, 99999999999999)}",
                address=sp["address"],
                address_normalized=normalize_address(sp["address"]),
                city=sp["city"],
                state="IL",
                zip_code=sp["zip_code"],
                neighborhood=sp["neighborhood"],
                municipality=sp["city"],
                property_type="Single Family",
                year_built=random.randint(1920, 2015),
                square_footage=to_decimal(random.randint(1100, 3800)),
                bedrooms=random.randint(2, 5),
                bathrooms=to_decimal(round(random.uniform(1.5, 3.5), 1)),
                lot_size=to_decimal(round(random.uniform(0.08, 0.4), 2)),
                assessed_value=to_decimal(round(sp["value"] * 0.85)),
                market_value=to_decimal(sp["value"]),
                tax_year=2024,
                latitude=to_coord(sp["lat"]),
                longitude=to_coord(sp["lon"]),
            )
            db.add(prop)
            properties.append(prop)
        db.flush()
        log.info(f"  Created {len(properties)} properties.")

        log.info("Seeding sales...")
        sale_count = 0
        for prop in properties:
            mv = float(prop.market_value)
            sqft = float(prop.square_footage) if prop.square_footage else None
            for i in range(random.randint(1, 3)):
                days_ago = random.randint(30, 365 * 8)
                sale_date_val = date.today() - timedelta(days=days_ago)
                sale_price_f = round(mv * random.uniform(0.6, 1.05))
                db.add(Sale(
                    property_id=prop.id,
                    sale_date=sale_date_val,
                    sale_price=to_decimal(sale_price_f),
                    price_per_sqft=to_decimal(sale_price_f / sqft) if sqft else None,
                    seller_name=random.choice(SAMPLE_NAMES),
                    buyer_name=random.choice(SAMPLE_NAMES),
                    deed_type=random.choice(["Warranty Deed", "Quitclaim Deed", "Trustee's Deed"]),
                    document_number=f"DOC-{random.randint(1000000, 9999999)}-{prop.id}-{i}",
                    source="Cook County Recorder",
                ))
                sale_count += 1
        log.info(f"  Created {sale_count} sales.")

        log.info("Seeding foreclosures...")
        for prop in random.sample(properties, k=8):
            days_ago = random.randint(15, 540)
            filing = date.today() - timedelta(days=days_ago)
            status = random.choice([
                ForeclosureStatus.lis_pendens, ForeclosureStatus.lis_pendens,
                ForeclosureStatus.judgment, ForeclosureStatus.auction_scheduled,
                ForeclosureStatus.sold_at_auction, ForeclosureStatus.reo,
            ])
            mv = float(prop.market_value)
            loan_amount = round(mv * random.uniform(0.75, 0.95))
            db.add(Foreclosure(
                property_id=prop.id,
                status=status,
                filing_date=filing,
                judgment_date=filing + timedelta(days=random.randint(90, 240)) if status != ForeclosureStatus.lis_pendens else None,
                auction_date=filing + timedelta(days=random.randint(240, 360)) if status in [ForeclosureStatus.auction_scheduled, ForeclosureStatus.sold_at_auction, ForeclosureStatus.reo] else None,
                plaintiff=random.choice(SAMPLE_BANKS),
                defendant=random.choice(SAMPLE_NAMES),
                case_number=f"{random.randint(2020, 2026)}-CH-{random.randint(10000, 99999)}",
                court="Cook County Circuit Court",
                original_loan_amount=to_decimal(loan_amount),
                judgment_amount=to_decimal(round(loan_amount * random.uniform(1.05, 1.18))) if status != ForeclosureStatus.lis_pendens else None,
                source="Cook County Circuit Court",
            ))
        log.info("  Created 8 foreclosures.")

        log.info("Seeding evictions...")
        for prop in random.sample(properties, k=10):
            days_ago = random.randint(10, 365)
            filing = date.today() - timedelta(days=days_ago)
            status = random.choice([
                EvictionStatus.filed, EvictionStatus.served,
                EvictionStatus.judgment_for_plaintiff, EvictionStatus.executed,
                EvictionStatus.dismissed,
            ])
            rent = random.randint(1100, 3200)
            db.add(Eviction(
                property_id=prop.id,
                status=status,
                filing_date=filing,
                hearing_date=filing + timedelta(days=random.randint(14, 30)),
                judgment_date=filing + timedelta(days=random.randint(30, 75)) if status in [EvictionStatus.judgment_for_plaintiff, EvictionStatus.executed] else None,
                execution_date=filing + timedelta(days=random.randint(75, 120)) if status == EvictionStatus.executed else None,
                plaintiff=random.choice(LANDLORDS),
                defendant=random.choice(SAMPLE_NAMES),
                case_number=f"{random.randint(2023, 2026)}-M1-{random.randint(700000, 799999)}",
                court="Cook County Circuit Court",
                eviction_reason=random.choice(EVICTION_REASONS),
                monthly_rent=to_decimal(rent),
                amount_owed=to_decimal(rent * random.randint(2, 6)),
                source="Cook County Circuit Court",
            ))
        log.info("  Created 10 evictions.")

        log.info("Seeding bank seizures...")
        for prop in random.sample(properties, k=6):
            days_ago = random.randint(30, 540)
            seizure = date.today() - timedelta(days=days_ago)
            stype = random.choice([SeizureType.tax_lien, SeizureType.tax_sale,
                                   SeizureType.reo, SeizureType.hud, SeizureType.county_owned])
            entity_map = {
                SeizureType.tax_lien: ("Cook County Treasurer", "county"),
                SeizureType.tax_sale: ("Cook County Treasurer", "county"),
                SeizureType.reo: (random.choice(SAMPLE_BANKS), "bank"),
                SeizureType.hud: ("U.S. Dept. of Housing and Urban Development", "federal"),
                SeizureType.county_owned: ("Cook County Land Bank Authority", "county"),
            }
            entity, etype = entity_map[stype]
            db.add(BankSeizure(
                property_id=prop.id,
                seizure_type=stype,
                seizure_date=seizure,
                seizing_entity=entity,
                seizing_entity_type=etype,
                tax_delinquency_amount=to_decimal(random.uniform(2500, 28000)) if stype in [SeizureType.tax_lien, SeizureType.tax_sale] else None,
                lien_amount=to_decimal(random.uniform(5000, 35000)) if stype in [SeizureType.tax_lien, SeizureType.tax_sale] else None,
                assessed_value_at_seizure=prop.assessed_value,
                document_number=f"DOC-{random.randint(1000000, 9999999)}",
                case_number=f"SEIZ-{prop.id}-{stype.value}",
                is_active=random.choice([True, True, True, False]),
                source=entity,
            ))
        log.info("  Created 6 bank seizures.")

        log.info("Seeding active listings with price drops...")
        listing_props = random.sample(properties, k=15)
        listing_count = 0
        for prop in listing_props:
            mv = float(prop.market_value)
            sqft = float(prop.square_footage) if prop.square_footage else None
            source = random.choice([ListingSource.redfin, ListingSource.realtor])
            list_days_ago = random.randint(30, 180)
            list_date = date.today() - timedelta(days=list_days_ago)
            original_f = round(mv * random.uniform(0.97, 1.18))
            current_f = original_f
            drops_count = random.randint(0, 4)
            total_drop_f = 0.0
            last_change_date = None

            listing = Listing(
                property_id=prop.id, source=source,
                source_listing_id=f"{source.value}-seed-{prop.id}",
                url=f"https://www.{source.value}.com/listing/{prop.id}",
                status=random.choice([ListingStatus.active, ListingStatus.active, ListingStatus.pending]),
                list_date=list_date,
                current_price=to_decimal(current_f),
                original_price=to_decimal(original_f),
                lowest_price=to_decimal(current_f),
                highest_price=to_decimal(original_f),
                days_on_market=list_days_ago,
                price_per_sqft=to_decimal(current_f / sqft) if sqft else None,
                photo_url=f"https://picsum.photos/seed/{prop.id}/400/300",
                is_active=True,
            )
            db.add(listing)
            db.flush()
            db.add(PriceHistory(listing_id=listing.id, change_date=list_date, price=to_decimal(original_f)))

            for i in range(drops_count):
                days_after = int(list_days_ago * (i + 1) / (drops_count + 1))
                if days_after < 1:
                    continue
                drop_pct_f = random.uniform(0.015, 0.06)
                delta_f = round(current_f * drop_pct_f)
                previous_f = current_f
                current_f -= delta_f
                total_drop_f += delta_f
                change_date = list_date + timedelta(days=days_after)
                last_change_date = change_date
                db.add(PriceHistory(
                    listing_id=listing.id, change_date=change_date,
                    price=to_decimal(current_f),
                    previous_price=to_decimal(previous_f),
                    change_amount=to_decimal(-delta_f),
                    change_percent=to_decimal(round(-drop_pct_f * 100, 2)),
                ))

            listing.current_price = to_decimal(current_f)
            listing.lowest_price = to_decimal(current_f)
            listing.price_drops_count = drops_count
            listing.total_price_drop_amount = to_decimal(total_drop_f)
            listing.total_price_drop_pct = to_decimal(round((original_f - current_f) / original_f * 100, 2)) if original_f else Decimal("0")
            listing.last_price_change_date = last_change_date
            listing_count += 1
        log.info(f"  Created {listing_count} listings.")

        db.commit()
        log.info("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
