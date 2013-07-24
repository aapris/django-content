# -*- coding: utf-8 -*-
import email
import sys
import os
import re
import datetime
from dateutil import tz
import time
from optparse import make_option
from django.contrib.auth.models import User

from django.db import transaction
from django.db.models import Count #, Avg, Max, Min
from django.core.management.base import BaseCommand #, CommandError
from django.conf import settings
settings.DEBUG = False

import logging
log = logging.getLogger('fetch_mail')

from content.models import Content, Mail

# FIXME: handle mailed files elsewhere, e.g. in comeup app

# Helpers
def get_subject(msg):
    """
    Parse and decode msg's Subject.
    TODO: return meaningful value if Subject was not found, raise error when there is error
    TODO: link to the RFC.
    """
    try:
         subject_all = email.Header.decode_header(msg.get_all('Subject')[0])
    except:
        # TOD: Should we return false here?
        subject_all = []
    # Subject_all is a tuple, 1st item is Subject and 2nd item is possible encoding
    # [("Jimmy & Player's Bar", None)]
    # [('Fudiskent\xe4t vihert\xe4v\xe4t', 'iso-8859-1')]
    subject_list = []
    for word in subject_all:
        if word[1] is not None: # Try first to use encoding guessed by email-module
            try:
                subject_list.append(unicode(word[0], word[1]))
            except: # UnicodeDecodeError: 'iso2022_jp' codec can't decode byte 0x81 in position 0: illegal multibyte sequence
                subject_list.append(unicode(word[0], errors='replace'))
        else:
            try: # Try first latin-1, it's the best guess in western Europe
                subject_list.append(unicode(word[0], 'utf-8', errors='replace'))
            except UnicodeError: # Final fallback, use utf-8 and replace errors
                subject_list.append(unicode(word[0], 'latin-1'))
    try:
        subject = u' '.join(subject_list)
        # Remove extra whitespaces (TODO: use some wiser method here
        subject = subject.replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ').replace('  ', ' ')
    except:
        return False
    return subject

def get_recipient(msg):
    """
    Loop 'to_headers' until an email address(s) is found.
    Some mail servers use Envelope-to header.
    """
    to_headers = ['to', 'envelope-to', 'cc', ]
    tos = []
    while len(tos) == 0 and len(to_headers) > 0:
        tos = msg.get_all(to_headers.pop(0), [])
    return tos

def handle_part(part):
    filename = part.get_filename()
    filedata = part.get_payload(decode=1)
    return filename, filedata

# not in use yet
def get_all_data(msg):
    all = {}
    all['subject'] = get_subject(msg)
    all['tos'] = get_recipient(msg)
    all['msg_id'] = msg.get('message-id', '')
    all['froms'] = msg.get_all('from', [])
    return all

def savefiles(msg, simulate):
    """
    Extract parts from  msg (which is an email.message_from_string(str) instance)
    and send them to the database.
    NOTES:
    - uses only the first found email address to assume recipient

    TODO stuff
    - reject if From: is empty
    """
    part_counter = 1
    subject = get_subject(msg)
    tos = get_recipient(msg)
    #print tos
    msg_id = msg.get('message-id', '')
    froms = msg.get_all('from', [])
    p = re.compile('([\w\.\-]+)@')
    try: # May raise in some cases IndexError: list index out of range
        matches = p.findall(froms[0])
        sender_nick = matches[0].split(".")[0].title() # Use all before first '.'
    except:
        print "ERROR: No From header %s" % (msg_id)
        return False
    if len(tos) == 0:
        print "ERROR: No Tos found %s" % (msg_id)
        return False
    p = re.compile('([\w]+)\.([\w]+)@') # e.g. user.authtoken@plok.in
    matches = p.findall(tos[0])
    if len(matches) > 0:
        username = matches[0][0].title()
        key = matches[0][1].lower()
    else:
        print "ERROR: No user.authkey found from %s %s" % (tos[0], msg_id)
        return False
    print "User, key:", username, key
    # TODO: replace this with AuthTicket stuff
    #from django.contrib.auth import authenticate
    #user = authenticate(authtoken='qwerty123')
    try:
        user = User.objects.get(username=username.lower())
    except User.DoesNotExist:
        print "User.DoesNotExist !"
        log.warning("User.DoesNotExist: '%s'" % username)
        return False
    privacy = 'PRIVATE'
    if key.lower() == 'pub':
        privacy = 'PUBLIC'
    elif key.lower() == 'res':
        privacy = 'RESTRICTED'
    else:
        log.warning("Privacy part not found: '%s'" % key)

    parts_not_to_save = ["multipart/mixed",
                         "multipart/alternative",
                         "multipart/related",
                         "text/plain",
                         ]
    if simulate: # Print lots of debug stuff
        print u'=========\nMetadata:\n========='
        print u'''Subject: %s\nUsername: %s\nFrom: %s\nTo: %s\nM-id: %s\n(%s)''' % (
                subject, user, u','.join(froms), u','.join(tos), msg_id, privacy)
        print u'=========\nParts:\n========='
    saved_parts = 0
    log.info("Walking through message parts")
    for part in msg.walk():
        part_content_type = part.get_content_type()
        filename, filedata = handle_part(part)
        if part_content_type in parts_not_to_save or filename is None:
            # print "NOT SAVING", part_content_type
            log_msg = "Not saving '%s', filename '%s'." % (part_content_type, filename)
            log.info(log_msg)
            if simulate: print log_msg # Print lots of debug stuff
            continue
            #print filedata, type(filedata), len(filedata)
        if filedata is None or len(filedata) == 0:
            log_msg = "Not saving '%s', filename '%s', file has no data" % (part_content_type, filename)
            log.warning(log_msg)
            if simulate: print log_msg # Print lots of debug stuff
            continue
        log_msg = u'Saving: %s (%s)' % (filename, part_content_type)
        log.info(log_msg)
        if simulate: print log_msg # Print lots of debug stuff
        c = Content(
            user = user,
            privacy = privacy,
            caption = subject,
            author = sender_nick,
        )
        if simulate is False:
            c.set_file(filename, filedata)
            c.set_fileinfo()
            c.generate_thumbnail()
            #c.get_type_instance()
            c.save()
            saved_parts += 1
    return saved_parts


def process_mails(limit, simulate):
    mails = Mail.objects.filter(status='UNPROCESSED').order_by('created')
    if limit > 0:
        mails = mails[:limit]
    for mail in mails:
        path = mail.file.path
        with open(path, 'rt') as f:
            maildata = f.read()
        msg = email.message_from_string(maildata)
        saved_parts_count = savefiles(msg, simulate)
        if saved_parts_count:
            mail.status = 'PROCESSED'
            log.info("Saved %d files" % saved_parts_count)
        else:
            mail.status = 'FAILED'
            log.warning("Saved %d files" % saved_parts_count)
        mail.processed = datetime.datetime.now()
        if simulate == False:
            mail.save()

class Command(BaseCommand):
    # Limit max number of mails to process
    option_list = BaseCommand.option_list + (
        make_option('--limit',
                    action='store',
                    dest='limit',
                    type='int',
                    default=0,
                    help='Limit the number of mails to handle'),
        )
    # Don't move mail from 'new' to 'processed'/'failed' after processing it
    option_list = option_list + (
        make_option('--simulate',
                    action='store_true',
                    dest='simulate',
                    default=False,
                    help=u'Process mail but do not flag it processed, also do not save actual files to the database'),
        )
    args = ''
    help = 'Process new retrieved mails'

    def handle(self, *args, **options):
        limit = options.get('limit')
        #verbosity = options.get('verbosity')
        simulate = options.get('simulate')
        process_mails(limit=limit, simulate=simulate)
