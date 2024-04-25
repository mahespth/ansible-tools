from ansible.plugins.callback import CallbackBase
from ansible import constants as C

class CallbackModule(CallbackBase):
    """
    This callback module overrides the no_log feature for debugging purposes.
    """
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'stdout'
    CALLBACK_NAME = 'debug_override'

    def v2_runner_on_ok(self, result):
        # Check if no_log is enabled, and if so, force it to log the output.
        if result._result.get('censored'):
            self._display.display("Override no_log: %s" % result._result, color=C.COLOR_DEBUG)
        else:
            self._display.display("Normal log: %s" % result._result, color=C.COLOR_OK)

    def v2_runner_on_failed(self, result, ignore_errors=False):
        if 'msg' in result._result:
            self._display.display("Failure due to: %s" % result._result['msg'], color=C.COLOR_ERROR)


"""
[defaults]
stdout_callback = debug_override
callback_plugins = ./callback_plugins/
"""

