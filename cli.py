"""Commands run on the server: `flask --app app <command>`.

Administrator access is only ever granted here. Running a command needs access to the
server and its database, which a visitor to the site never has.
"""
import click
from sqlalchemy import func
from app import db
from models import User


def _find(email):
    user = User.query.filter(func.lower(User.email) == email.strip().lower()).first()
    if user is None:
        raise click.ClickException(f"No account with the email {email}. The person has to sign up first.")
    return user


def register_commands(app):
    @app.cli.command("make-admin")
    @click.argument("email")
    def make_admin(email):
        """Give an existing account administrator access."""
        user = _find(email)
        if user.is_admin:
            click.echo(f"{user.email} is already an administrator.")
            return
        user.is_admin = True
        db.session.commit()
        click.echo(f"{user.email} ({user.username}) is now an administrator.")

    @app.cli.command("revoke-admin")
    @click.argument("email")
    def revoke_admin(email):
        """Take administrator access away from an account."""
        user = _find(email)
        user.is_admin = False
        db.session.commit()
        click.echo(f"{user.email} is no longer an administrator.")

    @app.cli.command("list-admins")
    def list_admins():
        """Show which accounts have administrator access."""
        admins = User.query.filter(User.is_admin.is_(True)).order_by(User.id).all()
        if not admins:
            click.echo("There are no administrators yet. Create one with: flask --app app make-admin EMAIL")
        for user in admins:
            click.echo(f"{user.email} ({user.username})")
