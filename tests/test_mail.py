import textwrap

import automail.core.mail


def test_create():
    message = automail.core.mail.create('test')
    message.set_boundary('===============BOUND==')  # for test purpose
    assert message.as_string() == textwrap.dedent(
        """
        From: example@example.com
        To: example@example.com
        Message-ID: {}
        Reply-To: example+36f028580bb02cc8272a9a020f4200e3@example.com
        References: <36f028580bb02cc8272a9a020f4200e3@example.com>
        Subject: [36f028580bb02] test
        MIME-Version: 1.0
        Content-Type: multipart/alternative; boundary="===============BOUND=="

        --===============BOUND==
        Content-Type: text/plain; charset="utf-8"
        Content-Transfer-Encoding: 7bit

        test

        --===============BOUND==
        Content-Type: application/json
        Content-Transfer-Encoding: base64
        MIME-Version: 1.0

        InRlc3Qi

        --===============BOUND==
        Content-Type: text/html; charset="utf-8"
        Content-Transfer-Encoding: 7bit
        MIME-Version: 1.0

        <container><p>test</p></container>

        --===============BOUND==--
        """.format(message.get('message-id'))[1:]  # remove initial LR
    )
