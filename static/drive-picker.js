(() => {
  const button = document.getElementById("choose-drive-folder");
  if (!button) return;
  const status = document.getElementById("drive-status"),
    config = JSON.parse(document.getElementById("picker-config").textContent);
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const response = await fetch(button.dataset.tokenUrl, {
        method: "POST",
        headers: {
          "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")
            .value,
        },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error);
      await new Promise((resolve, reject) =>
        gapi.load("picker", {
          callback: resolve,
          onerror: () => reject(new Error("Không tải được bộ chọn Google.")),
        }),
      );
      const view = new google.picker.DocsView(google.picker.ViewId.FOLDERS)
        .setIncludeFolders(true)
        .setSelectFolderEnabled(true);
      const picker = new google.picker.PickerBuilder()
        .addView(view)
        .setOAuthToken(data.access_token)
        .setDeveloperKey(config.key)
        .setAppId(config.appId)
        .setOrigin(location.origin)
        .setTitle("Chọn đúng thư mục lưu trữ đã chỉ định")
        .setCallback((result) => {
          if (result.action === google.picker.Action.PICKED) {
            document.getElementById("drive-folder-id").value =
              result.docs[0].id;
            document.getElementById("drive-folder-form").submit();
          }
        })
        .build();
      picker.setVisible(true);
    } catch (error) {
      status.textContent = error.message || "Không mở được Google Picker.";
    } finally {
      button.disabled = false;
    }
  });
})();
