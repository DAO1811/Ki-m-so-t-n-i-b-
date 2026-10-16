(() => {
  const money = (value) =>
    new Intl.NumberFormat("vi-VN", {
      style: "currency",
      currency: "VND",
      maximumFractionDigits: 0,
    }).format(value);
  const short = (value) =>
    new Intl.NumberFormat("vi-VN", {
      notation: "compact",
      maximumFractionDigits: 1,
    }).format(value);
  const el = (name, attrs = {}, text) => {
    const node = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
    if (text !== undefined) node.textContent = text;
    return node;
  };
  function empty(container, description) {
    const div = document.createElement("div");
    div.className = "chart-empty";
    const title = document.createElement("b");
    title.textContent = "Chưa có dữ liệu phát sinh";
    const detail = document.createElement("span");
    detail.textContent = description;
    div.append(title, detail);
    container.append(div);
  }
  const activity = JSON.parse(
    document.getElementById("activity-data").textContent,
  );
  const container = document.getElementById("activity-chart");
  if (!activity.length)
    empty(
      container,
      "Phiếu nhập và xuất đã duyệt trong khoảng ngày chọn sẽ được thể hiện ở đây.",
    );
  else {
    const W = 620,
      H = 240,
      left = 57,
      right = 15,
      top = 15,
      bottom = 38,
      pw = W - left - right,
      ph = H - top - bottom;
    const svg = el("svg", {
      viewBox: `0 0 ${W} ${H}`,
      role: "img",
      "aria-label": "Giá trị nhập và xuất trong kỳ",
    });
    const max =
      Math.max(...activity.flatMap((r) => [r.inbound, r.outbound]), 1) * 1.15;
    for (let i = 0; i <= 4; i++) {
      const y = top + ph - (i / 4) * ph;
      svg.append(
        el("line", {
          x1: left,
          y1: y,
          x2: W - right,
          y2: y,
          class: "grid-line",
        }),
        el(
          "text",
          { x: left - 8, y: y + 3, "text-anchor": "end" },
          short((max * i) / 4),
        ),
      );
    }
    const step = pw / activity.length,
      bar = Math.min(18, step * 0.28);
    activity.forEach((row, index) => {
      const center = left + step * (index + 0.5);
      for (const [key, color, offset] of [
        ["inbound", "#09b98b", -bar - 1],
        ["outbound", "#f34c57", 1],
      ]) {
        const height = (row[key] / max) * ph;
        const rect = el("rect", {
          x: center + offset,
          y: top + ph - height,
          width: bar,
          height: Math.max(height, row[key] > 0 ? 1 : 0),
          rx: 2,
          fill: color,
        });
        rect.append(
          el(
            "title",
            {},
            `${row.label} · ${key === "inbound" ? "Nhập" : "Xuất"}: ${money(row[key])}`,
          ),
        );
        svg.append(rect);
      }
      if (
        activity.length <= 12 ||
        index % Math.ceil(activity.length / 10) === 0
      )
        svg.append(
          el(
            "text",
            { x: center, y: H - 15, "text-anchor": "middle" },
            row.label,
          ),
        );
    });
    container.append(svg);
  }
  const warehouses = JSON.parse(
      document.getElementById("warehouse-data").textContent,
    ),
    warehouseContainer = document.getElementById("warehouse-chart");
  if (!warehouses.length)
    empty(
      warehouseContainer,
      "Nhập kho để bắt đầu theo dõi giá trị tồn theo từng kho.",
    );
  else {
    const max = Math.max(...warehouses.map((row) => row.value), 1);
    warehouses.slice(0, 8).forEach((row) => {
      const line = document.createElement("div");
      line.className = "warehouse-bar-row";
      const label = document.createElement("div");
      label.className = "warehouse-bar-label";
      const name = document.createElement("span");
      name.textContent = `${row.label} · ${row.name}`;
      const value = document.createElement("b");
      value.textContent = money(row.value);
      label.append(name, value);
      const track = document.createElement("div");
      track.className = "warehouse-bar-track";
      const fill = document.createElement("div");
      fill.className = "warehouse-bar-fill";
      fill.style.width = `${(row.value / max) * 100}%`;
      track.append(fill);
      line.append(label, track);
      warehouseContainer.append(line);
    });
    if (warehouses.length > 8) {
      const note = document.createElement("p");
      note.className = "caption";
      note.textContent =
        "Hiển thị 8 kho có giá trị cao nhất. Xem đầy đủ trong Báo cáo.";
      warehouseContainer.append(note);
    }
  }
})();
