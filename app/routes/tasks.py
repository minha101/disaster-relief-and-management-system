from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Task, TaskAssignment, District, User, Volunteer, RescueTeam
from ..services import audit
from .crud import scoped, get_cfg, need

bp = Blueprint('tasks', __name__, url_prefix='/tasks')
COLUMNS = [('todo', 'To do'), ('in_progress', 'In progress'), ('review', 'Review'), ('done', 'Done')]


@bp.route('/')
@login_required
def board():
    need('tasks', 'view')
    cfg = get_cfg('tasks')
    q = scoped(cfg, Task.query)
    if request.args.get('district', type=int):
        q = q.filter(Task.district_id == request.args.get('district', type=int))
    if request.args.get('priority') in ('low', 'medium', 'high', 'critical'):
        q = q.filter(Task.priority == request.args.get('priority'))
    if request.args.get('mine'):
        q = q.join(TaskAssignment, TaskAssignment.task_id == Task.id).filter(TaskAssignment.user_id == current_user.id)
    tasks = q.order_by(Task.sort_order, Task.id).limit(400).all()
    ids = [t.id for t in tasks]
    names = {}
    if ids:
        for a in TaskAssignment.query.filter(TaskAssignment.task_id.in_(ids)).all():
            who = (db.session.get(User, a.user_id).full_name if a.user_id else
                   a.volunteer.full_name if a.volunteer else a.team.name if a.team else None)
            if who:
                names.setdefault(a.task_id, []).append(who)
    cols = {k: [t for t in tasks if t.status == k] for k, _ in COLUMNS}
    return render_template('pages/tasks.html', columns=COLUMNS, cols=cols, names=names, today=datetime.utcnow().date(),
                           districts=District.query.order_by(District.name).all(),
                           can_edit=current_user.can('tasks', 'edit'), can_create=current_user.can('tasks', 'create'),
                           args=request.args)


@bp.post('/move')
@login_required
def move():
    need('tasks', 'edit')
    cfg = get_cfg('tasks')
    data = request.get_json(silent=True) or {}
    status = data.get('status')
    order = data.get('order') or []
    if status not in dict(COLUMNS) or not isinstance(order, list) or len(order) > 400:
        abort(400)
    ids = [int(i) for i in order if str(i).isdigit()]
    tasks = {t.id: t for t in scoped(cfg, Task.query.filter(Task.id.in_(ids))).all()}
    for pos, tid in enumerate(ids):
        t = tasks.get(tid)
        if not t:
            continue
        if t.status != status:
            audit.log('task_move', 'tasks', t.id, f'{t.status} -> {status}', commit=False)
            t.status = status
            t.completed_at = datetime.utcnow() if status == 'done' else None
        t.sort_order = pos
    db.session.commit()
    return jsonify(ok=True)


@bp.post('/quick')
@login_required
def quick():
    need('tasks', 'create')
    title = (request.form.get('title') or '').strip()[:200]
    prio = request.form.get('priority', 'medium')
    if not title or prio not in ('low', 'medium', 'high', 'critical'):
        return jsonify(ok=False, error='Title and valid priority required'), 400
    top = db.session.query(db.func.coalesce(db.func.max(Task.sort_order), 0)).scalar() or 0
    t = Task(title=title, priority=prio, status='todo', sort_order=top + 1, created_by_id=current_user.id, data_source='reported')
    db.session.add(t)
    db.session.flush()
    audit.log('create', 'tasks', t.id, title, commit=False)
    db.session.commit()
    return jsonify(ok=True, id=t.id)
