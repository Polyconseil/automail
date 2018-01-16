import email.message
import hashlib
import json
import mimetypes
import os.path
import uuid

import markdown


class Codec(object):
    @classmethod
    def get_id(cls, item):
        """Returns a unique ID for the item.
        Defaults to item.id if present, or uses a 128-bits hash of str(item)
        """
        return getattr(item, 'id', hashlib.sha3_256(str(item).encode('utf-8')).hexdigest()[:32])

    @classmethod
    def get_human_id(cls, item):
        """Returns a human readable version of the ID for the mail subject.
        Defaults to get_id(item)[:13]
        """
        return cls.get_id(item)[:13]

    @classmethod
    def get_external_id(cls, item):
        """Returns an external ID for the item.
        Defaults to item.external_id if present, or None.
        """
        return getattr(item, 'external_id', None)

    @classmethod
    def get_from(cls, item):
        """Sender address
        """
        return 'example@example.com'

    @classmethod
    def get_to(cls, item):
        """Recipient address
        """
        return 'example@example.com'

    @classmethod
    def get_subject(cls, item):
        """Subject of the e-mail (title of the item), defaults to str(item)
        """
        return str(item)

    @classmethod
    def render_template(cls, template, context):
        """Render a template given the item context
        """
        if isinstance(context, dict):
            return template.format(**context)
        return template.format(context)

    @classmethod
    def get_context(cls, item):
        """Returns a dict context of the item for serialization
        """
        if hasattr(item, '__dict__'):
            return {str(k): str(v) for k, v in item.__dict__}
        return str(item)

    @classmethod
    def get_text_template(cls, item):
        """Template to generate a text version of the body using the context.
        """
        return '{}'

    @classmethod
    def text_to_html(cls, text):
        """Generate an HTML version of the plain text.
        Defaults to a markdown generation.
        """
        return markdown.markdown(text)

    @classmethod
    def get_html_template(cls, item):
        """Template to generate an HTML version of the body using the context
        and the markdown version of the body.
        The context passed down to the template will be:
        {markup: "HTML generated from markup text", context: ...}
        """
        return '<container>{markup}</container>'

    @classmethod
    def get_attachments(cls, item):
        return None


def create(item, codec=Codec):
    """Create an email.message.EmailMessage object using given codec
    """
    message = email.message.EmailMessage()
    uid = codec.get_id(item)
    from_ = codec.get_from(item)
    sender, domain = email.utils.parseaddr(from_)[1].split('@')
    message.add_header('From', from_)
    message.add_header('To', codec.get_to(item))
    message.add_header('Message-ID', '<{}@{}>'.format(uuid.uuid4(), domain))
    message.add_header('Reply-To', '{}+{}@{}'.format(sender, uid, domain))
    message.add_header('References', '<{}@{}>'.format(uid, domain))
    message.add_header(
        'Subject',
        ''.join(
            '[{}]'.format(t)
            for t in [codec.get_human_id(item), codec.get_external_id(item)]
            if t
        ) + ' ' + codec.get_subject(item),
     )
    context = codec.get_context(item)
    plain = codec.render_template(codec.get_text_template(item), context)
    message.set_content(plain)
    message.add_alternative(
        json.dumps(context).encode('utf-8'),
        'application', 'json',
    )
    message.add_alternative(
        codec.render_template(
            codec.get_html_template(item),
            {'markup': codec.text_to_html(plain), "context": context}
        ),
        'html',
    )
    for file_ in codec.get_attachments(item) or []:
        filename = os.path.basename(file_.name)
        maintype, subtype = mimetypes.guess_type(filename).split('/', 1)
        message.add_attachment(
            file_.read(),
            maintype,
            subtype,
            filename=filename,
        )
    return message
