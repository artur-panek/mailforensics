# Security

MailForensics processes mail infrastructure evidence that can contain sensitive information.

## Reporting a security issue

Do not open a public issue containing credentials, private mail content, authentication material, or unsanitized production logs.

For ordinary parser bugs, use the bug-report form with a minimal sanitized fixture.

## Data handling

MailForensics is designed as a local CLI. It does not require a hosted service or database. HTML and JSON reports are generated locally from the evidence you provide.

Always review generated reports before sharing them outside your environment.
