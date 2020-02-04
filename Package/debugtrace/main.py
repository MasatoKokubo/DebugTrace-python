# main.py
# (C) 2020 Masato Kokubo
from abc import abstractmethod
import configparser
import datetime
import inspect
import logging
from logging import config
import os
import sys
import traceback
from debugtrace import _print as pr

_DO_NOT_OUTPUT = 'Do not output'

_config_path = './' + __package__ + '.ini'
_config = configparser.ConfigParser()
if os.path.exists(_config_path):
    _config.read(_config_path)

def _get_config_value(key: str, fallback: object) -> object:
    value = fallback
    try:
        if type(fallback) == bool:
            value = _config.getboolean(__package__, key, fallback=fallback)
        elif type(fallback) == int:
            value = _config.getint(__package__, key, fallback=fallback)
        else:
            value = _config.get(__package__, key, fallback=fallback)
            value = value.replace('\\s', ' ')

    except BaseException as ex:
        pr._print('debugtrace: (' + _config_path + ') key: ' + key + ', error: '  + str(ex), sys.stderr)

    return value

_logger_name                 = _get_config_value('logger'                      , 'stderr'                  ).lower()
_logging_config_file         = _get_config_value('logging_config_file'         , 'logging.conf'            )
_logging_logger_name         = _get_config_value('logging_logger_name'         , __package__               )
_logging_level               = _get_config_value('logging_level'               , 'DEBUG'                   ).upper()
is_enabled                   = _get_config_value('is_enabled'                  , True                      )
enter_string                 = _get_config_value('enter_string'                , 'Enter'                   )
leave_string                 = _get_config_value('leave_string'                , 'Leave'                   )
limit_string                 = _get_config_value('limit_string'                , '...'                     )
_maximum_indents             = _get_config_value('maximum_indents'             , 20                        )
_code_indent_string          = _get_config_value('code_indent_string'          , '|   '                    )
_data_indent_string          = _get_config_value('data_indent_string'          , '  '                      )
non_output_string            = _get_config_value('non_output_string'           , '...'                     )
cyclic_reference_string      = _get_config_value('cyclic_reference_string'     , '*** Cyclic Reference ***')
varname_value_separator      = _get_config_value('varname_value_separator'     , ' = '                     )
key_value_separator          = _get_config_value('key_value_separator'         , ': '                      )
log_datetime_format          = _get_config_value('log_datetime_format'         , '%Y-%m-%d %H:%M:%S.%f'    )
enter_format                 = _get_config_value('enter_format'                , '{0} ({1}:{2})'           )
leave_format                 = _get_config_value('leave_format'                , '{0} ({1}:{2}) time: {3}'     )
count_format                 = _get_config_value('count_format'                , 'count:{}'                )
minimum_output_count         = _get_config_value('minimum_output_count'        , 5                         )
string_length_format         = _get_config_value('string_length_format'        , 'length:{}'               )
minimum_output_string_length = _get_config_value('minimum_output_string_length', 5                         )
maximum_data_output_width    = _get_config_value('maximum_data_output_width'   , 80                        )
collection_limit             = _get_config_value('collection_limit'            , 256                       )
string_limit                 = _get_config_value('string_limit'                , 2048                      )
reflection_nest_limit        = _get_config_value('reflection_nest_limit'       , 4                         )
non_output_attributes        = [] # Not implemented
reflection_classes           = [] # Not implemented
output_non_public_attributes = [] # Not implemented
#   log_time_zone: datetime.timezone = None

class _LoggerBase(object):
    @abstractmethod
    def print(self, message: str) -> None:
        pass

class _Std(_LoggerBase):
    def __init__(self, iostream):
        self.iostream = iostream
    
    def print(self, message: str) -> None:
        pr._print(datetime.datetime.now().strftime(log_datetime_format) + ' ' + message, self.iostream)

class StdOut(_Std):
    def __init__(self):
        super().__init__(sys.stdout)

    def __str__(self):
        return 'sys.stsdout'

class StdErr(_Std):
    def __init__(self):
        super().__init__(sys.stderr)

    def __str__(self):
        return 'sys.stderr'

class Logger(_LoggerBase):
    def __init__(self):
        if os.path.exists(_logging_config_file):
            config.fileConfig(_logging_config_file)
        else:
            pr._print('debugtrace: (' + _config_path + ') _logging_config_file = ' + _logging_config_file + \
                ' (Not found)', sys.stderr)

        self.logger = logging.getLogger(_logging_logger_name)
        self._logging_level = \
            logging.CRITICAL if _logging_level == 'CRITICAL' else \
            logging.ERROR    if _logging_level == 'ERROR'    else \
            logging.WARNING  if _logging_level == 'WARNING'  else \
            logging.INFO     if _logging_level == 'INFO'     else \
            logging.DEBUG    if _logging_level == 'DEBUG'    else \
            logging.NOTSET   if _logging_level == 'NOTSET'   else \
            logging.DEBUG

    def print(self, message: str) -> None:
        self.logger.log(self._logging_level, message)

    def __str__(self):
        return "logging.Logger('" + _logging_logger_name + "'), logging level: " + _logging_level

_logger = StdErr()
if _logger_name == 'stdout':
    _logger = StdOut()
elif _logger_name == 'stderr':
    _logger = StdErr()
elif _logger_name == 'logger':
    _logger = Logger()
else:
    pr._print('debugtrace: (' + _config_path + ') logger = ' + _logger_name + ' (Unknown)', sys.stderr)

_code_indent_strings = []
_data_indent_strings = []
_code_nest_level     = 0
_previous_nest_level = 0
_data_nest_level     = 0
_last_print_strings  = []
_reflected_objects   = []

def _up_nest() -> None:
    global _previous_nest_level
    global _code_nest_level

    _previous_nest_level = _code_nest_level
    _code_nest_level += 1

def _down_nest() -> None:
    global _previous_nest_level
    global _code_nest_level

    _previous_nest_level = _code_nest_level
    _code_nest_level -= 1

def _get_indent_string() -> str:
    global _code_indent_strings

    if len(_code_indent_strings) == 0:
        _code_indent_strings = \
            [_code_indent_string * index for index in range(0, _maximum_indents)]

    return _code_indent_strings[
        0 if (_code_nest_level < 0) else
        len(_code_indent_strings) - 1 if (_code_nest_level >= len(_code_indent_strings)) else
        _code_nest_level
    ]

def _get_data_indent_string() -> str:
    global _data_indent_strings

    if len(_data_indent_strings) == 0:
        _data_indent_strings = \
            [_data_indent_string * index for index in range(0, _maximum_indents)]

    return _data_indent_strings[
        0 if (_data_nest_level < 0) else
        len(_data_indent_strings) - 1 if (_data_nest_level >= len(_data_indent_strings)) else
        _data_nest_level
    ]

def _to_strings(value: object,
        output_private: bool,
        output_method: bool) -> list:
    strings = []
    if isinstance(value, type(None)):
        # None
        strings.append('None')
    elif isinstance(value, str):
        # str
        has_single_quote = False
        has_double_quote = False
        single_quote_str = \
            '(' + string_length_format.format(len(value)) + ')' if len(value) >= minimum_output_string_length \
            else ''
        double_quote_str = single_quote_str
        single_quote_str += "'"
        double_quote_str += '"'
        count = 1
        for char in value:
            if count > string_limit:
                single_quote_str += limit_string
                double_quote_str += limit_string
                break
            if char == "'":
                single_quote_str += "\\'"
                double_quote_str += char
                has_single_quote = True
            elif char == '"':
                single_quote_str += char
                double_quote_str += '\\"'
                has_double_quote = True
            elif char == '\\':
                single_quote_str += '\\\\'
                double_quote_str += '\\\\'
            elif char == '\n':
                single_quote_str += '\\n'
                double_quote_str += '\\n'
            elif char == '\r':
                single_quote_str += '\\r'
                double_quote_str += '\\r'
            elif char == '\t':
                single_quote_str += '\\t'
                double_quote_str += '\\t'
            elif char < ' ':
                num_str = format(ord(char), '02X')
                single_quote_str += '\\x' + num_str
                double_quote_str += '\\x' + num_str
            else:
                single_quote_str += char
                double_quote_str += char
            count += 1

        double_quote_str += '"'
        single_quote_str += "'"
        if has_single_quote and not has_double_quote:
            strings.append(double_quote_str)
        else:
            strings.append(single_quote_str)

    elif isinstance(value, int) or isinstance(value, float) or \
        isinstance(value, datetime.date) or isinstance(value, datetime.time) or \
        isinstance(value, datetime.datetime):
        # int, float, datetime.date, datetime.time, datetime.datetime
        strings.append(str(value))

    elif isinstance(value, list) or \
            isinstance(value, set) or isinstance(value, frozenset) or \
            isinstance(value, tuple) or \
            isinstance(value, dict):
        # list, set, frozenset, tuple, dict
        strings = _to_strings_iterator(value, output_private, output_method)

    elif _has_str_method(value):
        # has __str__ method
        strings.append(str(value))

    else:
        # use refrection
        if any(map(lambda obj: value is obj, _reflected_objects)):
            # cyclic reference
            strings.append(cyclic_reference_string)
        elif len(_reflected_objects) > reflection_nest_limit:
            # over reflection level limitation
            strings.append(limit_string)
        else:
            _reflected_objects.append(value)
            strings = _to_strings_using_refrection(value, output_private, output_method)
            _reflected_objects.pop()

    return strings

def _to_strings_using_refrection(value: object,
        output_private: bool,
        output_method: bool) -> list:
    global _data_nest_level

    members = []
    try:
        base_members = inspect.getmembers(value,
            lambda v: not inspect.isclass(v) and
                (output_method or not inspect.ismethod(v)) and
                not inspect.isbuiltin(v))

        members = [m for m in base_members
                if (not m[0].startswith('__') or not m[0].endswith('__')) and
                    (output_private or not m[0].startswith('_'))]
    except BaseException as ex:
        return [str(ex)]

    strings = []
    _data_nest_level += 1
    indent_string = _get_data_indent_string()

    string = _get_type_name(value)
    string += '{'

    member_index = 0
    line_breaked = False
    string_backup = string
    for member in members:
        name = member[0]
        value_strings = _to_strings(member[1], output_private, output_method)

        if not line_breaked and len(value_strings) > 1:
            # multi line value strings
            strings.append(string)
            string = indent_string
            line_breaked = True

        string_backup2 = string
        string += name
        string += key_value_separator

        value_index = 0
        for value_string in value_strings:
            if value_index == 0:
                string += value_string
            else:
                strings.append(string)
                string = value_string

            if not line_breaked and len(string) > maximum_data_output_width:
                if len(strings) == 0:
                    # first line break
                    strings.append(string_backup)
                    right_string = string[len(string_backup):]
                    string = indent_string
                    string += right_string
                else:
                    strings.append(string_backup2)
                    string = indent_string
                    string += name
                    string += key_value_separator
                    string += value_string
            value_index += 1

        if member_index < len(members) - 1:
            string += ', '
        line_breaked = False
        member_index += 1

    _data_nest_level -= 1
    if not line_breaked and len(strings) > 0:
        strings.append(string)
        string = _get_data_indent_string()
    string += '}'
    strings.append(string)

    return strings

def _to_strings_iterator(values: object,
        output_private: bool,
        output_method: bool) -> list:
    global _data_nest_level

    open_char = '{' # set, frozenset, dict
    close_char = '}'
    if isinstance(values, list):
        # list
        open_char = '['
        close_char = ']'
    elif isinstance(values, tuple):
        # tuple
        open_char = '('
        close_char = ')'
    
    strings = []
    _data_nest_level += 1
    indent_string = _get_data_indent_string()

    string = _get_type_name(values, len(values))
    string += open_char

    element_index = 0
    line_breaked = False
    string_backup = string
    for element in values:
        if element_index >= collection_limit:
            string += limit_string
            break

        value_strings = []
        if isinstance(values, dict):
            # dictionary
            value_strings = _to_strings_keyvalue(element, values[element], output_private, output_method)
        else:
            # list, set, frozenset or tuple
            value_strings = _to_strings(element, output_private, output_method)

        if not line_breaked and len(value_strings) > 1:
            # multi line element strings
            strings.append(string)
            string = indent_string
            line_breaked = True

        string_backup2 = string

        value_index = 0
        for value_string in value_strings:
            if value_index == 0:
                string += value_string
            else:
                strings.append(string)
                string = value_string

            if not line_breaked and len(string) > maximum_data_output_width:
                if len(strings) == 0:
                    # first line break
                    strings.append(string_backup)
                    right_string = string[len(string_backup):]
                    string = indent_string
                    string += right_string
                else:
                    strings.append(string_backup2)
                    string = indent_string
                    string += value_string

            value_index += 1

        if element_index < len(values) - 1:
            string += ', '
        line_breaked = False
        element_index += 1

    _data_nest_level -= 1
    if not line_breaked and len(strings) > 0:
        strings.append(string)
        string = _get_data_indent_string()
    string += close_char
    strings.append(string)

    return strings

def _to_strings_keyvalue(key: object, value: object,
        output_private: bool,
        output_method: bool) -> list:
    global _data_nest_level

    strings = []
    string = ''
    key_strings = _to_strings(key, output_private, output_method)
    value_strings = _to_strings(value, output_private, output_method)

    # key
    indent_string = _get_data_indent_string()
    index = 0
    for key_string in key_strings:
        string += key_string
        if index < len(key_strings) - 1:
            # not last
            strings.append(string)
            string = indent_string
        index += 1

    string += key_value_separator

    # value
    _data_nest_level += 1
    indent_string = _get_data_indent_string()
    index = 0
    for value_string in value_strings:
        string += value_string
        if index < len(value_strings) - 1:
            # not last
            strings.append(string)
            string = indent_string
        index += 1
    _data_nest_level -= 1

    strings.append(string)
    return strings

def _get_type_name(value: object, count: int = -1) -> str:
    type_name = str(type(value))
    if type_name.startswith("<class '"):
        type_name = type_name[8:]
    elif type_name.startswith("<enum '"):
        type_name = 'enum ' + type_name[7:]
    if type_name.endswith("'>"):
        type_name = type_name[:-2]
    return '(' + type_name + ')' if count < minimum_output_count \
        else '(' + type_name + ' ' + count_format.format(count) + ')'

def _has_str_method(value: object) -> bool:
    try:
        members = inspect.getmembers(value, lambda v: inspect.ismethod(v))
        return len([member for member in members if member[0] == '__str__']) != 0
    except:
        return False

def print(name: str, value: object = _DO_NOT_OUTPUT, *,
        output_private: bool = False,
        output_method: bool = False) -> None:
    '''
    Outputs the name and value.

    Japanese: 名前と値を出力します。

    Args:
        name: The name of the value (simply output message if the value is omitted)
            Japanese: 出力する名前 (valueが省略されている場合は、単に出力するメッセージ)

        value: The value to output if not omitted
            Japanese: 出力する値 (省略されていなければ)

        output_private: Output private member if True
            Japanese: Trueならプライベートメンバーを出力する

        output_method: Output method if True
            Japanese:  Trueならメソッドを出力する
    '''
    global _data_nest_level
    global _last_print_strings
    global _reflected_objects

    if not is_enabled: return

    _data_nest_level = 0
    _reflected_objects.clear()

    indent_string = _get_indent_string()
    if value is _DO_NOT_OUTPUT:
        _logger.print(indent_string + name)
    else:
        last_print_lines = len(_last_print_strings)
        _last_print_strings = _to_strings(value, output_private, output_method)

        if last_print_lines > 1 or len(_last_print_strings) > 1:
            _logger.print(indent_string)

        first_line = True
        for value_string in _last_print_strings:
            line = indent_string
            if  first_line:
                line += name + varname_value_separator
            line += value_string
            _logger.print(line)
            first_line = False

class _DebugTrace(object):
    '''
    Outputs a entering log when initializing
    and outputs an leaving log when deleting.

    Japanese:
    初期化時に開始ログを出力し、削除時に終了ログを出力します。
    '''
    __slots__ = ['name', 'filename', 'lineno', 'enter_time']
    
    def __init__(self, invoker: object):
        if not is_enabled: return

        if isinstance(invoker, type(None)):
            self.name = ''
        else:
            self.name = type(invoker).__name__
            if self.name == 'type':
                self.name = invoker.__name__
            self.name += '.'

        try:
            raise RuntimeError
        except RuntimeError:
            frame_summary = traceback.extract_stack(limit=3)[0]
            self.name += frame_summary.name
            self.filename = os.path.basename(frame_summary.filename)
            self.lineno = frame_summary.lineno

        indent_string = _get_indent_string()
        if _code_nest_level < _previous_nest_level:
            _logger.print(indent_string)

        _logger.print(indent_string +
            enter_string + ' ' +
            enter_format.format(self.name, self.filename, self.lineno)
        )
        _up_nest()
        self.enter_time = datetime.datetime.now()

    def __del__(self):
        if not is_enabled: return

        time = datetime.datetime.now() - self.enter_time
        _down_nest()
        _logger.print(_get_indent_string() +
            leave_string + ' ' +
            leave_format.format(self.name, self.filename, self.lineno, time)
        )

def enter(invoker: object=None):
    '''
    By calling this method when entering an execution block such as a function or method,
    outputs a entering log.
    Store the return value in some variable (such as _).
    Outputs a leaving log when leaving the scope of this variable.

    Japanese:
    関数やメソッドなどの実行ブロックに入る際にこのメソッドを呼び出す事で、開始のログを出力します。
    戻り値は何かの変数(例えば _)に格納してください。この変数のスコープを出る際に終了のログを出力します。

    Args
        invoker: The object or class that invoked this method.
            Japanese: このメソッドを呼び出したオブジェクトまたはクラス。
    
    Returns:
        An inner class object.
        Japanese: 内部クラスのオブジェクト。
    '''
    return _DebugTrace(invoker)

if is_enabled:
    from debugtrace import version
    print('DebugTrace-python ' + version.VERSION + ' -> ' + str(_logger))
    print('')
