#!/usr/bin/env python3
"""Plugin that queues transactions

Used to test restarts / crashes while HTLCs were accepted, but not yet
settled/forwarded/

"""
from lightning import Plugin, RpcError
from collections import deque
import random

plugin = Plugin()

THRESHOLD = 100000  # Msats below which we exclude channels from
                    # re-consideration
MAX_PATHS = 4
MIN_WINDOW = 100


def try_payment_on_path(plugin, best_route_index, amount, destination,
                        payment_hash, request):
    """ update inflight and attempt transaction on specified route
    """
    route_info = plugin.routes_in_use[destination][best_route_index]
    route_info["amount_inflight"] += amount
    plugin.log("amount in flight: {} on route {}, window: {}".format(
        route_info["amount_inflight"], 
        best_route_index, 
        route_info["window"]
    ))

    plugin.payment_hash_to_route[payment_hash] = best_route_index
    print("attempting to send payment", payment_hash,
          "on route ", route_info["route"])
    
    plugin.payment_hash_to_request[payment_hash] = request
    plugin.rpc.sendpay(route_info["route"], payment_hash)


def send_more_transactions(plugin, destination, route_index):
    """send more transactions to this destination on this route because some
    window just became available

    """
    route_info = plugin.routes_in_use[destination][route_index]
    slack = route_info["window"] - route_info["amount_inflight"]
    while len(plugin.queue.get(destination, [])) > 0:
        oldest_invoice = plugin.queue[destination][0]['invoice']
        oldest_request = plugin.queue[destination][0]['request']
        oldest_payment = plugin.rpc.decodepay(oldest_invoice)
        amount = oldest_payment['msatoshi']
        payment_hash = oldest_payment['payment_hash']

        if amount <= slack:
            plugin.queue[destination].popleft()
            try_payment_on_path(plugin, route_index, amount,
                                destination, payment_hash, oldest_request)
        else:
            plugin.log("no more slack to dest {} on route {}".format(
                destination, route_index
            ))
            break


@plugin.subscribe("sendpay_success")
def handle_sendpay_success(plugin, sendpay_success, **kwargs):
    """when a payment successfully completes on any route, update amount
    inflight, increase window and send more payments on that route

    """
    plugin.log(
        "sendpay_success recorded, id: {},payment_hash: {}".format(
            sendpay_success['id'],
            sendpay_success['payment_hash']
        )
    )

    # update inflight
    destination = sendpay_success['destination']
    amount = sendpay_success['msatoshi']
    payment_hash = sendpay_success['payment_hash']

    # set result
    try:
        plugin.payment_hash_to_request[payment_hash].set_result(sendpay_success)
        del plugin.payment_hash_to_request[payment_hash]
    except KeyError:
        plugin.log("unable to set result for payment hash: {}".format(
                payment_hash
            )
        )

    # update inflight/route windows
    try:
        route_index = plugin.payment_hash_to_route[payment_hash]
        route_info = plugin.routes_in_use[destination][route_index]
        route_info["amount_inflight"] -= amount
        plugin.log("amount in flight: {}".format(route_info["amount_inflight"]))

        # update window
        summation = 0
        for routes in plugin.routes_in_use[destination]:
            summation += routes["window"]
        plugin.log("adding {} to window on route {}".format(
            plugin.alpha/summation,
            route_info["route"]
        ))

        route_info["window"] += (plugin.alpha/summation)
        plugin.log("new window is {}".format(route_info["window"]))
        del plugin.payment_hash_to_route[payment_hash]

        send_more_transactions(plugin, destination, route_index)

    except KeyError:
        plugin.log("unable to find route for payment hash: {}".format(
                payment_hash
            )
        )



@plugin.subscribe("sendpay_failure")
def handle_sendpay_failure(plugin, sendpay_failure, **kwargs):
    """when a payment fails on any route, update amount inflight and decrease
    window

    """
    plugin.log("sendpay_failure recorded, id: {},\
     payment_hash: {}".format(sendpay_failure['data']['id'],
               sendpay_failure['data']['payment_hash']))

    destination = sendpay_failure['data']['destination']
    amount = sendpay_failure['data']['msatoshi']
    payment_hash = sendpay_failure['data']['payment_hash']

    # set result
    try:
        plugin.payment_hash_to_request[payment_hash].set_result(sendpay_failure)
        del payment_hash_to_request[payment_hash]
    except KeyError:
        plugin.log("unable to set result for payment hash: {}".format(
                payment_hash
            )
        )
    # update window/inflight data
    try:
        route_index = plugin.payment_hash_to_route[payment_hash]
        route_info = plugin.routes_in_use[destination][route_index]
        route_info["amount_inflight"] -= amount
        plugin.log("amount in flight: {}".format(route_info["amount_inflight"]))

        plugin.log("removing {} from window on route {}".format(
            plugin.beta, route_info["route"]
        ))

        route_info["window"] = max(
            route_info["amount_inflight"] - plugin.beta,
            MIN_WINDOW
        )

        plugin.log("new window is {}".format(route_info["window"]))
        del plugin.payment_hash_to_route[payment_hash]
        
        send_more_transactions(plugin, destination, route_index)
    except KeyError:
        plugin.log("unable to find route for payment hash: {}".format(
                payment_hash
            )
        )




@plugin.async_method('spiderpay')
def spiderpay(plugin, invoice, request):
    """main plugin method responsible for initiating payments by finding routes
    to the destination and picking the destination with most available window

    """
    decoded = plugin.rpc.decodepay(invoice)
    destination = decoded['payee']
    amount = decoded['msatoshi']
    payment_hash = decoded['payment_hash']
    plugin.log("starting to call spiderpay for invoice {} to destination {}, "
               "for amount {} with payment hash {}".format(
                   invoice,
                   destination,
                   amount,
                   payment_hash
               ))

    invoice_request = {'invoice': invoice, 'request': request}

    # find a set of routes to the destination
    if destination not in plugin.routes_in_use:
        plugin.routes_in_use[destination] = []
        excludes = []
        print("about to find routes")

        for i in range(MAX_PATHS):
            try:
                r = plugin.rpc.getroute(
                    destination, amount,
                    riskfactor=1, cltv=9, exclude=excludes
                )

                print("found the #", i, " route: ", r)
                route_info = {
                    "route": r['route'],
                    "window": MIN_WINDOW,
                    "amount_inflight": 0
                }
                plugin.routes_in_use[destination].append(route_info)

                for c in r['route']:
                    if 'channel' in c and c['msatoshi'] < THRESHOLD:
                        excludes.append(
                            c['channel'] + '/' + str(c['direction'])
                        )
                    print("excludes: ", excludes)

            except RpcError as e:
                plugin.log("RPC Error " + str(e))
                break

    if plugin.routes_in_use[destination] == []:
        plugin.log("no routes to destination:{} for invoice {}".format(
            destination, invoice
        ))
        # should fail TODO
        return

    plugin.log("found {} routes to destination {} ".format(
        len(plugin.routes_in_use[destination]), destination
    ))

    # add this payment to the payment queue for this destination
    plugin.log("queueing the following payment: {}".format(
        payment_hash
    ))
    if destination in plugin.queue:
        plugin.queue[destination].append(invoice_request)
    else:
        plugin.queue[destination] = deque()
        plugin.queue[destination].append(invoice_request)


    # pick a random route to attempt for the payment if 
    # there is slack available on any of them
    num_paths = len(plugin.routes_in_use[destination])
    path_ordering = list(range(num_paths))
    random.shuffle(path_ordering)
    
    route_found = False
    for i in path_ordering:
        route_info = plugin.routes_in_use[destination][i]
        slack = route_info["window"] - route_info["amount_inflight"]
        if slack >= amount:
            send_more_transactions(plugin, destination, i)
            route_found = True
            break
    
    if not route_found:
        plugin.log("insufficient slack for payment: {} amount: {}".format(
            payment_hash, amount
        ))
    

@plugin.method('spider-inspect')
def inspect(plugin):
    return {
        "queue": plugin.queue,
        "routes_in_use": plugin.routes_in_use,
    }


@plugin.init()
def init(options, configuration, plugin):
    """ initializes the plugin """
    plugin.log("spiderpay.py initializing")

    # maps destination to list of paths each of which has some score
    # window corresponding to its max capacity and how much we use it
    plugin.routes_in_use = {}

    # per-destination queue at the sender of payments to be sent
    plugin.queue = {}

    # maps the payments already sent out to the route index that they were
    # sent on
    plugin.payment_hash_to_route = {}
    
    # maps the payments already sent out to their requests to set result
    # eventually
    plugin.payment_hash_to_request = {}

    # window decrease and increase factors
    plugin.beta = 1
    plugin.alpha = 10


plugin.run()
