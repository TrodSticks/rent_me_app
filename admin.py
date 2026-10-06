"""Administration: the report queue, hiding listings and landlord verification.

Every route here is wrapped in admin_required, which checks the signed-in account on the
server. Nothing on the site can make someone an administrator; see cli.py for that.
"""
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from app import db
from models import REPORT_OUTCOMES, Property, Report, User, utcnow
from routes import bp, is_safe_redirect
from security import admin_required

PAGE_SIZE = 20


def _page():
    return max(request.args.get('page', 1, type=int) or 1, 1)


def _back(default_endpoint):
    return redirect(request.referrer if is_safe_redirect(request.referrer) else url_for(default_endpoint))


def hide_listing(property, reason):
    property.is_hidden = True
    property.hidden_at = utcnow()
    property.hidden_by_id = current_user.id
    property.hidden_reason = (reason or '').strip()[:200] or None


def restore_listing(property):
    property.is_hidden = False
    property.hidden_at = None
    property.hidden_by_id = None
    property.hidden_reason = None


# ---------- Reports ----------

@bp.route("/admin")
@admin_required
def admin_home():
    return redirect(url_for("main.admin_reports"))

@bp.route("/admin/reports")
@admin_required
def admin_reports():
    status = 'resolved' if request.args.get('status') == 'resolved' else 'open'
    query = Report.query.options(joinedload(Report.property), joinedload(Report.reporter),
                                 joinedload(Report.resolved_by)).filter(Report.status == status)
    # Oldest open reports first; most recently resolved first
    query = query.order_by(Report.created_at.asc(), Report.id.asc()) if status == 'open' \
        else query.order_by(Report.resolved_at.desc(), Report.id.desc())
    total = Report.query.filter(Report.status == status).count()
    page = _page()
    reports = query.limit(PAGE_SIZE).offset((page - 1) * PAGE_SIZE).all()
    hidden = Property.query.options(joinedload(Property.hidden_by)).filter(Property.is_hidden.is_(True)) \
        .order_by(Property.hidden_at.desc()).limit(50).all()
    return render_template("admin_reports.html", title="Reports", reports=reports, status=status,
                           page=page, has_next=page * PAGE_SIZE < total, total=total,
                           open_count=Report.query.filter(Report.status == 'open').count(),
                           hidden=hidden, outcomes=REPORT_OUTCOMES)

@bp.route("/admin/reports/<int:report_id>/resolve", methods=["POST"])
@admin_required
def admin_resolve_report(report_id):
    report = db.get_or_404(Report, report_id)
    outcome = request.form.get("outcome")
    if outcome not in REPORT_OUTCOMES:
        flash("Please choose an outcome for the report.", "danger")
        return _back("main.admin_reports")
    if report.status == 'resolved':
        flash("That report was already resolved.", "info")
        return _back("main.admin_reports")

    notes = request.form.get("notes", "").strip()[:1000]
    report.status = 'resolved'
    report.outcome = outcome
    report.resolution_notes = notes or None
    report.resolved_by_id = current_user.id
    report.resolved_at = utcnow()
    if outcome == 'listing_hidden':
        hide_listing(report.property, notes or f"Reported: {report.reason}")
    db.session.commit()
    flash("Report resolved." + (" The listing is now hidden." if outcome == 'listing_hidden' else ""), "success")
    return _back("main.admin_reports")

@bp.route("/admin/listings/<int:property_id>/hide", methods=["POST"])
@admin_required
def admin_hide_listing(property_id):
    property = db.get_or_404(Property, property_id)
    hide_listing(property, request.form.get("reason"))
    db.session.commit()
    flash(f"\"{property.title}\" is now hidden from renters.", "success")
    return _back("main.admin_reports")

@bp.route("/admin/listings/<int:property_id>/restore", methods=["POST"])
@admin_required
def admin_restore_listing(property_id):
    property = db.get_or_404(Property, property_id)
    restore_listing(property)
    db.session.commit()
    flash(f"\"{property.title}\" is visible to renters again.", "success")
    return _back("main.admin_reports")


# ---------- Landlord verification ----------

@bp.route("/admin/landlords")
@admin_required
def admin_landlords():
    search = request.args.get('q', '').strip()[:120]
    query = User.query.options(joinedload(User.landlord_verified_by)).filter(User.role == 'Landlord')
    if search:
        like = f"%{search.lower()}%"
        query = query.filter(func.lower(User.email).like(like) | func.lower(User.username).like(like))
    total = query.count()
    page = _page()
    landlords = query.order_by(User.id.desc()).limit(PAGE_SIZE).offset((page - 1) * PAGE_SIZE).all()
    return render_template("admin_landlords.html", title="Landlords", landlords=landlords, search=search,
                           page=page, has_next=page * PAGE_SIZE < total, total=total)

@bp.route("/admin/landlords/<int:user_id>/verify", methods=["POST"])
@admin_required
def admin_verify_landlord(user_id):
    landlord = db.get_or_404(User, user_id)
    if landlord.role != 'Landlord':
        flash("Only landlord accounts can be verified.", "danger")
    else:
        # Record who approved it and when
        landlord.landlord_verified_at = utcnow()
        landlord.landlord_verified_by_id = current_user.id
        db.session.commit()
        flash(f"{landlord.username} is now shown as a verified landlord.", "success")
    return _back("main.admin_landlords")

@bp.route("/admin/landlords/<int:user_id>/revoke", methods=["POST"])
@admin_required
def admin_revoke_landlord(user_id):
    landlord = db.get_or_404(User, user_id)
    landlord.landlord_verified_at = None
    landlord.landlord_verified_by_id = None
    db.session.commit()
    flash(f"{landlord.username} is no longer shown as a verified landlord.", "success")
    return _back("main.admin_landlords")
