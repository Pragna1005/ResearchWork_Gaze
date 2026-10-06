document.getElementById("export-annotations").onclick = () => {
  window.postMessage({ type: "REQUEST_ANNOTATIONS" }, "*");
};

document.getElementById("export-mouse").onclick = () => {
  window.postMessage({ type: "REQUEST_MOUSE_LOGS" }, "*");
};

window.addEventListener("message", (event) => {
  if (event.source !== window) return;

  if (event.data.type === "ANNOTATIONS_DATA") {
    const data = event.data.data || [];
    if (data.length === 0) return alert("No annotations found.");

    const headers = ["blockId", "timestamp", "helpfulness", "tag", "x", "y", "width", "height","x_screen","y_screen","content"];
    const rows = [headers.join(",")];

    data.forEach(row => {
      const line = headers.map(h => `"${(row[h] || "").toString().replace(/"/g, '""')}"`).join(",");
      rows.push(line);
    });

    downloadCSV(rows.join("\n"), "annotations.csv");
  }

  if (event.data.type === "MOUSE_DATA") {
    const data = event.data.data || [];
    if (data.length === 0) return alert("No mouse data found.");

    const headers = ["type", "x", "y", "timestamp"];
    const rows = [headers.join(",")];

    data.forEach(row => {
      const line = headers.map(h => `"${(row[h] || "").toString().replace(/"/g, '""')}"`).join(",");
      rows.push(line);
    });

    downloadCSV(rows.join("\n"), "mouse_log.csv");
  }
});

function downloadCSV(content, filename) {
  const blob = new Blob([content], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
}
