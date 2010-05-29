# Copyright 2010 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Class used for connecting to the results site."""

import os
import platform
import random
import socket
import sys
import tempfile
import time
import urllib
import zlib

# third_party
import httplib2
import simplejson

import util

RETRY_WAIT = 10


class SiteConnector(object):
  """Methods that connect to the results site."""

  def __init__(self, config, status_callback=None):
    self.config = config
    self.url = self.config.site_url.rstrip('/')
    self.status_callback = status_callback
    
  def msg(self, msg, count=None, total=None, **kwargs):
    if self.status_callback:
      self.status_callback(msg, count=count, total=total, **kwargs)
    else:
      print '%s [%s/%s]' % (msg, count, total)

  def GetIndexHosts(self):
    """Get a list of 'index' hosts for standardized testing."""
    url = self.url + '/index_hosts'
    h = httplib2.Http(tempfile.gettempdir(), timeout=10)
    content = None
    try:
      unused_resp, content = h.request(url, 'GET')
      hosts = []
      for record_type, host in simplejson.loads(content):
        hosts.append((str(record_type), str(host)))
      return hosts
    except simplejson.decoder.JSONDecodeError:
      self.msg('Failed to decode: "%s"' % content)
      return []
    except AttributeError:
      self.msg('%s refused connection' % url)
      return []
    except:
      self.msg('* Failed to fetch %s: %s' % (url, util.GetLastExceptionString()))
      return []
      

  def UploadJsonResults(self, json_data, hide_results=False, fail_quickly=False):
    """Data is generated by reporter.CreateJsonData."""

    url = self.url + '/submit'
    if not url or not url.startswith('http'):
      return (False, 'error')
    h = httplib2.Http()
    post_data = {
        'client_id': self._CalculateDuplicateCheckId(),
        'submit_id': random.randint(0, 2**32),
        'hidden': bool(hide_results),
        'data': json_data
    }
    try:
      resp, content = h.request(url, 'POST', urllib.urlencode(post_data))
      try:
        data = simplejson.loads(content)
        for note in data['notes']:
          print '    * %s' % note
        return (''.join((self.url, data['url'])), data['state'])
      except:
        print 'ERROR in RESPONSE for %s: [%s]:\n  %s' % (url, resp, content)
    # See http://code.google.com/p/httplib2/issues/detail?id=62
    except AttributeError:
      self.msg('%s refused connection' % url)
    except:
      self.msg('Error uploading results: %s' % util.GetLastExceptionString())

    # We haven't returned, something is up.
    if not fail_quickly:
      self.msg('Problem talking to %s, will retry after %ss' % (url, RETRY_WAIT))
      time.sleep(RETRY_WAIT)
      self.UploadJsonResults(json_data, hide_results=hide_results, fail_quickly=True)
    
    return (False, 'error')

  def _CalculateDuplicateCheckId(self):
    """This is so that we can detect duplicate submissions from a particular host.

    Returns:
      checksum: integer
    """
    # From http://docs.python.org/release/2.5.2/lib/module-zlib.html
    # "not suitable for use as a general hash algorithm."
    #
    # We are only using it as a temporary way to detect duplicate runs on the
    # same host in a short time period, so it's accuracy is not important.
    return zlib.crc32(platform.platform() + sys.version + platform.node() +
                      os.getenv('HOME', '') + os.getenv('USERPROFILE', ''))
