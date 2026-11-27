from .base import *


class Donor(Tracked):
    __tablename__ = 'donors'
    __label__ = '{name}'
    user_id = FK('users')
    name = Str(150, nullable=False)
    donor_type = Ch(['individual', 'corporate', 'ngo', 'government', 'anonymous'])
    email = Str(150)
    phone = Str(30)
    country = Str(60, default='Pakistan')
    is_anonymous = Bool(False)


class DonationCampaign(Tracked):
    __tablename__ = 'donation_campaigns'
    __label__ = '{title}'
    title = Str(200, nullable=False)
    disaster_id = FK('disasters')
    organization_id = FK('organizations')
    goal_amount = Money(nullable=False)
    status = Ch(['draft', 'active', 'completed', 'closed'], 'active', index=True)
    start_date = Dat()
    end_date = Dat()
    description = Txt()


class Donation(Tracked):
    __tablename__ = 'donations'
    __label__ = 'donation {id}'
    __staff_only__ = ('status',)
    donor_id = FK('donors', False)
    campaign_id = FK('donation_campaigns')
    donation_type = Ch(['cash', 'in_kind'])
    amount = Money(default=0, nullable=False)
    currency = Str(3, default='PKR', nullable=False)
    resource_id = FK('resources')
    quantity = Flt()
    status = Ch(['pledged', 'received', 'allocated', 'rejected'], index=True)
    donated_on = Dat(default=today, nullable=False)
    message = Str(255)


class DonationTransaction(Tracked):
    __tablename__ = 'donation_transactions'
    __label__ = 'txn {id}'
    __staff_only__ = ('status',)
    donation_id = FK('donations', False)
    amount = Money(nullable=False)
    method = Ch(['bank_transfer', 'cheque', 'mobile_wallet', 'cash', 'online', 'in_kind'])
    reference_no = Str(60)
    receipt_no = Str(60)
    status = Ch(['pending', 'completed', 'failed', 'refunded'], index=True)
    transaction_date = Dt(default=now, nullable=False)
    donation = db.relationship('Donation', backref='transactions')


class Volunteer(Tracked):
    __tablename__ = 'volunteers'
    __label__ = '{full_name}'
    __staff_only__ = ('status',)
    user_id = FK('users')
    full_name = Str(120, nullable=False)
    phone = Str(30, nullable=False)
    email = Str(150)
    gender = Ch(['male', 'female', 'other'])
    age = Int()
    district_id = FK('districts')
    organization_id = FK('organizations')
    availability = Ch(['available', 'busy', 'inactive'], index=True)
    status = Ch(['pending', 'approved', 'suspended'], index=True)
    has_vehicle = Bool(False)
    languages = Str(120)
    experience = Txt()
    registered_on = Dat(default=today, nullable=False)


class VolunteerSkill(Base):
    __tablename__ = 'volunteer_skills'
    __label__ = '{skill}'
    volunteer_id = FK('volunteers', False)
    skill = Ch(['first_aid', 'boat_operation', 'swimming', 'driving', 'cooking', 'logistics', 'counselling',
                'translation', 'construction', 'communication'])
    level = Ch(['basic', 'intermediate', 'expert'])
    certified = Bool(False)
    volunteer = db.relationship('Volunteer', backref=db.backref('skills', cascade='all, delete-orphan'))


class Task(Tracked):
    __tablename__ = 'tasks'
    __label__ = '{title}'
    __hidden__ = ('sort_order', 'completed_at')
    title = Str(200, nullable=False)
    description = Txt()
    status = Ch(['todo', 'in_progress', 'review', 'done'], index=True)
    priority = Ch(PRIO, 'medium')
    due_date = Dat()
    district_id = FK('districts')
    camp_id = FK('relief_camps')
    incident_id = FK('incidents')
    sort_order = Int(default=0, nullable=False)
    completed_at = Dt()


class VolunteerAssignment(Tracked):
    __tablename__ = 'volunteer_assignments'
    __label__ = 'assignment {id}'
    volunteer_id = FK('volunteers', False)
    task_id = FK('tasks')
    camp_id = FK('relief_camps')
    operation_id = FK('rescue_operations')
    role = Str(100)
    status = Ch(['assigned', 'active', 'completed', 'withdrawn'], index=True)
    start_date = Dat()
    end_date = Dat()
    hours_logged = Flt(default=0, nullable=False)


class TaskAssignment(Base):
    __tablename__ = 'task_assignments'
    __label__ = 'assignment {id}'
    task_id = FK('tasks', False)
    user_id = FK('users')
    volunteer_id = FK('volunteers')
    team_id = FK('rescue_teams')
    assigned_at = Dt(default=now, nullable=False)
    note = Str(255)
    task = db.relationship('Task', backref=db.backref('assignments', cascade='all, delete-orphan'))
    volunteer = db.relationship('Volunteer')
    team = db.relationship('RescueTeam')


class TaskComment(Tracked):
    __tablename__ = 'task_comments'
    __label__ = 'comment {id}'
    task_id = FK('tasks', False)
    body = Txt(nullable=False)
    task = db.relationship('Task', backref=db.backref('comments', cascade='all, delete-orphan'))
