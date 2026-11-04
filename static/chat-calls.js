/* WebRTC media stays on peer connections; authenticated HTTP carries signaling. */
(() => {
  "use strict";
  const C = window.DHDChat;
  if (!C) return;
  const $ = (id) => document.getElementById(id);
  const device = crypto.randomUUID();
  let call = null,
    stream = null,
    ice = [],
    cursor = 0,
    timer = null,
    polling = false,
    starting = false;
  const peers = new Map();
  const callURL = (suffix) => C.roomAPI(`calls/${call.id}/${suffix}`);
  const notice = (message) => {
    $("chat-call-help").textContent = message;
    $("chat-call-help").hidden = !message;
  };
  function mediaError(e) {
    if (["NotAllowedError", "SecurityError"].includes(e.name))
      return "Chưa được cấp quyền micro/camera. Bấm biểu tượng quyền bên cạnh địa chỉ trang để cho phép, rồi thử lại.";
    if (e.name === "NotFoundError")
      return "Không tìm thấy micro/camera. Kiểm tra thiết bị hoặc thử gọi thoại.";
    if (e.name === "NotReadableError")
      return "Micro/camera đang được ứng dụng khác sử dụng. Đóng ứng dụng đó rồi thử lại.";
    return e.message || "Không mở được cuộc gọi.";
  }
  async function getMedia(mode) {
    if (!navigator.mediaDevices?.getUserMedia || !window.RTCPeerConnection)
      throw new Error(
        "Trình duyệt chưa hỗ trợ gọi trên trang này. Dùng Chrome, Edge hoặc Safari mới qua HTTPS.",
      );
    return navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true },
      video:
        mode === "VIDEO"
          ? {
              width: { ideal: 640 },
              height: { ideal: 480 },
              frameRate: {
                ideal: C.getRoom()?.kind === "GROUP" ? 15 : 24,
                max: 24,
              },
            }
          : false,
    });
  }
  function tile(id, name, local = false) {
    const wrapper = C.node("div", "chat-call-tile");
    wrapper.dataset.peer = id;
    wrapper.append(
      C.node(
        "strong",
        "",
        name.split(/\s+/).slice(-1)[0][0]?.toUpperCase() || "D",
      ),
    );
    const video = C.node("video", local ? "is-local" : "");
    video.autoplay = true;
    video.playsInline = true;
    video.muted = local;
    wrapper.append(video, C.node("span", "", name + (local ? " · Bạn" : "")));
    $("chat-call-grid").append(wrapper);
    return { wrapper, video };
  }
  function play(video) {
    video.play().catch(() => {
      const button = C.node(
        "button",
        "chat-call-control",
        "Bấm để phát âm thanh",
      );
      button.type = "button";
      button.style.zIndex = "2";
      button.onclick = () =>
        video
          .play()
          .then(() => button.remove())
          .catch(() =>
            notice(
              "Trình duyệt chưa cho phát âm thanh. Kiểm tra quyền âm thanh của trang.",
            ),
          );
      video.parentElement.append(button);
    });
  }
  async function attach(result) {
    call = result.call;
    ice = result.ice_servers;
    cursor = 0;
    $("chat-call-grid").replaceChildren();
    const self = tile(C.boot.user_id, "Bạn", true);
    self.video.srcObject = stream;
    if (call.mode === "AUDIO") self.video.hidden = true;
    play(self.video);
    $("chat-call-title").textContent =
      (call.mode === "VIDEO" ? "Gọi video" : "Gọi thoại") +
      " · " +
      C.getRoom().title;
    $("chat-call-status").textContent = "Đang mời thành viên…";
    $("chat-call-camera").hidden = call.mode !== "VIDEO";
    $("chat-call-camera").textContent = "▣ Camera bật";
    $("chat-call-camera").classList.remove("is-off");
    $("chat-call-mic").textContent = "🎙 Micro bật";
    $("chat-call-mic").classList.remove("is-off");
    notice("");
    if (document.getElementById("chat-incoming")?.open)
      document.getElementById("chat-incoming").close();
    if (!$("chat-call-dialog").open) $("chat-call-dialog").showModal();
    await poll();
  }
  function cleanup() {
    clearTimeout(timer);
    for (const p of peers.values()) {
      p.pc.onicecandidate = null;
      p.pc.close();
      p.wrapper.remove();
    }
    peers.clear();
    if (stream) for (const track of stream.getTracks()) track.stop();
    stream = null;
    call = null;
    cursor = 0;
    if ($("chat-call-dialog").open) $("chat-call-dialog").close();
    $("chat-call-grid").replaceChildren();
  }
  async function start(mode) {
    if (starting || call) return;
    starting = true;
    try {
      stream = await getMedia(mode);
      const result = await C.api(
        C.roomAPI("calls/"),
        { mode, client_key: crypto.randomUUID(), device_key: device },
        "POST",
      );
      if (result.call.status === "ENDED")
        throw new Error("Cuộc gọi trước đã kết thúc. Vui lòng thử lại.");
      await attach(result);
    } catch (e) {
      cleanup();
      C.error(mediaError(e));
    } finally {
      starting = false;
    }
  }
  async function join() {
    if (starting || call) return;
    const active = C.getCall();
    if (!active) return;
    starting = true;
    try {
      stream = await getMedia(active.mode);
      const result = await C.api(
        C.roomAPI(`calls/${active.id}/action/`),
        { command: "join", device_key: device },
        "POST",
      );
      if (result.call.status === "ENDED")
        throw new Error("Cuộc gọi đã kết thúc.");
      await attach(result);
    } catch (e) {
      cleanup();
      C.error(mediaError(e));
    } finally {
      starting = false;
    }
  }
  async function signal(target, kind, payload, key = crypto.randomUUID()) {
    if (!call) return;
    return C.api(
      callURL("signal/"),
      { target, kind, payload, client_key: key, device_key: device },
      "POST",
    );
  }
  async function createPeer(remote) {
    const existing = peers.get(remote.id);
    if (existing) return existing;
    const { wrapper, video } = tile(remote.id, remote.name);
    const pc = new RTCPeerConnection({ iceServers: ice });
    const p = {
      pc,
      wrapper,
      video,
      candidates: [],
      offerKey: crypto.randomUUID(),
    };
    peers.set(remote.id, p);
    if (call.mode === "AUDIO") video.hidden = true;
    for (const track of stream.getTracks()) {
      const sender = pc.addTrack(track, stream);
      if (track.kind === "video") {
        const parameters = sender.getParameters();
        parameters.encodings = parameters.encodings?.length
          ? parameters.encodings
          : [{}];
        parameters.encodings[0].maxBitrate =
          C.getRoom().kind === "GROUP" ? 400000 : 1000000;
        sender.setParameters(parameters).catch(() => {});
      }
    }
    pc.ontrack = (event) => {
      video.srcObject = event.streams[0] || new MediaStream([event.track]);
      play(video);
    };
    pc.onicecandidate = (event) => {
      if (event.candidate)
        signal(remote.id, "ICE", event.candidate.toJSON()).catch(() =>
          notice(
            "Kết nối mạng chập chờn. Hệ thống đang thử tiếp các đường kết nối.",
          ),
        );
    };
    pc.onicegatheringstatechange = async () => {
      if (
        pc.iceGatheringState !== "complete" ||
        pc.connectionState === "closed"
      )
        return;
      const stats = await pc.getStats();
      if (![...stats.values()].some((s) => s.type === "local-candidate")) {
        notice(
          "Mạng hiện tại chưa tạo được đường truyền cuộc gọi. Cần cấu hình TURN hoặc thử một mạng khác.",
        );
      }
    };
    pc.onconnectionstatechange = () => {
      if (pc.connectionState === "connected") {
        notice("");
        $("chat-call-status").textContent = "Đã kết nối";
      } else if (pc.connectionState === "failed") {
        notice(
          "Chưa nối được âm thanh/video. Một số mạng công ty cần máy chủ chuyển tiếp TURN. Hãy thử mạng khác hoặc nhờ quản trị viên kiểm tra cấu hình gọi.",
        );
      } else if (pc.connectionState === "disconnected")
        notice(
          "Kết nối đang gián đoạn. Kiểm tra mạng của bạn và người tham gia.",
        );
    };
    if (C.boot.user_id < remote.id) {
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      await signal(
        remote.id,
        "OFFER",
        { type: pc.localDescription.type, sdp: pc.localDescription.sdp },
        p.offerKey,
      );
    }
    return p;
  }
  async function syncRoster(data) {
    const joined = data.participants.filter(
      (p) => p.state === "JOINED" && p.id !== C.boot.user_id,
    );
    for (const [id, p] of peers) {
      if (!joined.some((j) => j.id === id)) {
        p.pc.close();
        p.wrapper.remove();
        peers.delete(id);
      }
    }
    for (const remote of joined) await createPeer(remote);
    $("chat-call-status").textContent = joined.length
      ? `${joined.length + 1} người tham gia`
      : "Đang chờ người nghe…";
  }
  async function receive(event, data) {
    const remote = data.participants.find(
      (p) => p.id === event.sender && p.state === "JOINED",
    );
    if (!remote) return;
    const p = await createPeer(remote);
    if (event.kind === "ICE") {
      if (p.pc.remoteDescription) await p.pc.addIceCandidate(event.payload);
      else p.candidates.push(event.payload);
      return;
    }
    if (event.kind === "OFFER") {
      await p.pc.setRemoteDescription(event.payload);
      for (const candidate of p.candidates.splice(0))
        await p.pc.addIceCandidate(candidate);
      const answer = await p.pc.createAnswer();
      await p.pc.setLocalDescription(answer);
      await signal(remote.id, "ANSWER", {
        type: p.pc.localDescription.type,
        sdp: p.pc.localDescription.sdp,
      });
    } else if (
      event.kind === "ANSWER" &&
      p.pc.signalingState === "have-local-offer"
    ) {
      await p.pc.setRemoteDescription(event.payload);
      for (const candidate of p.candidates.splice(0))
        await p.pc.addIceCandidate(candidate);
    }
  }
  async function poll() {
    if (!call || polling) return;
    polling = true;
    const activeId = call.id;
    try {
      const beat = await C.api(
        callURL("action/"),
        { command: "heartbeat", device_key: device },
        "POST",
      );
      if (!call || call.id !== activeId) return;
      if (beat.call.status === "ENDED") {
        cleanup();
        C.error("");
        C.refresh();
        return;
      }
      const mine = beat.call.participants.find((p) => p.id === C.boot.user_id);
      if (mine?.state !== "JOINED") {
        cleanup();
        C.error("Bạn không còn tham gia cuộc gọi này.");
        return;
      }
      call = beat.call;
      await syncRoster(call);
      const result = await C.api(
        callURL("events/") +
          `?after=${cursor}&device_key=${encodeURIComponent(device)}`,
      );
      if (!call || call.id !== activeId) return;
      if (result.call.status === "ENDED") {
        cleanup();
        C.refresh();
        return;
      }
      for (const event of result.signals) {
        await receive(event, result.call);
        cursor = Math.max(cursor, event.id);
      }
    } catch (e) {
      if (call) notice(e.message);
    } finally {
      polling = false;
      if (call) {
        clearTimeout(timer);
        timer = setTimeout(poll, 1800);
      }
    }
  }
  async function leave() {
    if (!call) {
      cleanup();
      return;
    }
    const url = callURL("action/");
    cleanup();
    try {
      await C.api(url, { command: "leave", device_key: device }, "POST");
    } catch (e) {
      C.error(e.message);
    }
    C.refresh();
  }
  $("chat-audio")?.addEventListener("click", () => start("AUDIO"));
  $("chat-video")?.addEventListener("click", () => start("VIDEO"));
  $("chat-join").onclick = join;
  $("chat-decline").onclick = async () => {
    const active = C.getCall();
    if (!active) return;
    try {
      await C.api(
        C.roomAPI(`calls/${active.id}/action/`),
        { command: "decline", device_key: device },
        "POST",
      );
      C.refresh();
    } catch (e) {
      C.error(e.message);
    }
  };
  $("chat-call-leave").onclick = leave;
  $("chat-call-dialog").addEventListener("cancel", (event) => {
    event.preventDefault();
    leave();
  });
  $("chat-call-mic").onclick = () => {
    if (!stream) return;
    const tracks = stream.getAudioTracks(),
      enabled = !tracks[0]?.enabled;
    for (const track of tracks) track.enabled = enabled;
    $("chat-call-mic").textContent = enabled ? "🎙 Micro bật" : "🎙 Micro tắt";
    $("chat-call-mic").classList.toggle("is-off", !enabled);
  };
  $("chat-call-camera").onclick = () => {
    if (!stream) return;
    const tracks = stream.getVideoTracks(),
      enabled = !tracks[0]?.enabled;
    for (const track of tracks) track.enabled = enabled;
    $("chat-call-camera").textContent = enabled
      ? "▣ Camera bật"
      : "▣ Camera tắt";
    $("chat-call-camera").classList.toggle("is-off", !enabled);
    const video = $("chat-call-grid").querySelector("video.is-local");
    if (video) video.hidden = !enabled;
  };
  window.addEventListener("chat-room-call", (event) => {
    const active = event.detail;
    $("chat-room-call").hidden = !active || active.status === "ENDED" || !!call;
    if (active) {
      $("chat-room-call-label").textContent =
        `${active.initiator_name} đang ${active.mode === "VIDEO" ? "gọi video" : "gọi thoại"}. Tối đa 6 người.`;
    }
  });
  window.addEventListener("chat-access-denied", () => {
    if (call) {
      cleanup();
      C.error(
        "Quyền hoặc thành viên hội thoại đã thay đổi. Cuộc gọi trên thiết bị này đã dừng.",
      );
    }
  });
  window.addEventListener("pagehide", () => {
    if (!call) return;
    const url = callURL("action/");
    cleanup();
    fetch(url, {
      method: "POST",
      credentials: "same-origin",
      keepalive: true,
      headers: { "Content-Type": "application/json", "X-CSRFToken": C.csrf() },
      body: JSON.stringify({ command: "leave", device_key: device }),
    }).catch(() => {});
  });
})();
