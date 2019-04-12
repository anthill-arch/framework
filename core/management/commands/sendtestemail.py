from anthill.framework.core.management import Command, Option


class SendTestEmail(Command):
    help = description = 'Sends a test email to the email addresses specified as arguments.'

    def get_options(self):
        options = (
            Option('-e', '--email', dest='email', nargs='*',
                   help='One or more email addresses to send a test email to.'),
            Option('-m', '--managers', dest='managers', action='store_true',
                   help='Send a test email to the addresses specified in settings.MANAGERS.'),
            Option('-a', '--admins', dest='admins', action='store_true',
                   help='Send a test email to the addresses specified in settings.ADMINS.'),
        )
        return options

    def run(self, *args, **kwargs):
        import socket
        from anthill.framework.utils import timezone
        from anthill.framework.core.mail import mail_admins, mail_managers, send_mail

        subject = 'Test email from %s on %s' % (socket.gethostname(), timezone.now())

        send_mail(
            subject=subject,
            message="If you\'re reading this, it was successful.",
            from_email=None,
            recipient_list=kwargs['email'],
        )

        if kwargs['managers']:
            mail_managers(subject, "This email was sent to the site managers.")

        if kwargs['admins']:
            mail_admins(subject, "This email was sent to the site admins.")
