#include <napi.h>

extern "C" {
#include <ccan/str/hex/hex.h>
#include <hsmd/libhsmd.h>

char *libhsmd_init(const char *hex_hsm_secret, const char *network_name)
{
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
	if (taken(response))
		tal_free(response);
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
		return (char *)tal_free(ctx);

	res = tal_hex(NULL, response);
	res_len = hex_str_size(tal_bytelen(response));
	res = (char *)malloc(res_len);
	hex_encode(response, tal_bytelen(response), res, res_len);

	tal_free(ctx);
	return res;
}
}

Napi::String HsmdInit(const Napi::CallbackInfo &info)
{
	Napi::Env env = info.Env();
	assert(info.Length() == 2);
	std::string secret = info[0].As<Napi::String>().ToString().Utf8Value();
	std::string network = info[1].As<Napi::String>().ToString().Utf8Value();
	char *res = libhsmd_init(secret.c_str(), network.c_str());
	Napi::String result = Napi::String::New(env, res);
	tal_free(res);
	return result;
}

Napi::String HsmdHandle(const Napi::CallbackInfo &info)
{
	Napi::Env env = info.Env();
	assert(info.Length() == 4);
	long long cap = info[0].As<Napi::Number>().Int64Value();
	std::string message = info[3].As<Napi::String>().ToString().Utf8Value();
	char *response;
	if (!info[2].IsNull()) {
		long long dbid = info[1].As<Napi::Number>().Int64Value();
		std::string peer_id =
		    info[2].As<Napi::String>().ToString().Utf8Value();
		assert(dbid != 0);
		response =
		    libhsmd_handle(cap, dbid, peer_id.c_str(), message.c_str());
	} else {
		response = libhsmd_handle(cap, 0, NULL, message.c_str());
	}
	Napi::String res = Napi::String::New(env, response);
	free(response);
	return res;
}

Napi::Object init(Napi::Env env, Napi::Object exports)
{
	exports.Set(Napi::String::New(env, "Init"),
		    Napi::Function::New(env, HsmdInit));
	exports.Set(Napi::String::New(env, "Handle"),
		    Napi::Function::New(env, HsmdHandle));
	return exports;
};

NODE_API_MODULE(libhsmd, init);
