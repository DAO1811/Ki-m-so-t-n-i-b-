/* Local worker RPC. No external inference service, secrets, or paid API fallback. */
export async function createBrowserAssistant(worker, record, progress) {
  const pending = new Map();
  let next = 0;
  worker.onmessage = ({ data }) => {
    if (data.progress !== undefined) {
      progress({ progress: data.progress });
      return;
    }
    const job = pending.get(data.id);
    if (!job) return;
    pending.delete(data.id);
    if (data.ok) job.resolve(data.result);
    else job.reject(Error(data.error || "Bộ chạy AI chưa phản hồi."));
  };
  worker.onerror = () => {
    for (const job of pending.values())
      job.reject(
        Error(
          "Thiết bị chưa chạy được mô hình AI. Bạn vẫn dùng được tra cứu trực tiếp.",
        ),
      );
    pending.clear();
  };
  function call(cmd, data = {}) {
    return new Promise((resolve, reject) => {
      const id = ++next;
      pending.set(id, { resolve, reject });
      worker.postMessage({ id, cmd, ...data });
    });
  }
  await call("load", { record });
  return {
    generate: async (messages, max_tokens = 96) =>
      (await call("generate", { messages, max_tokens })).text,
    unload: () => call("unload"),
    interruptGenerate: () => worker.postMessage({ cmd: "stop" }),
  };
}
