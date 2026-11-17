# LogiOn RKLLM 테스트 서버 (stdlib only: flask/fastapi 없이, sudo 없이)
# 구조체 정의는 rknn-llm 1.3.0 examples/rkllm_server_demo/flask_server.py 와 동일.
# POST /v1/chat/completions  {"messages":[{"role":"system",...},{"role":"user",...}], "max_tokens":64}
import ctypes, sys, os, json, time, threading, argparse
from http.server import HTTPServer, BaseHTTPRequestHandler

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--lib", required=True)
ap.add_argument("--port", type=int, default=8090)
ap.add_argument("--max_context", type=int, default=256)
args = ap.parse_args()

lib = ctypes.CDLL(args.lib)
H = ctypes.c_void_p

class ExtendParam(ctypes.Structure):
    _fields_ = [("base_domain_id", ctypes.c_int32), ("embed_flash", ctypes.c_int8), ("enabled_cpus_num", ctypes.c_int8),
                ("enabled_cpus_mask", ctypes.c_uint32), ("n_batch", ctypes.c_uint8), ("use_cross_attn", ctypes.c_int8),
                ("reserved", ctypes.c_uint8 * 104)]
class Param(ctypes.Structure):
    _fields_ = [("model_path", ctypes.c_char_p), ("max_context_len", ctypes.c_int32), ("max_new_tokens", ctypes.c_int32),
                ("top_k", ctypes.c_int32), ("n_keep", ctypes.c_int32), ("top_p", ctypes.c_float), ("temperature", ctypes.c_float),
                ("repeat_penalty", ctypes.c_float), ("frequency_penalty", ctypes.c_float), ("presence_penalty", ctypes.c_float),
                ("mirostat", ctypes.c_int32), ("mirostat_tau", ctypes.c_float), ("mirostat_eta", ctypes.c_float),
                ("skip_special_token", ctypes.c_bool), ("ignore_eos_token", ctypes.c_bool), ("is_async", ctypes.c_bool),
                ("extend_param", ExtendParam)]
class EmbedInput(ctypes.Structure):
    _fields_ = [("embed", ctypes.POINTER(ctypes.c_float)), ("n_tokens", ctypes.c_size_t)]
class TokenInput(ctypes.Structure):
    _fields_ = [("input_ids", ctypes.POINTER(ctypes.c_int32)), ("n_tokens", ctypes.c_size_t)]
class ImageInput(ctypes.Structure):
    _fields_ = [("image_embed", ctypes.POINTER(ctypes.c_float)), ("n_image_tokens", ctypes.c_size_t), ("n_image", ctypes.c_size_t),
                ("image_start", ctypes.c_char_p), ("image_end", ctypes.c_char_p), ("image_content", ctypes.c_char_p),
                ("image_width", ctypes.c_size_t), ("image_height", ctypes.c_size_t)]
class VideoInput(ctypes.Structure):
    _fields_ = [("video_embed", ctypes.POINTER(ctypes.c_float)), ("n_frame_tokens", ctypes.c_size_t), ("n_frame_per_video", ctypes.c_size_t),
                ("n_video", ctypes.c_size_t), ("video_start", ctypes.c_char_p), ("video_end", ctypes.c_char_p),
                ("video_content", ctypes.c_char_p), ("frame_width", ctypes.c_size_t), ("frame_height", ctypes.c_size_t)]
class MMInput(ctypes.Structure):
    _fields_ = [("prompt", ctypes.c_char_p), ("image", ImageInput), ("video", VideoInput)]
class InputUnion(ctypes.Union):
    _fields_ = [("prompt_input", ctypes.c_char_p), ("embed_input", EmbedInput), ("token_input", TokenInput), ("multimodal_input", MMInput)]
class Input(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("role", ctypes.c_char_p), ("enable_thinking", ctypes.c_bool), ("input_type", ctypes.c_int), ("u", InputUnion)]
class SamplingParam(ctypes.Structure):
    _fields_ = [("top_k", ctypes.c_int32), ("top_p", ctypes.c_float), ("temperature", ctypes.c_float), ("repeat_penalty", ctypes.c_float),
                ("frequency_penalty", ctypes.c_float), ("presence_penalty", ctypes.c_float), ("mirostat", ctypes.c_int32),
                ("mirostat_tau", ctypes.c_float), ("mirostat_eta", ctypes.c_float)]
class InferParam(ctypes.Structure):
    _fields_ = [("mode", ctypes.c_int), ("lora_params", ctypes.c_void_p), ("prompt_cache_params", ctypes.c_void_p),
                ("sampling_params", ctypes.POINTER(SamplingParam)), ("keep_history", ctypes.c_int), ("max_new_tokens", ctypes.c_int32)]
class HiddenRes(ctypes.Structure):
    _fields_ = [("hidden_states", ctypes.POINTER(ctypes.c_float)), ("embd_size", ctypes.c_int), ("num_tokens", ctypes.c_int)]
class LogitsRes(ctypes.Structure):
    _fields_ = [("logits", ctypes.POINTER(ctypes.c_float)), ("vocab_size", ctypes.c_int), ("num_tokens", ctypes.c_int)]
class Perf(ctypes.Structure):
    _fields_ = [("prefill_time_ms", ctypes.c_float), ("prefill_tokens", ctypes.c_int), ("generate_time_ms", ctypes.c_float),
                ("generate_tokens", ctypes.c_int), ("memory_usage_mb", ctypes.c_float)]
class Result(ctypes.Structure):
    _fields_ = [("text", ctypes.c_char_p), ("token_id", ctypes.c_int), ("last_hidden_layer", HiddenRes), ("logits", LogitsRes), ("perf", Perf)]

ResCB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(Result), ctypes.c_void_p, ctypes.c_int)
TokCB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int32, ctypes.POINTER(ctypes.c_int32), ctypes.c_int32)
EmbCB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int32), ctypes.c_uint64, ctypes.c_void_p, ctypes.c_uint64)
class Callback(ctypes.Structure):
    _fields_ = [("result_callback", ResCB), ("result_userdata", ctypes.c_void_p), ("tokenizer_callback", TokCB),
                ("tokenizer_userdata", ctypes.c_void_p), ("embed_callback", EmbCB), ("embed_userdata", ctypes.c_void_p)]

state = {"buf": b"", "perf": None, "err": False}
def _cb(res, ud, st):
    if st == 0 and res and res.contents.text:          # RUN_NORMAL
        state["buf"] += res.contents.text
    elif st == 2:                                       # RUN_FINISH
        if res:
            p = res.contents.perf
            state["perf"] = {"prefill_tokens": p.prefill_tokens, "prefill_ms": round(p.prefill_time_ms, 1),
                             "generate_tokens": p.generate_tokens, "generate_ms": round(p.generate_time_ms, 1),
                             "mem_mb": round(p.memory_usage_mb, 1)}
    elif st == 3:
        state["err"] = True
    return 0
cb_fn = ResCB(_cb)

p = Param()
p.model_path = args.model.encode()
p.max_context_len = args.max_context
p.max_new_tokens = 64
p.top_k = 1; p.n_keep = -1; p.top_p = 0.9; p.temperature = 0.8
p.repeat_penalty = 1.1; p.frequency_penalty = 0.0; p.presence_penalty = 0.0
p.mirostat = 0; p.mirostat_tau = 5.0; p.mirostat_eta = 0.1
p.skip_special_token = True; p.ignore_eos_token = False; p.is_async = False
p.extend_param.base_domain_id = 0; p.extend_param.embed_flash = 1; p.extend_param.n_batch = 1
p.extend_param.use_cross_attn = 0; p.extend_param.enabled_cpus_num = 4
p.extend_param.enabled_cpus_mask = (1 << 4) | (1 << 5) | (1 << 6) | (1 << 7)

cbs = Callback(); cbs.result_callback = cb_fn; cbs.tokenizer_callback = TokCB(); cbs.embed_callback = EmbCB()
handle = H()
lib.rkllm_init.argtypes = [ctypes.POINTER(H), ctypes.POINTER(Param), ctypes.POINTER(Callback)]
lib.rkllm_run.argtypes = [H, ctypes.POINTER(Input), ctypes.POINTER(InferParam), ctypes.c_void_p]
lib.rkllm_set_chat_template.argtypes = [H, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
ret = lib.rkllm_init(ctypes.byref(handle), ctypes.byref(p), ctypes.byref(cbs))
if ret != 0:
    print("rkllm init failed", ret, flush=True); sys.exit(1)
print("rkllm init success", flush=True)

cur_sys = [None]
lock = threading.Lock()

MODEL_NAME = os.path.basename(args.model).rsplit(".", 1)[0]

def infer(system, user, max_new, top_k=1, repeat_penalty=1.1):
    if system != cur_sys[0]:
        # Qwen2.5 chat_template 과 동일 (PC: tokenizer.apply_chat_template(..., add_generation_prompt=True))
        r = lib.rkllm_set_chat_template(handle, f"<|im_start|>system\n{system}<|im_end|>\n".encode(),
                                        b"<|im_start|>user\n", b"<|im_end|>\n<|im_start|>assistant\n")
        print("set_chat_template ret", r, flush=True)
        cur_sys[0] = system
    state.update(buf=b"", perf=None, err=False)
    inp = Input(); inp.role = b"user"; inp.enable_thinking = False; inp.input_type = 0
    inp.prompt_input = user.encode()
    sp = SamplingParam(top_k=top_k, top_p=0.9, temperature=0.8, repeat_penalty=repeat_penalty, frequency_penalty=0.0,
                       presence_penalty=0.0, mirostat=0, mirostat_tau=5.0, mirostat_eta=0.1)
    ip = InferParam(); ip.mode = 0; ip.keep_history = 0; ip.max_new_tokens = max_new
    ip.sampling_params = ctypes.pointer(sp)
    t = time.perf_counter()
    lib.rkllm_run(handle, ctypes.byref(inp), ctypes.byref(ip), None)
    ms = (time.perf_counter() - t) * 1000
    return state["buf"].decode("utf-8", "replace"), ms, state["perf"], state["err"]

class Hd(BaseHTTPRequestHandler):
    # 요청은 한 번에 하나씩 처리한다 (HTTPServer 는 단일 스레드). 동시에 온 요청은 소켓에서 차례를 기다린다.
    def _json(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"status": "ok", "model": MODEL_NAME, "max_context": args.max_context})
        else:
            self.send_error(404)
    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_error(404); return
        try:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            msgs = body["messages"]
            system = next((m["content"] for m in msgs if m["role"] == "system"), "")
            user = [m["content"] for m in msgs if m["role"] == "user"][-1]
        except Exception as e:
            self._json(400, {"error": f"bad request: {e}"}); return
        with lock:
            out, ms, perf, err = infer(system, user, int(body.get("max_tokens", 64)),
                                       int(body.get("top_k", 1)), float(body.get("repeat_penalty", 1.1)))
        self._json(200, {"choices": [{"message": {"role": "assistant", "content": out}}], "server_ms": round(ms, 1),
                         "perf": perf, "error": err})
    def log_message(self, *a):
        pass

print(f"listening 127.0.0.1:{args.port}", flush=True)
try:
    HTTPServer(("127.0.0.1", args.port), Hd).serve_forever()
finally:
    lib.rkllm_destroy(handle)
