#include <ccan/str/hex/hex.h>
#include <libhsmd_node.h>

char *libhsmd_init(const char *hex_hsm_secret, const char *network_name) {
	const struct bip32_key_version *key_version;
	struct secret sec;
	u8 *response;
	setup_locale();
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
//tal_free(response);
	return res;
}

char *libhsmd_handle(long long cap, long long dbid, const char *peer_id,
		     const char *hexmsg)
{
	const tal_t *ctx = tal_arr(NULL, u8, 0);
	size_t res_len;
	u8 *response, *request = tal_hexdata(ctx, hexmsg, strlen(hexmsg));
	char *res;
	struct hsmd_client *client;
	struct node_id *peer = NULL;
	if (peer_id != NULL) {
		peer = tal(ctx, struct node_id);
		node_id_from_hexstr(hexmsg, strlen(hexmsg), peer);
		client = hsmd_client_new_peer(ctx, cap, dbid, peer, NULL);
	} else {
		client = hsmd_client_new_main(ctx, cap, NULL);
	}
	response = hsmd_handle_client_message(NULL, client, request);
	if (response == NULL)
		return tal_free(ctx);

	res = tal_hex(NULL, response);
	res_len = hex_str_size(tal_bytelen(response));
	res = malloc(res_len);
	hex_encode(response, tal_bytelen(response), res, res_len);

	tal_free(ctx);
	return res;
}
