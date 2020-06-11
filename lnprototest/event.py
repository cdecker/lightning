#! /usr/bin/python3
import traceback
from pyln.proto.message import SubtypeType, Message
import os.path
import io
import functools
from .errors import SpecFileError, EventError
from .namespace import event_namespace
from .utils import check_hex
from typing import Optional, Dict, Union, Callable, Any, TYPE_CHECKING
if TYPE_CHECKING:
    # Otherwise a circular dependency
    from .runner import Runner, Conn


# Type for arguments: either strings, or functions to call at runtime
ResolvableStr = Union[str, Callable[['Runner', 'Event', str], str]]
ResolvableInt = Union[int, Callable[['Runner', 'Event', str], int]]
Resolvable = Union[Any, Callable[['Runner', 'Event', str], Any]]


class Event(object):
    """Abstract base class for events."""
    def __init__(self):
        # From help(traceback.extract_stack):
        #   Each item in the list is a quadruple (filename,
        #   line number, function name, text), and the entries are in order
        #   from oldest to newest stack frame.
        self.name = 'unknown'
        for s in reversed(traceback.extract_stack()):
            # Ignore constructor calls, like this one.
            if s[2] != '__init__':
                self.name = "{}:{}:{}".format(type(self).__name__,
                                              os.path.basename(s[0]), s[1])
                break
        self.done = False

    def action(self, runner: 'Runner') -> None:
        if runner.config.getoption('verbose'):
            print("# running {}:".format(self))
        self.done = True

    def num_undone(self) -> int:
        """Number of actions to be done in this event; usually 1."""
        if self.done:
            return 0
        return 1

    def resolve_arg(self, fieldname: str, runner: 'Runner', arg: Resolvable) -> Any:
        """If this is a string, return it, otherwise call it to get result"""
        if callable(arg):
            return arg(runner, self, fieldname)
        else:
            return arg

    def resolve_args(self, runner: 'Runner', kwargs: Dict[str, Resolvable]) -> Dict[str, Any]:
        """Take a dict of args, replace callables with their return values"""
        ret: Dict[str, str] = {}
        for field, str_or_func in kwargs.items():
            ret[field] = self.resolve_arg(field, runner, str_or_func)
        return ret

    def __repr__(self):
        return self.name


class PerConnEvent(Event):
    """An event which takes a connprivkey arg"""
    def __init__(self, connprivkey: Optional[str]):
        super().__init__()
        self.connprivkey = connprivkey

    def find_conn(self, runner: 'Runner') -> 'Conn':
        """Helper for events which have a connection"""
        conn = runner.find_conn(self.connprivkey)
        if conn is None:
            if self.connprivkey is None:
                # None means "same as last used/created"
                raise SpecFileError(self, "No current connection")
            else:
                raise SpecFileError(self, "Unknown connection {}".format(self.connprivkey))
        return conn


class Connect(Event):
    """Connect to the runner, as if a node with private key connprivkey"""
    def __init__(self, connprivkey: str):
        self.connprivkey = connprivkey
        super().__init__()

    def action(self, runner: 'Runner') -> None:
        super().action(runner)
        if runner.find_conn(self.connprivkey):
            raise SpecFileError(self, "Already have connection to {}"
                                .format(self.connprivkey))
        runner.connect(self, self.connprivkey)


class Disconnect(PerConnEvent):
    """Disconnect the runner from the node whose private key is connprivkey: default is last connection specified"""
    def __init__(self, connprivkey: Optional[str] = None):
        super().__init__(connprivkey)

    def action(self, runner: 'Runner') -> None:
        super().action(runner)
        runner.disconnect(self, self.find_conn(runner))


class Msg(PerConnEvent):
    """Feed a message to the runner (via optional given connection)"""
    def __init__(self, msgtypename: str, connprivkey: Optional[str] = None,
                 **kwargs: ResolvableStr):
        super().__init__(connprivkey)
        self.msgtype = event_namespace.get_msgtype(msgtypename)
        if not self.msgtype:
            raise SpecFileError(self, "Unknown msgtype {}".format(msgtypename))
        self.kwargs = kwargs

    def action(self, runner: 'Runner') -> None:
        super().action(runner)
        # Now we have runner, we can fill in all the message fields
        message = Message(self.msgtype, **self.resolve_args(runner, self.kwargs))
        missing = message.missing_fields()
        if missing:
            raise SpecFileError(self, "Missing fields {}".format(missing))
        binmsg = io.BytesIO()
        message.write(binmsg)
        runner.recv(self, self.find_conn(runner), binmsg.getvalue())
        msg_to_stash(runner, self, message)


class RawMsg(PerConnEvent):
    """Feed a raw binary message to the runner (via optional given connection)"""
    def __init__(self, binmsg, connprivkey: Optional[str] = None):
        super().__init__(connprivkey)
        self.message = binmsg

    def action(self, runner: 'Runner') -> None:
        super().action(runner)
        runner.recv(self, self.find_conn(runner), self.message)


class ExpectMsg(PerConnEvent):
    """Wait for a message from the runner.

Args is the (usually incomplete) message which it should match.
if_match is the function to call if it matches: should raise an
exception if it's not satisfied.  if_nomatch is the function to all if
it doesn't match: if this returns the message is ignored and we wait
for a new one.

    """
    def _default_if_match(self, msg, ignore):
        pass

    def _default_if_nomatch(self, binmsg, errstr, ignore):
        raise EventError(self, "Runner gave bad msg {}: {}".format(binmsg, errstr))

    def __init__(self, msgtypename, if_match=_default_if_match,
                 if_nomatch=_default_if_nomatch, if_arg=None, connprivkey: Optional[str] = None, **kwargs):
        super().__init__(connprivkey)
        self.msgtype = event_namespace.get_msgtype(msgtypename)
        if not self.msgtype:
            raise SpecFileError(self, "Unknown msgtype {}".format(msgtypename))
        self.kwargs = kwargs
        self.if_match = if_match
        self.if_nomatch = if_nomatch
        self.if_arg = if_arg

    # FIXME: Put helper in Message?
    @staticmethod
    def _cmp_msg(subtype: SubtypeType,
                 fieldsa: Dict[str, Any],
                 fieldsb: Dict[str, Any],
                 prefix="") -> Optional[str]:
        """a is a subset of b"""
        for f in fieldsa:
            if f not in fieldsb:
                return "Missing field {}".format(prefix + f)
            fieldtype = subtype.find_field(f)
            if isinstance(fieldtype, SubtypeType):
                ret = ExpectMsg._cmp_msg(fieldtype, fieldsa[f], fieldsb[f],
                                         prefix + f + ".")
                if ret:
                    return ret
            else:
                if fieldsa[f] != fieldsb[f]:
                    return "Field {}: {} != {}".format(f,
                                                       fieldtype.fieldtype.val_to_str(fieldsb[f], fieldsb),
                                                       fieldtype.fieldtype.val_to_str(fieldsa[f], fieldsa))
        return None

    def message_match(self, runner: 'Runner', msg: Message) -> Optional[str]:
        """Does this message match what we expect?"""
        if msg.messagetype != self.msgtype:
            return "Expected {}, got {}".format(self.msgtype,
                                                msg.messagetype)
        partmessage = Message(self.msgtype, **self.resolve_args(runner, self.kwargs))
        ret = self._cmp_msg(msg.messagetype, partmessage.fields, msg.fields)
        if ret is None:
            self.if_match(self, msg, self.if_arg)
            msg_to_stash(runner, self, msg)
        return ret

    def action(self, runner: 'Runner') -> None:
        super().action(runner)
        while True:
            binmsg = runner.get_output_message(self.find_conn(runner))
            if binmsg is None:
                # Dummyrunner never returns output, so pretend it worked.
                if runner._is_dummy():
                    return
                raise EventError(self, "Did not receive a message from runner")

            # Might be completely unknown to namespace.
            try:
                msg = Message.read(event_namespace, io.BytesIO(binmsg))
            except ValueError as ve:
                self.if_nomatch(self, binmsg, str(ve), self.if_arg)
                continue

            err = self.message_match(runner, msg)
            if err:
                self.if_nomatch(self, binmsg, err, self.if_arg)
                # If that returns, it means we try again.
                continue

            break


class Block(Event):
    """Generate a block, at blockheight, with optional txs.

    """
    def __init__(self, blockheight, number=1, txs=[]):
        super().__init__()
        self.blockheight = blockheight
        self.number = number
        self.txs = txs

    def action(self, runner: 'Runner') -> None:
        super().action(runner)
        # Oops, did they ask us to produce a block with no predecessor?
        if runner.getblockheight() + 1 < self.blockheight:
            raise SpecFileError(self, "Cannot generate block #{} at height {}".
                                format(self.blockheight, runner.getblockheight()))

        # Throw away blocks we're replacing.
        if runner.getblockheight() >= self.blockheight:
            runner.trim_blocks(self.blockheight - 1)

        # Add new one
        runner.add_blocks(self, self.txs, self.number)
        assert runner.getblockheight() == self.blockheight - 1 + self.number


class ExpectTx(Event):
    """Expect the runner to broadcast a transaction

    """
    def __init__(self, txid: ResolvableStr):
        super().__init__()
        self.txid = txid

    def action(self, runner: 'Runner') -> None:
        super().action(runner)
        runner.expect_tx(self, self.resolve_arg('txid', runner, self.txid))


class FundChannel(PerConnEvent):
    """Tell the runner to fund a channel with this peer."""
    def __init__(self, amount, utxo, feerate, connprivkey: Optional[str] = None):
        super().__init__(connprivkey)
        self.amount = amount
        parts = utxo.partition('/')
        self.utxo = (check_hex(parts[0], 64), int(parts[2]))
        self.feerate = feerate

    def action(self, runner: 'Runner') -> None:
        super().action(runner)
        runner.fundchannel(self,
                           self.find_conn(runner),
                           self.amount, self.utxo[0],
                           self.utxo[1], self.feerate)


class Invoice(Event):
    def __init__(self, amount: int, preimage: ResolvableStr):
        super().__init__()
        self.preimage = preimage
        self.amount = amount

    def action(self, runner: 'Runner') -> None:
        super().action(runner)
        runner.invoice(self, self.amount,
                       check_hex(self.resolve_arg('preimage', runner, self.preimage), 64))


class AddHtlc(PerConnEvent):
    def __init__(self, amount: int, preimage: ResolvableStr, connprivkey: Optional[str] = None):
        super().__init__(connprivkey)
        self.preimage = preimage
        self.amount = amount

    def action(self, runner: 'Runner') -> None:
        super().action(runner)
        runner.addhtlc(self, self.find_conn(runner),
                       self.amount,
                       check_hex(self.resolve_arg('preimage', runner, self.preimage), 64))


class ExpectError(PerConnEvent):
    def __init__(self, connprivkey: Optional[str] = None):
        super().__init__(connprivkey)

    def action(self, runner: 'Runner') -> None:
        super().action(runner)
        error = runner.check_error(self, self.find_conn(runner))
        if error is None:
            # We ignore lack of responses from dummyrunner
            if not runner._is_dummy():
                raise EventError(self, "No error found")


class CheckEq(Event):
    """Event to check a condition is true"""
    def __init__(self, a: ResolvableStr, b: ResolvableStr):
        super().__init__()
        self.a = a
        self.b = b

    def action(self, runner: 'Runner') -> None:
        super().action(runner)
        a = self.resolve_arg('a', runner, self.a)
        b = self.resolve_arg('b', runner, self.b)
        if a != b:
            raise EventError(self, "{} != {}".format(a, b))


def msg_to_stash(runner: 'Runner', event: Event, msg: Message):
    """ExpectMsg and Msg save every field to the stash, in order"""
    fields = {}
    # Convert to strings.
    for f in msg.fields:
        fieldtype = msg.messagetype.find_field(f)
        fields[f] = fieldtype.fieldtype.val_to_str(msg.fields[f], msg.fields)
    stash = runner.get_stash(event, type(event).__name__, [])
    stash.append((msg.messagetype.name, fields))
    runner.add_stash(type(event).__name__, stash)


def field_from_stash(event: Event, runner: 'Runner', stashname: str, var: str) -> str:
    """Get field from stash for ExpectMsg or Nsg"""
    stash = runner.get_stash(event, stashname)
    if '.' in var:
        prevname, _, var = var.partition('.')
    else:
        prevname = ''
    for name, d in reversed(stash):
        if prevname == '' or name == prevname:
            if var not in d:
                raise SpecFileError(event, '{}: {} did not receive a {}'
                                    .format(stashname, prevname, var))
            return d[var]
    raise SpecFileError(event, '{}: have no prior {}'.format(stashname, prevname))


def _get_stash(stashname: str,
               # This is the signature which Msg() expects for callable values:
               runner: 'Runner',
               event: Event):
    return runner.get_stash(event, stashname)


def _get_stashed_field(stashname: str,
                       fieldname: Optional[str],
                       casttype: Any,
                       # This is the signature which Msg() expects for callable values:
                       runner: 'Runner',
                       event: Event,
                       field: str) -> Any:
    # If they don't specify fieldname, it's same as this field.
    if fieldname is None:
        fieldname = field
    strval = field_from_stash(event, runner, stashname, fieldname)
    try:
        return casttype(strval)
    except ValueError:
        raise SpecFileError(event, "{}.{} is {}, not a valid {}".format(stashname, fieldname, strval, casttype))


def stashed(stashname: str) -> functools.partial:
    """Use an entry from the stash as a field value at runtime"""
    return functools.partial(_get_stash, stashname)


def rcvd(fieldname: Optional[str] = None, casttype: Any = str) -> functools.partial:
    """Use previous ExpectMsg field (as string)

fieldname can be [msg].[field] or just [field] for last ExpectMsg

    """
    return functools.partial(_get_stashed_field, 'ExpectMsg', fieldname, casttype)


def sent(fieldname: Optional[str] = None, casttype: Any = str) -> functools.partial:
    """Use previous Msg field (as string)

fieldname can be [msg].[field] or just [field] for last Msg

    """
    return functools.partial(_get_stashed_field, 'Msg', fieldname, casttype)


def msat(sats: ResolvableInt) -> ResolvableInt:
    def _msat(runner: 'Runner', event: Event, field: str) -> int:
        if callable(sats):
            return 1000 * sats(runner, event, field)
        else:
            return 1000 * sats
    return _msat
