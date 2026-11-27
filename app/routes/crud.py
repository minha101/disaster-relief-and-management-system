import csv
import io
import json
from datetime import datetime, date
from decimal import Decimal
from flask import (Blueprint, render_template, request, redirect, url_for, flash, abort, Response, jsonify)
from flask_login import login_required, current_user
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..registry import REGISTRY
from ..models import Attachment, IncidentImage, Report
from ..services import audit, hooks, uploads, pdfgen
from ..services.formgen import (form_columns, field_meta, apply_form, coerce, fk_target, choices_of, label_of,
                                to_input, default_of, label_query, fk_options, EXCLUDE)

bp = Blueprint('crud', __name__, url_prefix='/m')
NO_IMPORT = {'users', 'roles', 'permissions', 'user_roles', 'role_permissions'}


# ------------------------------------------------------------------ helpers
def get_cfg(slug):
    cfg = REGISTRY.get(slug)
    if not cfg:
        abort(404)
    return cfg


def need(slug, action):
    if not current_user.can(slug, action):
        abort(403)


def is_tracked(model):
    return hasattr(model, 'created_by_id')


def own_only(cfg):
    return not current_user.can(cfg['slug'], 'all')


def scoped(cfg, q):
    if own_only(cfg):
        m = cfg['model']
        q = q.filter(m.created_by_id == current_user.id) if is_tracked(m) else q.filter(db.false())
    return q


def load(cfg, id):
    obj = cfg['model'].query.get_or_404(id)
    if own_only(cfg) and not (is_tracked(cfg['model']) and obj.created_by_id == current_user.id):
        abort(404)
    return obj


def mutable(cfg, what='edit'):
    if cfg['readonly'] or (cfg['immutable'] and what in ('edit', 'delete')):
        abort(403)


def safe_next(default):
    nxt = request.values.get('next') or ''
    return nxt if nxt.startswith('/') and not nxt.startswith('//') and '\\' not in nxt else default


BADGE = {'critical': 'danger', 'very_high': 'danger', 'exceptional': 'danger', 'pending': 'danger', 'open': 'danger',
         'false_alarm': 'secondary', 'high': 'warning', 'acknowledged': 'warning', 'under_review': 'warning',
         'proposed': 'warning', 'blocked': 'danger', 'flooded': 'danger', 'poor': 'warning', 'failed': 'danger',
         'moderate': 'info', 'medium': 'info', 'in_progress': 'primary', 'assigned': 'primary', 'active': 'primary',
         'deployed': 'primary', 'dispatched': 'primary', 'en_route': 'primary', 'on_site': 'primary',
         'resolved': 'success', 'completed': 'success', 'rescued': 'success', 'delivered': 'success',
         'verified': 'success', 'approved': 'success', 'available': 'success', 'operational': 'success',
         'fulfilled': 'success', 'received': 'success', 'done': 'success', 'good': 'success', 'recovered': 'success',
         'sample': 'secondary', 'reported': 'info', 'closed': 'secondary', 'cancelled': 'secondary', 'low': 'secondary',
         'offline': 'secondary', 'draft': 'secondary', 'rejected': 'secondary', 'in': 'success', 'out': 'warning'}


def fmt(col, v):
    if v is None:
        return ''
    t = col.type
    if isinstance(t, db.Boolean):
        return 'Yes' if v else 'No'
    if isinstance(t, db.DateTime):
        return v.strftime('%d %b %Y %H:%M')
    if isinstance(t, db.Date):
        return v.strftime('%d %b %Y')
    if isinstance(t, (db.Float, db.Numeric)):
        return f'{float(v):,.2f}'.rstrip('0').rstrip('.')
    if isinstance(t, db.Integer) and not col.foreign_keys and col.name not in ('id', 'entity_id'):
        return f'{v:,}'
    s = str(v)
    return s if len(s) <= 70 else s[:67] + '...'


def fk_maps(model, cols, objs):
    maps = {}
    for name in cols:
        col = model.__table__.columns.get(name)
        t = fk_target(col) if col is not None else None
        if t:
            ids = {getattr(o, name) for o in objs if getattr(o, name) is not None}
            maps[name] = {x.id: x.label for x in label_query(t).filter(t.id.in_(ids)).all()} if ids else {}
    return maps


def table_data(cfg, objs, cols=None):
    model = cfg['model']
    cols = cols or cfg['cols']
    maps = fk_maps(model, cols, objs)
    headers = [(c, label_of(model.__table__.columns[c]) if c in model.__table__.columns else c) for c in cols]
    rows = []
    for o in objs:
        cells = []
        for c in cols:
            col = model.__table__.columns[c]
            v = getattr(o, c)
            cell = dict(kind='text', text=fmt(col, v), url=None, cls=None)
            if c in maps:
                t = fk_target(col)
                cell['text'] = maps[c].get(v, '') if v is not None else ''
                if v is not None and current_user.can(t.__slug__, 'view'):
                    cell['url'] = url_for('crud.detail', slug=t.__slug__, id=v)
            elif isinstance(col.type, db.Boolean):
                cell.update(kind='badge', cls='success' if v else 'secondary')
            elif choices_of(col) and v:
                cell.update(kind='badge', text=str(v).replace('_', ' '), cls=BADGE.get(v, 'light text-dark border'))
            cells.append(cell)
        rows.append(dict(obj=o, cells=cells))
    return dict(headers=headers, rows=rows)


def filter_defs(cfg):
    model = cfg['model']
    names = list(cfg['filters']) + (['data_source'] if is_tracked(model) else [])
    out = []
    for n in names:
        col = model.__table__.columns.get(n)
        if col is None:
            continue
        if fk_target(col):
            opts = fk_options(col, 500)
        elif choices_of(col):
            opts = [(c, c.replace('_', ' ').title()) for c in choices_of(col)]
        elif isinstance(col.type, db.Boolean):
            opts = [('1', 'Yes'), ('0', 'No')]
        else:
            continue
        out.append(dict(name=n, label=label_of(col), options=opts))
    return out


def build_query(cfg):
    model = cfg['model']
    q = scoped(cfg, model.query)
    term = (request.args.get('q') or '').strip()
    if term and cfg['search']:
        q = q.filter(or_(*[getattr(model, c).ilike(f'%{term}%') for c in cfg['search']]))
    active = {}
    for f in filter_defs(cfg):
        v = request.args.get(f['name'])
        if v in (None, ''):
            continue
        col = getattr(model, f['name'])
        ctype = model.__table__.columns[f['name']].type
        try:
            v2 = (v in ('1', 'true')) if isinstance(ctype, db.Boolean) else int(v) if isinstance(ctype, db.Integer) else v
        except ValueError:
            continue
        q = q.filter(col == v2)
        active[f['name']] = v
    for key, op in (('from', '>='), ('to', '<=')):
        raw = request.args.get(key)
        if raw:
            try:
                d = datetime.fromisoformat(raw)
                q = q.filter(model.created_at >= d) if op == '>=' else q.filter(model.created_at < d.replace(hour=23, minute=59, second=59))
                active[key] = raw
            except ValueError:
                pass
    sort = request.args.get('sort')
    direction = request.args.get('dir', 'desc')
    if isinstance(sort, str) and sort in model.__table__.columns.keys():
        c = getattr(model, sort)
        q = q.order_by(c.asc() if direction == 'asc' else c.desc())
    else:
        q = q.order_by(model.id.desc())
    return q, active, term


# ------------------------------------------------------------------ list / export
@bp.route('/<slug>/')
@login_required
def index(slug):
    cfg = get_cfg(slug)
    need(slug, 'view')
    q, active, term = build_query(cfg)
    per_page = min(request.args.get('per_page', 15, type=int), 100)
    p = q.paginate(page=request.args.get('page', 1, type=int), per_page=per_page, error_out=False)
    args = {k: v for k, v in request.args.items() if k != 'page'}
    return render_template('crud/list.html', cfg=cfg, p=p, td=table_data(cfg, p.items), filters=filter_defs(cfg),
                           active=active, term=term, args=args, sort=request.args.get('sort'),
                           direction=request.args.get('dir', 'desc'), can_import=slug not in NO_IMPORT and not cfg['readonly'])


@bp.route('/<slug>/export.csv')
@login_required
def export_csv(slug):
    cfg = get_cfg(slug)
    need(slug, 'view')
    q, _, _ = build_query(cfg)
    cols = [c for c in cfg['model'].__table__.columns if c.name != 'password_hash']
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([c.name for c in cols])
    for o in q.limit(50000).all():
        row = []
        for c in cols:
            v = getattr(o, c.name)
            v = '' if v is None else v.isoformat() if isinstance(v, (date, datetime)) else v
            if isinstance(v, str) and v[:1] in ('=', '+', '-', '@', '\t', '\r'):
                v = "'" + v                      # neutralise spreadsheet formula injection
            row.append(v)
        w.writerow(row)
    audit.log('export_csv', slug)
    return Response('\ufeff' + buf.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename={slug}_{date.today():%Y%m%d}.csv'})


@bp.route('/<slug>/export.pdf')
@login_required
def export_pdf(slug):
    cfg = get_cfg(slug)
    need(slug, 'view')
    q, _, _ = build_query(cfg)
    objs = q.limit(500).all()
    td = table_data(cfg, objs)
    rows = [[c['text'] for c in r['cells']] for r in td['rows']]
    pdf = pdfgen.build_pdf(cfg['title'], [(f'{cfg["title"]} ({len(rows)} rows, max 500)', [h[1] for h in td['headers']], rows)],
                           pdfgen.meta(current_user, 'as filtered on screen (includes sample data where flagged)'))
    db.session.add(Report(title=cfg['title'], report_type='module_export', data_scope='filtered', created_by_id=current_user.id,
                          parameters=json.dumps(dict(request.args)), file_name=f'{slug}.pdf'))
    audit.log('export_pdf', slug, commit=False)
    db.session.commit()
    return Response(pdf, mimetype='application/pdf', headers={'Content-Disposition': f'inline; filename={slug}.pdf'})


@bp.route('/<slug>/template.csv')
@login_required
def template_csv(slug):
    cfg = get_cfg(slug)
    need(slug, 'create')
    return Response(','.join(c.name for c in form_columns(cfg, current_user)) + '\n', mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename={slug}_template.csv'})


@bp.route('/<slug>/import', methods=['GET', 'POST'])
@login_required
def import_csv(slug):
    cfg = get_cfg(slug)
    need(slug, 'create')
    if slug in NO_IMPORT or cfg['readonly']:
        abort(403)
    report = None
    if request.method == 'POST':
        f = request.files.get('file')
        if not f or not f.filename.lower().endswith('.csv'):
            flash('Choose a .csv file.', 'danger')
        else:
            cols = {c.name: c for c in form_columns(cfg, current_user)}
            reader = csv.DictReader(io.StringIO(f.read().decode('utf-8-sig', errors='replace')))
            ok, errors = 0, []
            for i, row in enumerate(reader, start=2):
                if i > 2001:
                    errors.append('Row limit (2000) reached; remaining rows ignored.')
                    break
                obj = cfg['model']()
                row = {k.strip(): v for k, v in row.items() if k}
                row_errs = []
                for name, col in cols.items():
                    if name not in row:
                        continue
                    val, err = coerce(col, row[name])
                    if err:
                        row_errs.append(f'{name}: {err}')
                    elif val is None and (col.nullable or col.default is not None):
                        continue
                    elif val is None:
                        row_errs.append(f'{name}: required')
                    else:
                        setattr(obj, name, val)
                missing = [n for n, c in cols.items() if n not in row and not c.nullable and c.default is None]
                if missing:
                    row_errs.append('missing columns: ' + ', '.join(missing))
                ctx = dict(user=current_user, data=row, old=None)
                try:
                    if is_tracked(cfg['model']):
                        obj.created_by_id, obj.data_source = current_user.id, 'reported'
                    if not row_errs:
                        msg = hooks.before_save(slug, obj, True, ctx)
                        if msg:
                            row_errs.append(msg)
                    if row_errs:
                        raise ValueError('; '.join(row_errs))
                    db.session.add(obj)
                    db.session.flush()
                    hooks.after_save(slug, obj, True, ctx)
                    db.session.commit()            # one row per transaction so a bad row never affects good ones
                    ok += 1
                except (ValueError, IntegrityError) as e:
                    db.session.rollback()
                    errors.append(f'Row {i}: {str(e)[:160]}')
            audit.log('import_csv', slug, details={'imported': ok, 'rejected': len(errors)}, commit=False)
            db.session.commit()
            report = dict(ok=ok, errors=errors[:25], total_errors=len(errors))
            flash(f'Imported {ok} row(s); {len(errors)} rejected.', 'success' if ok else 'warning')
    return render_template('crud/import.html', cfg=cfg, report=report)


# ------------------------------------------------------------------ detail
@bp.route('/<slug>/<int:id>')
@login_required
def detail(slug, id):
    cfg = get_cfg(slug)
    need(slug, 'view')
    obj = load(cfg, id)
    model = cfg['model']
    cols = [c.name for c in model.__table__.columns if c.name != 'password_hash']
    td = table_data(cfg, [obj], cols)
    fields = [(h[1], cell) for h, cell in zip(td['headers'], td['rows'][0]['cells'])]
    kids = []
    for child_slug, fk in cfg['children']:
        ccfg = REGISTRY[child_slug]
        if not current_user.can(child_slug, 'view'):
            continue
        q = scoped(ccfg, ccfg['model'].query.filter(getattr(ccfg['model'], fk) == obj.id)).order_by(ccfg['model'].id.desc())
        items = q.limit(25).all()
        kids.append(dict(cfg=ccfg, fk=fk, td=table_data(ccfg, items), count=q.count(),
                         can_add=current_user.can(child_slug, 'create') and not ccfg['readonly']))
    files = Attachment.query.filter_by(entity_slug=slug, entity_id=id).order_by(Attachment.id.desc()).all()
    images = IncidentImage.query.filter_by(incident_id=id).all() if slug == 'incidents' else []
    return render_template('crud/detail.html', cfg=cfg, obj=obj, fields=fields, kids=kids, files=files, images=images,
                           can_edit=current_user.can(slug, 'edit') and not cfg['readonly'] and not cfg['immutable'],
                           can_delete=current_user.can(slug, 'delete') and not cfg['readonly'] and not cfg['immutable'],
                           can_verify=current_user.can(slug, 'all') and current_user.can(slug, 'edit') and
                           getattr(obj, 'data_source', None) == 'reported')


# ------------------------------------------------------------------ create / edit
def virtual_meta(cfg, obj):
    out = []
    for v in cfg['virtual']:
        f = dict(name=v['name'], label=v['label'], kind=v['type'], required=v.get('required', False), help=v.get('help'),
                 value='')
        if v['name'] == 'role_code':
            from ..models import Role
            roles = Role.query.order_by(Role.name).all()
            if not current_user.has_role('super_admin'):
                roles = [r for r in roles if r.code != 'super_admin']
            f['choices'] = [(r.code, r.name) for r in roles]
            f['value'] = obj.role_codes[0] if getattr(obj, 'id', None) and obj.role_codes else ''
        out.append(f)
    return out


def form_view(cfg, obj, creating):
    slug, model = cfg['slug'], cfg['model']
    cols = form_columns(cfg, current_user)
    virt = virtual_meta(cfg, obj)
    errors, posted = {}, request.method == 'POST'
    if posted:
        data = request.form
        old = None if creating else {c.name: getattr(obj, c.name) for c in model.__table__.columns}
        errors = apply_form(cfg, obj, data, current_user, creating)
        for v in virt:
            if v['required'] and not data.get(v['name']) and v['name'] != 'password':
                errors[v['name']] = 'required'
        if creating and is_tracked(model):
            obj.created_by_id, obj.data_source = current_user.id, 'reported'
        ctx = dict(user=current_user, data=data, old=old)
        if not errors:
            msg = hooks.before_save(slug, obj, creating, ctx)
            if msg:
                errors['_form'] = msg
        if not errors:
            try:
                if creating:
                    db.session.add(obj)
                db.session.flush()
                hooks.after_save(slug, obj, creating, ctx)
                audit.log('create' if creating else 'update', slug, obj.id, obj.label, commit=False)
                db.session.commit()
                flash(f'{cfg["title"]}: record {"created" if creating else "updated"}.', 'success')
                return redirect(safe_next(url_for('crud.detail', slug=slug, id=obj.id)))
            except IntegrityError:
                errors['_form'] = 'Could not save: a unique value already exists or a referenced record is invalid.'
            except ValueError as e:
                errors['_form'] = str(e)
        db.session.rollback()
    fields = []
    for c in cols:
        if posted:
            val = request.form.get(c.name)
        elif creating:
            val = request.args.get(c.name) or default_of(c)
        else:
            val = to_input(c, getattr(obj, c.name))
        fields.append(field_meta(c, val))
    for v in virt:
        if posted:
            v['value'] = request.form.get(v['name'], '') if v['type'] != 'password' else ''
    return render_template('crud/form.html', cfg=cfg, obj=obj, creating=creating, fields=fields, virtual=virt,
                           errors=errors, next=safe_next(''))


@bp.route('/<slug>/new', methods=['GET', 'POST'])
@login_required
def new(slug):
    cfg = get_cfg(slug)
    need(slug, 'create')
    mutable(cfg, 'create')
    return form_view(cfg, cfg['model'](), True)


@bp.route('/<slug>/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(slug, id):
    cfg = get_cfg(slug)
    need(slug, 'edit')
    mutable(cfg, 'edit')
    return form_view(cfg, load(cfg, id), False)


@bp.post('/<slug>/<int:id>/delete')
@login_required
def delete(slug, id):
    cfg = get_cfg(slug)
    need(slug, 'delete')
    mutable(cfg, 'delete')
    obj = load(cfg, id)
    if slug == 'users' and obj.id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('crud.index', slug=slug))
    if slug == 'roles' and obj.is_system:
        flash('System roles cannot be deleted.', 'danger')
        return redirect(url_for('crud.index', slug=slug))
    label = obj.label
    try:
        db.session.delete(obj)
        db.session.flush()
        hooks.after_delete(slug, obj)
        audit.log('delete', slug, id, label, commit=False)
        db.session.commit()
        flash('Record deleted.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Cannot delete: other records still reference it. Close or deactivate it instead.', 'danger')
    return redirect(safe_next(url_for('crud.index', slug=slug)))


@bp.post('/<slug>/<int:id>/verify')
@login_required
def verify(slug, id):
    cfg = get_cfg(slug)
    need(slug, 'edit')
    need(slug, 'all')
    obj = load(cfg, id)
    if getattr(obj, 'data_source', None) != 'reported':
        flash('Only records with status "reported" can be verified (sample data can never be verified).', 'warning')
    else:
        obj.data_source, obj.verified_by_id, obj.verified_at = 'verified', current_user.id, datetime.utcnow()
        audit.log('verify', slug, id, commit=False)
        db.session.commit()
        flash('Record marked as verified.', 'success')
    return redirect(url_for('crud.detail', slug=slug, id=id))


# ------------------------------------------------------------------ uploads
@bp.post('/<slug>/<int:id>/upload')
@login_required
def upload(slug, id):
    cfg = get_cfg(slug)
    need(slug, 'edit')
    obj = load(cfg, id)
    try:
        stored, name, mime, size = uploads.save(request.files.get('file'))
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('crud.detail', slug=slug, id=id))
    desc = (request.form.get('description') or '')[:255] or None
    if slug == 'incidents' and mime.startswith('image/'):
        db.session.add(IncidentImage(incident_id=id, file_name=name, stored_name=stored, caption=desc,
                                     uploaded_by_id=current_user.id))
    else:
        db.session.add(Attachment(entity_slug=slug, entity_id=id, original_name=name, stored_name=stored, mime_type=mime,
                                  size_bytes=size, description=desc, uploaded_by_id=current_user.id))
    audit.log('upload', slug, id, name, commit=False)
    db.session.commit()
    flash('File uploaded.', 'success')
    return redirect(url_for('crud.detail', slug=slug, id=id))


@bp.post('/<slug>/<int:id>/file/<kind>/<int:fid>/delete')
@login_required
def delete_file(slug, id, kind, fid):
    cfg = get_cfg(slug)
    need(slug, 'edit')
    load(cfg, id)
    f = (IncidentImage.query.filter_by(id=fid, incident_id=id).first() if kind == 'image'
         else Attachment.query.filter_by(id=fid, entity_slug=slug, entity_id=id).first_or_404())
    if f:
        import os
        from flask import current_app
        try:
            os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], f.stored_name))
        except OSError:
            pass
        db.session.delete(f)
        audit.log('delete_file', slug, id, commit=False)
        db.session.commit()
        flash('File removed.', 'success')
    return redirect(url_for('crud.detail', slug=slug, id=id))
