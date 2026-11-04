import {
  pipeline,
  env,
  InterruptableStoppingCriteria,
} from "./vendor/transformers-3.8.1/transformers-3.8.1.mjs";
env.allowLocalModels = false;
env.useBrowserCache = true;
env.backends.onnx.wasm.numThreads = 1;
env.backends.onnx.wasm.proxy = false;
env.backends.onnx.wasm.wasmPaths = new URL(
  "./vendor/transformers-3.8.1/",
  import.meta.url,
).href;
let model = null;
const stopping = new InterruptableStoppingCriteria();
self.onmessage = async ({ data }) => {
  const { id, cmd } = data;
  try {
    if (cmd === "load") {
      if (
        data.record?.model_repo !== "onnx-community/Qwen2.5-0.5B-Instruct" ||
        data.record?.revision !== "22942cb7d7ba4cc81bb4673549ca4d4614469b5e"
      )
        throw Error("Unsupported model");
      model = await pipeline("text-generation", data.record.model_repo, {
        device: "wasm",
        dtype: "q4",
        revision: "22942cb7d7ba4cc81bb4673549ca4d4614469b5e",
        progress_callback: (p) => {
          if (p.status === "progress")
            postMessage({ progress: p.progress / 100 });
        },
      });
      postMessage({ id, ok: true, result: "ready" });
    }
    if (cmd === "generate") {
      if (!model) throw Error("AI not ready");
      stopping.reset();
      const out = await model(data.messages, {
        max_new_tokens: Math.min(data.max_tokens || 96, 128),
        do_sample: false,
        return_full_text: false,
        stopping_criteria: stopping,
      });
      let text = out[0].generated_text;
      if (Array.isArray(text)) text = text.at(-1).content;
      postMessage({ id, ok: true, result: { text } });
    }
    if (cmd === "stop") stopping.interrupt();
    if (cmd === "unload") {
      await model?.dispose();
      model = null;
      postMessage({ id, ok: true, result: true });
    }
  } catch (e) {
    postMessage({ id, ok: false, error: e.message });
  }
};
