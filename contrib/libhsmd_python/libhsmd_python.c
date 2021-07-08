#include <Python.h>
#include <ccan/str/hex/hex.h>
#include <common/setup.h>
#include <common/status_levels.h>
#include <hsmd/libhsmd.h>
#include <libhsmd_python.h>

char *init(char *hex_hsm_secret, char *network_name) {
	const struct bip32_key_version *key_version;
	struct secret sec;
	u8 *response;
	common_setup(NULL);
	if (sodium_init() == -1) {
		fprintf(
		    stderr,
		    "Could not initialize libsodium. Maybe not enough entropy"
		    " available ?");
		return NULL;
	}

	wally_init(0);
	secp256k1_ctx = wally_get_secp_context();

	sodium_mlock(&sec, sizeof(sec));
	if (!hex_decode(hex_hsm_secret, strlen(hex_hsm_secret), sec.data,
			sizeof(sec.data))) {
		fprintf(stderr,
			"Expected hex_hsm_secret of length 64, got %zu\n",
			strlen(hex_hsm_secret));
		return NULL;
	}

	/* Look up chainparams by their name */
	chainparams = chainparams_for_network(network_name);
	if (chainparams == NULL) {
		fprintf(stderr, "Could not find chainparams for network %s\n",
			network_name);
		return NULL;
	}

	key_version = &chainparams->bip32_key_version;

	response = hsmd_init(sec, *key_version);
	sodium_munlock(&sec, sizeof(sec));

	char *res = tal_hex(NULL, response);
	tal_free(response);
	return res;
}

char *handle(long long cap, long long dbid, char *peer_id, char *hexmsg) {
	size_t res_len;
	u8 *response, *request;
	char *res;
	struct hsmd_client *client;
	struct node_id *peer = NULL;
	request = tal_hexdata(tmpctx, hexmsg, strlen(hexmsg));
	if (peer_id != NULL) {
		peer = tal(tmpctx, struct node_id);
		node_id_from_hexstr(peer_id, strlen(peer_id), peer);
		client = hsmd_client_new_peer(tmpctx, cap, dbid, peer, NULL);
	} else {
		client = hsmd_client_new_main(tmpctx, cap, NULL);
	}
	response = hsmd_handle_client_message(tmpctx, client, request);
	if (response == NULL) {
		clean_tmpctx();
		return NULL;
	}

	res_len = hex_str_size(tal_bytelen(response));
	res = malloc(res_len);
	hex_encode(response, tal_bytelen(response), res, res_len);

	clean_tmpctx();
	return res;
}

/* When running as a subdaemon controlled by lightningd the hsmd will
 * report logging, debugging information and crash reports to
 * lightningd via the status socket, using the wire protocol used in
 * LN more generally. This is done so lightningd can print add the
 * messages to its own logs, presenting a unified view of what is
 * happening.
 *
 * When using libhsmd not as a subdaemon controlled by lightningd we
 * cannot make use of the communication primitives we used in that
 * context. For this reason libhsmd defers the selection of actual
 * primitives to link time, and here we provide simple ones that just
 * print to stdout, as alternatives to the status wire protocol ones.
 */
static void pylog(enum log_level  level, char *msg) {

    static PyObject *logging = NULL;
    static PyObject *string = NULL;

    // import logging module on demand
    if (logging == NULL){
        logging = PyImport_ImportModuleNoBlock("logging");
        if (logging == NULL)
            PyErr_SetString(PyExc_ImportError,
                "Could not import module 'logging'");
    }

    // build msg-string
    string = Py_BuildValue("s", msg);

    // call function depending on loglevel
    switch (level) {
    case LOG_INFORM:
	    PyObject_CallMethod(logging, "info", "O", string);
	    break;

    case LOG_UNUSUAL:
	    PyObject_CallMethod(logging, "warn", "O", string);
	    break;

    case LOG_BROKEN:
	    PyObject_CallMethod(logging, "error", "O", string);
	    break;

    case LOG_DBG:
	    PyObject_CallMethod(logging, "debug", "O", string);
	    break;

    case LOG_IO_IN:
    case LOG_IO_OUT:
	    /* Ignore io logging */
	    break;
    }
    Py_DECREF(string);
}

u8 *hsmd_status_bad_request(struct hsmd_client *client, const u8 *msg, const char *error)
{
	pylog(LOG_BROKEN, (char *)error);
	return NULL;
}

void hsmd_status_fmt(enum log_level level, const struct node_id *peer,
		     const char *fmt, ...)
{
	va_list ap;
	char *msg, *peer_msg;
	va_start(ap, fmt);
	msg = tal_vfmt(NULL, fmt, ap);
	va_end(ap);

	if (peer != NULL) {
		va_start(ap, fmt);
		peer_msg = tal_fmt(msg, "%s: %s", node_id_to_hexstr(msg, peer), msg);
		va_end(ap);
		pylog(level, peer_msg);
	} else {
		pylog(level, msg);
	}
	tal_free(msg);
}

void hsmd_status_failed(enum status_failreason reason, const char *fmt, ...)
{
	char *msg;
	va_list ap;
	va_start(ap, fmt);
	msg = tal_vfmt(NULL, fmt, ap);
	va_end(ap);
	pylog(LOG_BROKEN, msg);
	tal_free(msg);
	exit(0x80 | (reason & 0xFF));
}
