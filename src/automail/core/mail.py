import email.message
import hashlib
import json
import mimetypes
import os.path
import re
import uuid

import bs4
import chardet

try:
    import geojson
except ImportError:
    geojson = None
import markdown
import yaml

from automail.utils import parse as utils_parse


class Codec(object):
    @classmethod
    def get_id(cls, item):
        """Returns a unique ID for the item.
        Defaults to item.id if present, or uses a 128-bits hash of str(item)
        """
        return getattr(
            item, "id", hashlib.sha3_256(str(item).encode("utf-8")).hexdigest()[:32]
        )

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
        return getattr(item, "external_id", None)

    @classmethod
    def get_issuer(cls, item):
        """Issuer address
        """
        return "example@example.com"

    @classmethod
    def get_recipient(cls, item):
        """Recipient address
        """
        return "example@example.com"

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
        if hasattr(item, "__dict__"):
            return {str(k): str(v) for k, v in item.__dict__}
        return str(item)

    @classmethod
    def get_text_template(cls, item):
        """Template to generate a text version of the body using the context.
        """
        return "{}"

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
        return "<container>{markup}</container>"

    @classmethod
    def get_attachments(cls, item):
        """Returns file attachments for given item.
        python file compatible objects are expected (file.name & file.read())
        """
        return None

    @classmethod
    def update_item(cls, **kwargs):
        return kwargs

    @classmethod
    def re_new(cls):
        return re.compile(r"new")

    @classmethod
    def re_external_id(cls):
        return re.compile(r"x-?ref(erence)?\s+([^\s]+)")

    @classmethod
    def re_id(cls):
        return re.compile(r"ref(erence)?\s+([0-9a-f-]+)")


def create(item, codec=Codec):
    """Create an email.message.EmailMessage object using given codec
    """
    message = email.message.EmailMessage()
    identifier = codec.get_id(item)
    issuer = codec.get_issuer(item)
    sender, domain = email.utils.parseaddr(issuer)[1].split("@")
    message.add_header("From", issuer)
    message.add_header("To", codec.get_recipient(item))
    message.add_header("Message-ID", "<{}@{}>".format(uuid.uuid4(), domain))
    message.add_header("References", "<{}@{}>".format(identifier, domain))
    message.add_header("Reply-To", "{}+{}@{}".format(sender, identifier, domain))
    message.add_header(
        "Subject",
        "".join(
            "[{}]".format(t)
            for t in [codec.get_human_id(item), codec.get_external_id(item)]
            if t
        )
        + " "
        + codec.get_subject(item),
    )
    context = codec.get_context(item)
    plain = codec.render_template(codec.get_text_template(item), context)
    message.set_content(plain)
    message.add_alternative(json.dumps(context).encode("utf-8"), "application", "json")
    message.add_alternative(
        codec.render_template(
            codec.get_html_template(item),
            {"markup": codec.text_to_html(plain), "context": context},
        ),
        "html",
    )
    for file_ in codec.get_attachments(item) or []:
        filename = os.path.basename(file_.name)
        maintype, subtype = mimetypes.guess_type(filename)[0].split("/", 1)
        content = file_.read()
        if maintype == "text":
            charset = "utf-8"
            try:
                content = content.decode(charset)
            except UnicodeDecodeError:
                charset = chardet.detect(content).get("encoding")
                try:
                    content = content.decode(charset)
                except UnicodeDecodeError:
                    maintype, subtype = "application", "octet-stream"
        if maintype == "text":
            message.add_attachment(
                content, maintype, charset=charset, filename=filename
            )
        else:
            message.add_attachment(content, maintype, subtype, filename=filename)
    return message


EMAIL_ADDRESS_RE = re.compile(
    r"(?P<recipient>[A-Za-z0-9!#$%&'*/=?\.^_`{|}~-]+)"
    r"(\+(?P<identifier>[A-Za-z0-9!#$%&'*/=?\.^_`{|}~+-]+))?"
    r"@(?P<domain>[A-Za-z0-9.:\[\]-]+)"
)

SIGNATURE_RE = re.compile(r"^--\s*$", re.MULTILINE)


def get_address_parts(email_address):
    _name, address = email.utils.parseaddr(email_address)
    result = EMAIL_ADDRESS_RE.match(address).groupdict()
    return (result["recipient"], result["identifier"], result["domain"])


def parse(data, codec=Codec):  # noqa: C901
    message = email.message_from_bytes(data)
    # ################################################################## HEADERS
    _, issuer = email.utils.parseaddr(message.get("from"))
    subject = utils_parse.normalize(message.get("subject"))
    recipient, identifier, domain = get_address_parts(message.get("to"))
    new_tag, subject = utils_parse.consume_re(codec.re_new(), subject)
    new = bool(new_tag)
    external_id, subject = utils_parse.consume_re(codec.re_external_id(), subject)
    if not identifier and "in-reply-to" in message:
        irt = get_address_parts(message.get("in-reply-to"))
        if irt[0] == recipient and irt[2] == domain:
            if irt[1] == "new":
                new_tag = True
            else:
                identifier = irt[1]
            identifier = irt[1]
    if not identifier:
        identifier, subject = utils_parse.consume_re(codec.re_id(), subject)

    # ##################################################################### BODY
    json_part, text_part, html_part, attachments = "", "", "", []
    for part in message.walk():
        # sub-parts are iterated over in this walk
        if part.is_multipart():
            continue
        payload = part.get_payload(decode=True)
        if geojson and part.get_content_type() == "application/geo+json":
            try:
                attachments.append(
                    (part.get_content_type(), geojson.loads(payload.decode("utf-8")))
                )
            except ValueError:
                pass
        elif part.get_content_type() == "application/json":
            try:
                json_part = json.loads(payload.decode("utf-8"))
            except ValueError:
                json_part = None
        elif part.get_content_maintype() == "text":
            payload = payload.decode(part.get_content_charset() or "utf-8")
            # if multiple text/plain parts are given, concatenate
            if part.get_content_subtype() == "plain":
                text_part += payload
            # if no text/plain version is given,
            # get plain text version from HTML using BeautifulSoup
            if part.get_content_subtype() == "html" and not text_part:
                soup = bs4.BeautifulSoup(payload, "html.parser")
                for item in soup(["script", "style"]):
                    item.extract()
                html_part += "\n" + "\n".join(
                    l.strip() for l in soup.get_text().split("\n") if l
                )
            # other subtypes of txt are considered attachments
            if part.get_content_subtype() not in ("plain", "html"):
                attachments.append((part.get_content_type(), payload))
        # attachments
        elif part.get_content_maintype() in ("image", "video", "application"):
            attachments.append((part.get_content_type(), payload))

    # ################################################################# FIX TEXT
    text_part = (text_part or html_part).strip()
    # remove signature
    match = SIGNATURE_RE.search(text_part)
    if match:
        text_part = text_part[: match.start()].strip()

    # ################################################################# FIX JSON
    # if no `application/json` part was given, parse `text/plain` as YAML
    # if we manage to parse YAML, remove this part from `text/plain`
    # otherwise, leave the text part untouched
    if not json_part:
        try:
            # only parse the first YAML document provided.
            # this enables the user to provide YAML,
            # use the '---' or '...' YAML document separators
            # and provided plain text afterwards.
            json_part = next(yaml.safe_load_all(text_part))
            document_starts = [
                e
                for e in yaml.parse(text_part)
                if isinstance(e, yaml.events.DocumentStartEvent)
            ][1:]
            if document_starts:
                text_part = text_part[document_starts[1].end_mark.index + 1 :]
            else:
                text_part = ""
        except yaml.YAMLError:
            json_part = None

    return codec.update_item(
        domain=domain,
        issuer=issuer,
        recipient=recipient,
        identifier=identifier,
        external_id=external_id,
        new=new,
        subject=subject,
        json_part=json_part,
        text_part=text_part,
        attachments=attachments,
    )
