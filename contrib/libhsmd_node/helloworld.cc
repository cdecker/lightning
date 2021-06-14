#include <iostream>
#include <napi.h>
extern "C" {
#include <libhsmd_node.h>
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
