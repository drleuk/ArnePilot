"""Install exception handler for process crash."""
import os
import sys
import capnp
import requests
import threading
from common.params import Params
from selfdrive.version import version, dirty, origin, branch
from common.op_params import opParams
op_params = opParams()
uniqueID = op_params.get('uniqueID', None)

from selfdrive.swaglog import cloudlog
from common.android import ANDROID

if os.getenv("NOLOG") or os.getenv("NOCRASH") or not ANDROID:
  def capture_exception(*exc_info):
    pass
  def bind_user(**kwargs):
    pass
  def bind_extra(**kwargs):
    pass
  def install():
    pass
else:
  from raven import Client
  from raven.transport.http import HTTPTransport
  params = Params()
  try:
    dongle_id = params.get("DongleId").decode('utf8')
  except AttributeError:
    dongle_id = "None"
  try:
    ipaddress = requests.get('https://checkip.amazonaws.com/').text.strip()
  except:
    ipaddress = "255.255.255.255"
  error_tags = {'dirty': dirty, 'username': uniqueID, 'dongle_id': dongle_id, 'branch': branch, 'remote': origin}
  
  client = Client('https://137e8e621f114f858f4c392c52e18c6d:8aba82f49af040c8aac45e95a8484970@sentry.io/1404547',
                  install_sys_hook=False, transport=HTTPTransport, release=version, tags=error_tags)

  def capture_exception(*args, **kwargs):
    exc_info = sys.exc_info()
    if not exc_info[0] is capnp.lib.capnp.KjException:
      client.captureException(*args, **kwargs)
    cloudlog.error("crash", exc_info=kwargs.get('exc_info', 1))
    
  def bind_user(**kwargs):
    client.user_context(kwargs)
    
  def capture_warning(warning_string):
    bind_user(id=dongle_id, ip_address=ipaddress)
    client.captureMessage(warning_string, level='warning')
  
  def capture_info(info_string):
    bind_user(id=dongle_id, ip_address=ipaddress)
    client.captureMessage(info_string, level='info')
    
  def bind_extra(**kwargs):
    client.extra_context(kwargs)

  def install():
    # installs a sys.excepthook
    __excepthook__ = sys.excepthook
    def handle_exception(*exc_info):
      if exc_info[0] not in (KeyboardInterrupt, SystemExit):
        capture_exception(exc_info=exc_info)
      __excepthook__(*exc_info)
    sys.excepthook = handle_exception

    """
    Workaround for `sys.excepthook` thread bug from:
    http://bugs.python.org/issue1230540
    Call once from the main thread before creating any threads.
    Source: https://stackoverflow.com/a/31622038
    """
    init_original = threading.Thread.__init__

    def init(self, *args, **kwargs):
      init_original(self, *args, **kwargs)
      run_original = self.run

      def run_with_except_hook(*args2, **kwargs2):
        try:
          run_original(*args2, **kwargs2)
        except Exception:
          sys.excepthook(*sys.exc_info())

      self.run = run_with_except_hook

    threading.Thread.__init__ = init
