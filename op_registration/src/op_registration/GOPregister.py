import click
from pync import Notifier

import op_registration


@click.group()
def main() -> None:
    click.echo(" command is active")


main.add_command(op_registration.set_credentials)
main.add_command(op_registration.schedule_registration)
