"""Loads FICTIONAL demonstration data (every row is flagged data_source='sample').

Usage (Windows CMD):  python seed.py            -> add sample data to an empty database
                      python seed.py --reset    -> DROP all tables, recreate, then seed (development only)
Demo passwords are random per run (or DEMO_USER_PASSWORD from .env) and printed once; never hardcoded.
"""
import os
import random
import secrets
import sys
from datetime import datetime, timedelta, date

from app import create_app
from app.extensions import db
from app.models import *
from app.services import rbac, settings, stock, hooks, risk

R = random.Random(2026)
NOW = datetime.utcnow()
MALE = 'Ahmed Ali Bilal Hamza Imran Kamran Usman Zubair Faisal Tariq Naveed Shahid Asif Rashid Nadeem Waqas'.split()
FEMALE = 'Ayesha Fatima Sana Hina Mariam Nadia Saima Rabia Zainab Amna Sadia Uzma'.split()
SUR = 'Khan Malik Baloch Chandio Soomro Qureshi Bhatti Jatoi Mirani Abbasi Yousafzai Rind Lashari Memon Shah Ansari'.split()

# (province, district, approx. centroid lat, lng) - coordinates are approximate, for map demonstration only
DISTRICTS = [
    ('Punjab', 'Lahore', 31.52, 74.36), ('Punjab', 'Multan', 30.20, 71.47), ('Punjab', 'Rajanpur', 29.10, 70.33),
    ('Punjab', 'Dera Ghazi Khan', 30.05, 70.64), ('Punjab', 'Muzaffargarh', 30.07, 71.19), ('Punjab', 'Layyah', 30.96, 70.94),
    ('Punjab', 'Bahawalpur', 29.40, 71.68), ('Punjab', 'Rahim Yar Khan', 28.42, 70.30), ('Punjab', 'Jhang', 31.27, 72.32),
    ('Punjab', 'Mianwali', 32.58, 71.54), ('Punjab', 'Sialkot', 32.49, 74.53), ('Punjab', 'Gujranwala', 32.16, 74.19),
    ('Sindh', 'Sukkur', 27.70, 68.86), ('Sindh', 'Larkana', 27.56, 68.21), ('Sindh', 'Jacobabad', 28.28, 68.44),
    ('Sindh', 'Kashmore', 28.43, 69.58), ('Sindh', 'Dadu', 26.73, 67.78), ('Sindh', 'Khairpur', 27.53, 68.76),
    ('Sindh', 'Hyderabad', 25.39, 68.37), ('Sindh', 'Thatta', 24.75, 67.92), ('Sindh', 'Sanghar', 26.05, 68.95),
    ('Sindh', 'Shikarpur', 27.96, 68.64), ('Sindh', 'Karachi', 24.86, 67.01),
    ('Khyber Pakhtunkhwa', 'Nowshera', 34.01, 71.98), ('Khyber Pakhtunkhwa', 'Charsadda', 34.15, 71.74),
    ('Khyber Pakhtunkhwa', 'Swat', 35.22, 72.43), ('Khyber Pakhtunkhwa', 'Dera Ismail Khan', 31.83, 70.90),
    ('Khyber Pakhtunkhwa', 'Peshawar', 34.01, 71.58), ('Khyber Pakhtunkhwa', 'Upper Dir', 35.21, 71.88),
    ('Balochistan', 'Jaffarabad', 28.45, 68.30), ('Balochistan', 'Nasirabad', 28.50, 68.43), ('Balochistan', 'Quetta', 30.18, 66.99),
    ('Balochistan', 'Lasbela', 26.23, 66.31), ('Gilgit-Baltistan', 'Gilgit', 35.92, 74.31), ('Gilgit-Baltistan', 'Ghizer', 36.00, 73.80),
    ('Azad Jammu & Kashmir', 'Muzaffarabad', 34.37, 73.47)]
HOT = {'Rajanpur', 'Dera Ghazi Khan', 'Muzaffargarh', 'Jacobabad', 'Kashmore', 'Dadu', 'Sukkur', 'Larkana', 'Nowshera',
       'Charsadda', 'Swat', 'Jaffarabad', 'Nasirabad', 'Khairpur', 'Shikarpur', 'Layyah', 'Rahim Yar Khan'}


def pname(female=None):
    f = R.choice(FEMALE if (female if female is not None else R.random() < .4) else MALE)
    return f'{f} {R.choice(SUR)}'


def phone():
    return f'03{R.randint(0, 4)}0-0000{R.randint(100, 999)}'      # clearly fictional pattern


def add(model, **kw):
    o = model(**kw)
    if hasattr(model, 'data_source') and 'data_source' not in kw:
        o.data_source = 'sample'
    db.session.add(o)
    return o


def ago(days_max, days_min=0):
    return NOW - timedelta(days=R.uniform(days_min, days_max), hours=R.uniform(0, 23))


def near(d, s=.25):
    return round(d.latitude + R.uniform(-s, s), 5), round(d.longitude + R.uniform(-s, s), 5)


def main():
    app = create_app()
    with app.app_context():
        if '--reset' in sys.argv:
            db.drop_all()
        db.create_all()
        rbac.sync_rbac()
        settings.ensure_defaults()
        if Incident.query.filter_by(data_source='sample').count():
            print('Sample data already present. Use  python seed.py --reset  to rebuild (this drops ALL data).')
            return
        roles = {r.code: r for r in Role.query.all()}

        # ---- geography
        provs = {}
        for n, c in (('Punjab', 'PB'), ('Sindh', 'SD'), ('Khyber Pakhtunkhwa', 'KP'), ('Balochistan', 'BA'),
                     ('Gilgit-Baltistan', 'GB'), ('Azad Jammu & Kashmir', 'AJK')):
            provs[n] = add(Province, name=n, code=c)
        db.session.flush()
        dist = {}
        for p, n, la, lo in DISTRICTS:
            dist[n] = add(District, province_id=provs[p].id, name=n, latitude=la, longitude=lo)
        db.session.flush()
        dlist = list(dist.values())
        for d in dlist:
            add(City, district_id=d.id, name=f'{d.name} City', latitude=d.latitude, longitude=d.longitude)
        villages = {}
        for d in dlist:
            villages[d.id] = []
            for k in range(3):
                la, lo = near(d, .3)
                villages[d.id].append(add(Village, district_id=d.id, name=f'Basti {R.choice(SUR)} ({k + 1})', latitude=la, longitude=lo))
        db.session.flush()

        # ---- reference data
        types = {}
        for n, c, fl, col in (('Riverine Flood', 'FLOOD', True, '#1d4ed8'), ('Flash Flood', 'FLASH', True, '#0ea5e9'),
                              ('Urban Flooding', 'URBAN', True, '#6366f1'), ('Cloudburst', 'CLOUD', False, '#64748b'),
                              ('Landslide', 'SLIDE', False, '#a16207'), ('Glacial Lake Outburst', 'GLOF', False, '#0891b2')):
            types[c] = add(DisasterType, name=n, code=c, is_flood=fl, color=col)
        cats = {n: add(RequestCategory, name=n, code=n[:4].upper(), priority_weight=w) for n, w in
                (('Rescue / Evacuation', 3), ('Medical Emergency', 3), ('Food & Water', 1), ('Shelter', 1),
                 ('Missing Person', 2), ('Other', 0))}
        rcat = {k: add(ResourceCategory, name=n, kind=k) for k, n in
                (('food', 'Food'), ('water', 'Drinking Water'), ('medical', 'Medical Supplies'), ('shelter', 'Shelter & NFI'), ('hygiene', 'Hygiene'))}
        db.session.flush()
        res = {}
        for name, k, unit in (('Family Ration Pack', 'food', 'pack'), ('Drinking Water', 'water', 'litre'),
                              ('Water Purification Tablets', 'water', 'pack'), ('Family Medicine Kit', 'medical', 'kit'),
                              ('First Aid Kit', 'medical', 'kit'), ('Tent (family)', 'shelter', 'piece'),
                              ('Blanket', 'shelter', 'piece'), ('Mosquito Net', 'shelter', 'piece'),
                              ('Life Jacket', 'shelter', 'piece'), ('Hygiene Kit', 'hygiene', 'kit'),
                              ('Tarpaulin Sheet', 'shelter', 'piece'), ('Infant Formula', 'food', 'pack')):
            res[name] = add(Resource, name=name, category_id=rcat[k].id, unit=unit, sku=f'SKU-{len(res) + 1:03d}', perishable=k in ('food',))
        db.session.flush()

        # ---- organisations & users
        orgs = []
        pre = 'Rah-e-Nijat Khidmat Umeed Hamdard Sahara Khalq Insaaniyat Noor Aman Mehrbani Taawun Dastak'.split()
        suf = ['Welfare Trust', 'Foundation', 'Relief Society', 'Rescue Services', 'Health Network', 'Community Forum']
        for i in range(50):
            d = R.choice(dlist)
            orgs.append(add(Organization, name=f'{R.choice(pre)} {R.choice(suf)} #{i + 1} (Sample)',
                            org_type=R.choice(['ngo', 'ngo', 'ngo', 'community', 'private', 'international_ngo']),
                            registration_no=f'SAMPLE-{1000 + i}', email=f'info@org{i + 1}.example', phone=phone(),
                            district_id=d.id, address=f'{d.name} (fictional address)', is_verified=False))
        gov = add(Organization, name='Provincial Disaster Management Authority (Sample)', org_type='government',
                  email='ops@pdma-sample.example', phone=phone())
        db.session.flush()
        for o in orgs[:20]:
            dep = add(Department, organization_id=o.id, name=R.choice(['Operations', 'Logistics', 'Medical', 'Fundraising']), head_name=pname())
        db.session.flush()

        pw = os.environ.get('DEMO_USER_PASSWORD') or (secrets.token_urlsafe(8) + 'Aa7')
        demo = [('admin1', 'Admin', 'admin', gov), ('admin2', 'Admin', 'admin', gov), ('dma1', 'DMA Manager', 'dma', gov),
                ('dma2', 'DMA Duty Officer', 'dma', gov), ('ngo1', 'NGO Manager', 'ngo', orgs[0]),
                ('rescue1', 'Rescue Team Lead', 'rescue_team', gov), ('rescue2', 'Rescue Team Lead', 'rescue_team', gov),
                ('volunteer1', 'Volunteer', 'volunteer', None), ('donor1', 'Donor', 'donor', None), ('affected1', 'Affected Person', 'affected', None)]
        lines, users = [], {}
        for key, title, role, org in demo:
            u = add(User, email=f'{key}@demo.example', full_name=f'{pname()} ({title})', phone=phone(), active=True,
                    organization_id=org.id if org else None, district_id=R.choice(dlist).id)
            u.set_password(pw)
            db.session.flush()
            db.session.add(UserRole(user_id=u.id, role_id=roles[role].id))
            users[key] = u
            lines.append(f'{u.email:28} {role}')
        admin_id = users['admin1'].id
        db.session.flush()

        def T(model, **kw):
            if hasattr(model, 'created_by_id'):
                kw.setdefault('created_by_id', admin_id)
            return add(model, **kw)

        # ---- disasters & incidents
        disasters = [T(Disaster, title=t, disaster_type_id=types[c].id, severity=s, status=st, start_date=(NOW - timedelta(days=dd)).date(),
                       estimated_affected=n, description='Fictional demonstration event.', official_reference='SAMPLE')
                     for t, c, s, st, dd, n in (('SAMPLE Monsoon Flood Event A', 'FLOOD', 'critical', 'active', 70, 250000),
                                                ('SAMPLE Flash Flood Event B', 'FLASH', 'high', 'recovering', 200, 60000),
                                                ('SAMPLE Urban Flooding Event C', 'URBAN', 'moderate', 'closed', 330, 15000),
                                                ('SAMPLE Landslide Event D', 'SLIDE', 'high', 'monitoring', 120, 8000))]
        db.session.flush()
        weights = [4 if d.name in HOT else 1 for d in dlist]
        incidents = []
        for i in range(100):
            d = R.choices(dlist, weights)[0]
            vil = R.choice(villages[d.id])
            la, lo = near(d, .3)
            loc = T(Location, name=f'Site near {vil.name}', location_type='point', district_id=d.id, latitude=la, longitude=lo)
            db.session.flush()
            age = R.uniform(0, 400)
            sev = R.choices(['low', 'moderate', 'high', 'critical'], [3, 5, 4, 2])[0]
            aff = int(R.lognormvariate(6.2, 1.1))
            typ = R.choices(['FLOOD', 'FLASH', 'URBAN', 'CLOUD', 'SLIDE'], [5, 3, 1, 1, 1])[0]
            status = 'resolved' if age > 150 else 'contained' if age > 90 else R.choice(['reported', 'active', 'active'])
            inc = T(Incident, title=f'{types[typ].name} - {vil.name}', disaster_id=R.choice(disasters).id, incident_type_id=types[typ].id,
                    district_id=d.id, village_id=vil.id, location_id=loc.id, latitude=la, longitude=lo, severity=sev, status=status,
                    reported_at=NOW - timedelta(days=age), affected_people=aff, people_rescued=int(aff * R.uniform(0, .85)),
                    injured=int(aff * R.uniform(0, .02)), fatalities=int(aff * R.uniform(0, .004)),
                    description='Fictional demonstration incident.')
            incidents.append(inc)
        db.session.flush()
        for v in R.sample([v for vs in villages.values() for v in vs], 40):
            T(AffectedArea, disaster_id=R.choice(disasters).id, district_id=v.district_id, village_id=v.id, population_affected=R.randint(200, 6000),
              households_affected=R.randint(30, 900), houses_damaged=R.randint(10, 500), status=R.choice(['assessing', 'affected', 'affected', 'recovering']),
              assessment_date=(NOW - timedelta(days=R.randint(1, 60))).date())
        for i in range(40):
            d = R.choice(dlist)
            la, lo = near(d)
            T(AffectedHousehold, head_name=pname(), phone=phone(), family_size=R.randint(2, 11), disaster_id=disasters[0].id, district_id=d.id,
              village_id=R.choice(villages[d.id]).id, status=R.choice(['affected', 'displaced', 'in_camp', 'rescued']), latitude=la, longitude=lo,
              needs=R.choice(['Food and clean water', 'Shelter / tents', 'Medicines', 'Evacuation support']))

        # ---- teams, vehicles, ambulances
        teams = []
        for i, nm in enumerate('Alpha Bravo Charlie Delta Echo Foxtrot Golf Hotel India Juliet'.split()):
            d = R.choice(dlist)
            la, lo = near(d, .1)
            moving = i < 7
            t = T(RescueTeam, name=f'Rescue Team {nm} (Sample)', code=f'RT-{i + 1:02d}', team_type=R.choice(['boat', 'medical', 'search_rescue', 'logistics', 'boat']),
                  organization_id=gov.id, district_id=d.id, lead_user_id=users['rescue1'].id if i == 0 else None, phone=phone(),
                  status=R.choice(['available', 'deployed', 'deployed', 'standby']) if i < 9 else 'offline', base_latitude=la, base_longitude=lo,
                  last_latitude=la + R.uniform(-.1, .1) if moving else None, last_longitude=lo + R.uniform(-.1, .1) if moving else None,
                  last_location_at=ago(1) if moving else None, equipment='Boats, life jackets, ropes, first-aid (fictional)')
            teams.append(t)
        db.session.flush()
        for t in teams:
            for k in range(R.randint(3, 5)):
                T(TeamMember, team_id=t.id, name=pname(), role=R.choice(['Boat operator', 'Paramedic', 'Diver', 'Driver', 'Coordinator']), phone=phone(), is_leader=k == 0)
        vehicles = [T(Vehicle, plate_no=f'SMP-{100 + i}', vehicle_type=R.choice(['truck', 'boat', 'pickup', 'van', 'tractor', 'bus']),
                      capacity=R.randint(4, 40), organization_id=gov.id, team_id=R.choice(teams).id, district_id=R.choice(dlist).id,
                      driver_name=pname(False), phone=phone(), status=R.choice(['available', 'in_use', 'maintenance'])) for i in range(15)]
        hospitals = []
        for i in range(12):
            d = R.choice(dlist)
            la, lo = near(d, .08)
            tb = R.randint(40, 400)
            hospitals.append(T(Hospital, name=f'{d.name} District Hospital (Sample {i + 1})', district_id=d.id, address='Fictional address', phone=phone(),
                               emergency_phone=phone(), latitude=la, longitude=lo, total_beds=tb, available_beds=int(tb * R.uniform(.05, .5)),
                               has_icu=R.random() < .6, has_trauma_unit=R.random() < .5, status=R.choice(['operational', 'operational', 'limited'])))
        db.session.flush()
        for i in range(8):
            h = R.choice(hospitals)
            T(Ambulance, plate_no=f'AMB-{200 + i}', hospital_id=h.id, district_id=h.district_id, driver_name=pname(False), phone=phone(),
              equipment_level=R.choice(['basic', 'advanced']), status=R.choice(['available', 'available', 'dispatched', 'maintenance']))

        # ---- relief camps
        camps = []
        for i in range(20):
            d = R.choices(dlist, weights)[0]
            la, lo = near(d, .15)
            cap = 60 if i < 2 else R.randint(70, 300)
            camps.append(T(ReliefCamp, name=f'{d.name} Relief Camp {i + 1} (Sample)', code=f'CMP-{i + 1:02d}', district_id=d.id,
                           village_id=R.choice(villages[d.id]).id, organization_id=R.choice(orgs).id, latitude=la, longitude=lo,
                           address='Fictional school ground', capacity=cap, status='open', manager_name=pname(), phone=phone(),
                           opened_on=(NOW - timedelta(days=R.randint(5, 80))).date()))
        db.session.flush()
        for c in camps:
            for ft in R.sample(['toilets', 'clean_water', 'kitchen', 'medical_post', 'electricity', 'women_space'], 4):
                T(CampFacility, camp_id=c.id, facility_type=ft, quantity=R.randint(1, 20), facility_condition=R.choice(['good', 'fair', 'poor']))
        for i in range(220):
            c = camps[i % 20] if i < 40 else R.choice(camps)
            T(CampResident, camp_id=c.id, full_name=pname(), persons=R.randint(2, 8), age=R.randint(1, 80), gender=R.choice(['male', 'female']),
              phone=phone(), check_in=(NOW - timedelta(days=R.randint(1, 60))).date(), status='resident' if R.random() < .93 else 'left')
        db.session.flush()
        for c in camps:
            stock.recompute_camp(c.id, snapshot=False)
            for w in range(6, 0, -1):
                T(CampCapacityHistory, camp_id=c.id, capacity=c.capacity, occupancy=max(0, int(c.current_occupancy * R.uniform(.5, 1.05) * (1 - w * .05))),
                  recorded_at=NOW - timedelta(weeks=w), created_at=NOW - timedelta(weeks=w), note='sample snapshot')
        db.session.flush()

        # ---- inventory & stock ledger (>= 100 transactions)
        wh = ['Provincial Warehouse - Multan (Sample)', 'Provincial Warehouse - Sukkur (Sample)', 'Provincial Warehouse - Peshawar (Sample)']
        big = {'pack': (3000, 9000), 'litre': (30000, 80000), 'kit': (300, 900), 'piece': (400, 2500)}
        whlines = []
        for w in wh:
            for r in res.values():
                inv = stock.get_inventory(r.id, None, w, create=True, user_id=admin_id, source='sample')
                inv.reorder_level = big[r.unit][0] * .2
                stock.apply_stock(inv, 'in', R.randint(*big[r.unit]), R.choice(['donation', 'purchase']), 'SAMPLE-WH', admin_id, 'sample', when=ago(60, 20))
                whlines.append(inv)
        for c in camps:
            occ = max(c.current_occupancy, 1)
            for rn, rate in (('Family Ration Pack', 1), ('Drinking Water', 3), ('Family Medicine Kit', .05)):
                if R.random() < .75:
                    days = R.choice([.2, .5, 1, 2, 4, 6])
                    inv = stock.get_inventory(res[rn].id, c.id, create=True, user_id=admin_id, source='sample')
                    inv.reorder_level = max(1, occ * rate)
                    stock.apply_stock(inv, 'in', max(1, int(occ * rate * days)), 'transfer', 'SAMPLE-IN', admin_id, 'sample', when=ago(20, 1))
        db.session.flush()
        while StockTransaction.query.count() < 100:
            inv = R.choice(whlines)
            stock.apply_stock(inv, 'in', R.randint(50, 400), R.choice(['donation', 'purchase']), 'SAMPLE-TOPUP', admin_id, 'sample', when=ago(15))
            db.session.flush()
        # distributions (reduce camp stock)
        for i in range(40):
            c = R.choice(camps)
            r = res[R.choice(['Family Ration Pack', 'Drinking Water', 'Family Medicine Kit'])]
            inv = stock.get_inventory(r.id, c.id)
            if inv and inv.quantity >= 2:
                q = float(int(inv.quantity * R.uniform(.05, .3)) or 1)
                stock.apply_stock(inv, 'out', q, 'distribution', f'SAMPLE-DIST-{i}', admin_id, 'sample', when=ago(10))
                T(DistributionRecord, camp_id=c.id, resource_id=r.id, quantity=q, beneficiaries=R.randint(20, 400),
                  distribution_date=(NOW - timedelta(days=R.randint(0, 10))).date(), organization_id=R.choice(orgs).id, distributed_by=pname())
        reqs = [T(ResourceRequest, camp_id=R.choice(camps).id, resource_id=R.choice(list(res.values())).id, quantity_needed=R.randint(50, 800),
                  urgency=R.choice(['moderate', 'high', 'critical']), status=R.choice(['open', 'open', 'approved']),
                  needed_by=(NOW + timedelta(days=R.randint(1, 10))).date()) for _ in range(25)]
        db.session.flush()
        for i in range(10):
            rq = reqs[i]
            src = R.choice([l for l in whlines if l.resource_id == rq.resource_id])
            st = ['proposed', 'approved', 'dispatched', 'delivered', 'delivered', 'proposed', 'approved', 'cancelled', 'proposed', 'delivered'][i]
            a = T(ResourceAllocation, request_id=rq.id, resource_id=rq.resource_id, source_inventory_id=src.id, camp_id=rq.camp_id,
                  quantity=min(rq.quantity_needed, 100), status=st, notes='sample allocation')
            db.session.flush()
            if st == 'delivered':
                dest = stock.get_inventory(rq.resource_id, rq.camp_id, create=True, user_id=admin_id, source='sample')
                stock.apply_stock(src, 'out', a.quantity, 'transfer', f'ALLOC-{a.id}', admin_id, 'sample')
                stock.apply_stock(dest, 'in', a.quantity, 'transfer', f'ALLOC-{a.id}', admin_id, 'sample')
                a.applied = True
                rq.status = 'fulfilled' if a.quantity >= rq.quantity_needed else 'partially_fulfilled'
        db.session.flush()

        # ---- SOS requests, operations
        sos = []
        for i in range(100):
            inc = R.choice(incidents)
            la, lo = inc.latitude + R.uniform(-.05, .05), inc.longitude + R.uniform(-.05, .05)
            st = R.choices(['pending', 'acknowledged', 'assigned', 'in_progress', 'rescued', 'resolved', 'cancelled', 'false_alarm'], [25, 8, 10, 10, 20, 20, 4, 3])[0]
            created = ago(60)
            inj = R.random() < .2
            cat = R.choice(list(cats.values()))
            e = T(EmergencyRequest, tracking_code=hooks.new_tracking_code(), category_id=cat.id, requester_name=pname(), phone=phone(),
                  people_count=R.randint(1, 25), has_injured=inj, needs_medical=inj or R.random() < .15, district_id=inc.district_id, address='Near fictional village',
                  latitude=round(la, 5), longitude=round(lo, 5), description='Fictional demonstration SOS request.', status=st, created_at=created,
                  incident_id=inc.id, assigned_team_id=R.choice(teams).id if st in ('assigned', 'in_progress', 'rescued') else None,
                  resolved_at=created + timedelta(hours=R.randint(2, 48)) if st in ('rescued', 'resolved', 'cancelled', 'false_alarm') else None)
            e.priority = hooks.auto_priority(e)
            sos.append(e)
        db.session.flush()
        for e in sos:
            db.session.add(RequestUpdate(request_id=e.id, status='pending', note='Request received', created_at=e.created_at))
            if e.status != 'pending':
                db.session.add(RequestUpdate(request_id=e.id, status=e.status, note=f'Status changed to {e.status}', created_at=e.created_at + timedelta(hours=1), updated_by_id=admin_id))
        ops = []
        for i in range(12):
            inc = R.choice(incidents)
            st = R.choice(['planned', 'active', 'active', 'completed', 'paused'])
            ops.append(T(RescueOperation, name=f'Operation {inc.title[:60]}', disaster_id=inc.disaster_id, incident_id=inc.id, district_id=inc.district_id,
                         commander_user_id=users['rescue1'].id, status=st, priority=R.choice(['high', 'critical', 'moderate']),
                         started_at=ago(30) if st != 'planned' else None, ended_at=ago(3) if st == 'completed' else None,
                         people_targeted=R.randint(50, 1500), description='Fictional demonstration operation.'))
        db.session.flush()
        for i in range(25):
            op = ops[i % 12]
            n = R.randint(0, 120) if op.status != 'planned' else 0
            T(RescueAssignment, operation_id=op.id, team_id=R.choice(teams).id, request_id=R.choice(sos).id if R.random() < .5 else None,
              vehicle_id=R.choice(vehicles).id, status='completed' if op.status == 'completed' else R.choice(['assigned', 'en_route', 'on_site']),
              people_rescued=n, notes='sample')
            op.people_rescued += n
        for i in range(5):
            d = R.choice(dlist)
            plan = T(EvacuationPlan, title=f'Evacuation plan - {d.name} riverside villages', disaster_id=disasters[0].id, district_id=d.id, destination_camp_id=R.choice(camps).id,
                     status=R.choice(['draft', 'approved', 'active', 'completed']), trigger_condition='When authority declares high flood level (sample rule)',
                     people_to_evacuate=R.randint(500, 5000), people_evacuated=R.randint(0, 400), description='Fictional plan.')
            db.session.flush()
            for k in range(2 if i < 3 else 1):
                la, lo = near(d, .2)
                T(EvacuationRoute, plan_id=plan.id, name=f'Route {k + 1} to camp', start_latitude=la, start_longitude=lo, end_latitude=la + R.uniform(-.1, .1),
                  end_longitude=lo + R.uniform(-.1, .1), distance_km=round(R.uniform(4, 35), 1), estimated_minutes=R.randint(15, 120), status=R.choice(['open', 'open', 'blocked', 'flooded']))

        # ---- funding
        donors = [T(Donor, name=pname() if i % 3 else f'{R.choice(pre)} Traders (Sample)', donor_type='individual' if i % 3 else 'corporate', email=f'donor{i + 1}@sample.example',
                    phone=phone(), is_anonymous=i % 7 == 0) for i in range(30)]
        camps_f = [T(DonationCampaign, title=t, disaster_id=disasters[0].id, organization_id=R.choice(orgs).id, goal_amount=g, status='active',
                     start_date=(NOW - timedelta(days=50)).date(), description='Fictional campaign.')
                   for t, g in (('SAMPLE Food & Water Appeal', 5000000), ('SAMPLE Shelter Appeal', 8000000), ('SAMPLE Medical Aid Appeal', 3000000), ('SAMPLE Rebuilding Fund', 12000000))]
        db.session.flush()
        for i in range(50):
            cash = i < 45
            amt = R.choice([2000, 5000, 10000, 25000, 50000, 100000, 250000]) if cash else 0
            d = T(Donation, donor_id=R.choice(donors).id, campaign_id=R.choice(camps_f).id, donation_type='cash' if cash else 'in_kind', amount=amt,
                  resource_id=None if cash else res['Blanket'].id, quantity=None if cash else R.randint(50, 500), status='received' if i % 9 else 'pledged',
                  donated_on=(NOW - timedelta(days=R.randint(0, 50))).date())
            db.session.flush()
            if cash:
                T(DonationTransaction, donation_id=d.id, amount=amt, method=R.choice(['bank_transfer', 'mobile_wallet', 'online', 'cheque']), reference_no=f'SMP-{i + 1000}',
                  receipt_no=f'RCPT-{i + 1}', status='completed' if d.status == 'received' else 'pending', transaction_date=ago(50))

        # ---- volunteers, tasks
        vols = [T(Volunteer, full_name=pname(), phone=phone(), email=f'vol{i + 1}@sample.example', gender=R.choice(['male', 'female']), age=R.randint(19, 55),
                  district_id=R.choice(dlist).id, organization_id=R.choice(orgs).id, availability=R.choice(['available', 'available', 'busy']),
                  status='approved' if i % 6 else 'pending', has_vehicle=R.random() < .3, languages='Urdu, Punjabi', experience='Fictional volunteer profile.') for i in range(30)]
        db.session.flush()
        for v in vols:
            for sk in R.sample(['first_aid', 'boat_operation', 'swimming', 'driving', 'cooking', 'logistics', 'counselling', 'translation'], 2):
                add(VolunteerSkill, volunteer_id=v.id, skill=sk, level=R.choice(['basic', 'intermediate', 'expert']), certified=R.random() < .3)
        tasks = []
        for i, t in enumerate(['Distribute ration packs', 'Set up water point', 'Register new camp arrivals', 'Deliver medicines to camp', 'Clear drainage at camp',
                               'Boat patrol riverside', 'Survey damaged houses', 'Set up medical post', 'Collect donated blankets', 'Update stock register', 'Escort evacuation convoy',
                               'Install tents', 'Spray mosquito control', 'Child-friendly space setup', 'Fuel generators', 'Verify SOS requests',
                               'Prepare hygiene kits', 'Train volunteers (first aid)', 'Repair access road marker', 'Update camp register', 'Arrange transport', 'Check food quality', 'Report water levels (official source)', 'Debrief teams']):
            d = R.choice(dlist)
            tasks.append(T(Task, title=t, description='Fictional task.', status=['todo', 'in_progress', 'review', 'done'][i % 4], priority=R.choice(['low', 'medium', 'high', 'critical']),
                           due_date=(NOW + timedelta(days=R.randint(-3, 10))).date(), district_id=d.id, camp_id=R.choice(camps).id, sort_order=i))
        db.session.flush()
        for t in tasks[:20]:
            add(TaskAssignment, task_id=t.id, volunteer_id=R.choice(vols).id) if R.random() < .6 else add(TaskAssignment, task_id=t.id, team_id=R.choice(teams).id)
            T(VolunteerAssignment, volunteer_id=R.choice(vols).id, task_id=t.id, camp_id=t.camp_id, role='Field support', status=R.choice(['assigned', 'active', 'completed']),
              start_date=(NOW - timedelta(days=R.randint(0, 10))).date(), hours_logged=R.randint(0, 40))
        for t in tasks[:15]:
            T(TaskComment, task_id=t.id, body='Fictional comment: please confirm quantities before dispatch.')

        # ---- medical, alerts, comms
        for i in range(10):
            d = R.choice(dlist)
            la, lo = near(d, .1)
            T(MedicalFacility, name=f'{d.name} Field Clinic {i + 1} (Sample)', facility_type=R.choice(['mobile_clinic', 'field_hospital', 'dispensary', 'bhu']),
              hospital_id=R.choice(hospitals).id, camp_id=R.choice(camps).id, district_id=d.id, latitude=la, longitude=lo, phone=phone(), staff_count=R.randint(2, 15), status='operational')
        for i in range(20):
            T(MedicalAssistance, camp_id=R.choice(camps).id, hospital_id=R.choice(hospitals).id, patient_name=pname(), age=R.randint(1, 80),
              medical_condition=R.choice(['Diarrhoea', 'Skin infection', 'Fever', 'Minor injury', 'Respiratory infection']), treatment='Basic treatment (fictional)',
              severity=R.choice(['low', 'moderate', 'high']), status=R.choice(['registered', 'under_treatment', 'recovered', 'referred']))
        for i in range(8):
            d = R.choice(dlist)
            T(WeatherAlert, title=f'Heavy rain advisory - {d.name} (sample)', district_id=d.id, alert_type=R.choice(['heavy_rain', 'storm', 'cloudburst']),
              severity=R.choice(['moderate', 'high', 'critical']), source_name='SAMPLE - fictional bulletin', issued_at=ago(5), valid_until=NOW + timedelta(days=R.randint(1, 4)), is_active=i < 5,
              message='Fictional alert for demonstration; not an official forecast.')
        for i in range(10):
            d = R.choice(dlist)
            T(FloodAlert, title=f'River level alert - {d.name} (sample)', district_id=d.id, river=R.choice(['Indus', 'Chenab', 'Jhelum', 'Sutlej', 'Kabul']), station='Sample station',
              flood_level=R.choice(['low', 'medium', 'high', 'very_high']), source_name='SAMPLE - fictional bulletin', issued_at=ago(4),
              valid_until=NOW + timedelta(days=R.randint(1, 3)), is_active=i < 6, message='Fictional alert for demonstration; not an official flood bulletin.')
        for i in range(15):
            T(Communication, channel=R.choice(['sms', 'call', 'radio', 'email']), direction=R.choice(['outbound', 'inbound']), subject=R.choice(['Team dispatch confirmation', 'Camp stock request', 'Evacuation notice relay']),
              message='Fictional log entry.', recipient_name=pname(), recipient_contact=phone(), status='logged', sent_at=ago(10))
        for i in range(8):
            T(Complaint, subject=R.choice(['Delay in ration delivery', 'Water point not working', 'Overcrowded tents']), category=R.choice(['aid_delay', 'camp_conditions', 'missing_supplies']),
              camp_id=R.choice(camps).id, description='Fictional complaint.', priority=R.choice(['low', 'medium', 'high']), status=R.choice(['open', 'under_review', 'resolved']))
        for i in range(10):
            T(Feedback, category=R.choice(['service', 'camp', 'distribution']), camp_id=R.choice(camps).id, rating=R.randint(2, 5), comment='Fictional feedback.')
        for n, ph, note in (('Rescue 1122 (Punjab/KP, where available)', '1122', 'Publicly known national/provincial number - confirm locally'), ('Edhi Ambulance', '115', 'Publicly known number - confirm locally'),
                            ('Police Emergency', '15', 'Publicly known number - confirm locally'), ('Fire Brigade', '16', 'Publicly known number - confirm locally')):
            add(EmergencyContact, name=n, category='rescue', phone=ph, is_national=True, notes=note, data_source='reported', created_by_id=admin_id)
        for i in range(8):
            d = R.choice(dlist)
            T(EmergencyContact, name=f'{d.name} District Control Room (Sample)', category='disaster_authority', phone=phone(), district_id=d.id, designation='Duty officer')
        for u in list(users.values())[:6]:
            add(OrganizationMember, organization_id=gov.id, user_id=u.id, position='Staff', joined_on=date.today())
        db.session.commit()

        risk.save_snapshot(risk.compute('all'), 'all', admin_id)
        creds = os.path.join(app.instance_path, 'demo_credentials.txt')
        os.makedirs(app.instance_path, exist_ok=True)
        with open(creds, 'w') as fh:
            fh.write('Demo accounts (password shared by all, generated for this run)\nPassword: ' + pw + '\n' + '\n'.join(lines) + '\n')
        print('\nSample data loaded (every row flagged "sample").')
        print('Tables:', len(db.metadata.tables), '| incidents:', Incident.query.count(), '| SOS:', EmergencyRequest.query.count(), '| camps:', ReliefCamp.query.count(),
              '| stock txns:', StockTransaction.query.count(), '| donations:', Donation.query.count(), '| orgs:', Organization.query.count())
        print('\nDemo logins (password printed once, also saved in instance/demo_credentials.txt):')
        print('  password:', pw)
        print('\n'.join('  ' + l for l in lines))
        print('\nCreate your Super Admin at http://127.0.0.1:5000/setup (or: flask create-admin).')


if __name__ == '__main__':
    main()
