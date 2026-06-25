"""Shared test setup — keep the suite from ever touching external services.

The registration flow emails the admin via Resend. With a real ``RESEND_API_KEY``
in the developer's ``.env``, running the suite would send real mail to the test
admin address (``admin@test.de``) and burn the Resend quota. Forcing the key empty
here — before any app/config import — makes ``send_email()`` short-circuit to a
no-op in tests. Imported by pytest before test modules, so it wins over ``.env``.
"""
import os

os.environ["RESEND_API_KEY"] = ""
