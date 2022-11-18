import json
from pathlib import Path
from importlib import resources
from msggen.model import Method, CompositeField, Service
import logging


def load_jsonrpc_method(name, schema_dir: Path):
    """Load a method based on the file naming conventions for the JSON-RPC.
    """
    base_path = schema_dir
    req_file = base_path / f"{name.lower()}.request.json"
    resp_file = base_path / f"{name.lower()}.schema.json"
    request = CompositeField.from_js(json.load(open(req_file)), path=name)
    response = CompositeField.from_js(json.load(open(resp_file)), path=name)

    # Normalize the method request and response typename so they no
    # longer conflict.
    request.typename += "Request"
    response.typename += "Response"


methods = {
    "Getinfo": {},
    "ListPeers": {},
    "ListFunds": {},
    "SendPay": {},
    "ListChannels": {},
    "AddGossip": {},
    "AutoCleanInvoice": {},
    "CheckMessage": {},
    "Close": {},
    "Connect": {},
    "CreateInvoice": {},
    "Datastore": {},
    "CreateOnion": {},
    "DelDatastore": {},
    "DelExpiredInvoice": {},
    "DelInvoice": {},
    "Invoice": {},
    "ListDatastore": {},
    "ListInvoices": {},
    "SendOnion": {},
    "ListSendPays": {},
    "ListTransactions": {},
    "Pay": {},
    "ListNodes": {},
    "WaitAnyInvoice": {},
    "WaitInvoice": {},
    "WaitSendPay": {},
    "NewAddr": {},
    "Withdraw": {},
    "KeySend": {},
    "FundPsbt": {},
    "SendPsbt": {},
    "SignPsbt": {},
    "UtxoPsbt": {},
    "TxDiscard": {},
    "TxPrepare": {},
    "TxSend": {},
    # "decodepay": {},
    # "decode": {},
    # "delpay": {},
    # "disableoffer": {},
    "Disconnect": {},
    "Feerates": {},
    # "fetchinvoice": {},
    "FundChannel_Cancel": {
        "name": "FundChannelCancel"
    },
    "FundChannel_Complete": {
        "name": "FundChannelComplete"
    },
    "FundChannel": {},
    "FundChannel_Start": {
        "name": "FundChannelStart"
    },
    # "funderupdate": {},
    # "getlog": {},
    "GetRoute": {},
    "ListForwards": {},
    # "listoffers": {},
    "ListPays": {},
    # "multifundchannel": {},
    # "multiwithdraw": {},
    # "offerout": {},
    # "offer": {},
    # "openchannel_abort": {},
    # "openchannel_bump": {},
    # "openchannel_init": {},
    # "openchannel_signed": {},
    # "openchannel_update": {},
    # "parsefeerate": {},
    "Ping": {},
    # "plugin": {},
    # "reserveinputs": {},
    # "sendcustommsg": {},
    # "sendinvoice": {},
    # "sendonionmessage": {},
    # "setchannelfee": {},
    "SetChannel": {},
    "SignMessage": {},
    # "unreserveinputs": {},
    # "waitblockheight": {},
    # "ListConfigs": {},
    # "check",  # No point in mapping this one
    "Stop": {},
    # "notifications",  # No point in mapping this
    # "help": {},
}


def load_jsonrpc_service():
    schema = json.load(resources.open_text("msggen", "schema.json"))
    methods = []
    for name, m in schema['methods'].items():
        logging.info(f"Parsing schema for {name}")
        request = CompositeField.from_js(m['request'], path=name)
        response = CompositeField.from_js(m['response'], path=name)

        # Normalize the method request and response typename so they no
        # longer conflict.
        request.typename += "Request"
        response.typename += "Response"

        methods.append(Method(
            name,
            request=request,
            response=response,
        ))

    service = Service(name="Node", methods=methods)
    service.includes = ['primitives.proto']  # Make sure we have the primitives included.
    return service
