(() => {
  const byId = (id) => document.getElementById(id);
  let busy = false;

  function showError(message) {
    const notice = byId("notice");
    if (!notice) return;
    notice.textContent = message;
    notice.className = "notice error";
    notice.style.display = "block";
  }

  function fillSelect(select, items, labelFor) {
    const previous = select.value;
    select.replaceChildren();
    for (const item of items) {
      const option = document.createElement("option");
      option.value = item.nick || item.name;
      option.textContent = labelFor(item);
      select.appendChild(option);
    }
    if (items.some((item) => (item.nick || item.name) === previous)) {
      select.value = previous;
    }
  }

  function renderMembers(items) {
    const container = byId("members");
    container.replaceChildren();
    const online = items.filter((item) => item.online);
    byId("memberCount").textContent = `${online.length} online / ${items.length} joined`;
    for (const item of items) {
      const row = document.createElement("div");
      row.className = "member";
      const name = document.createElement("span");
      name.textContent = item.nick;
      const status = document.createElement("span");
      status.className = "small";
      status.textContent = `${item.role} · ${item.online ? "online" : "offline"}`;
      row.append(name, status);
      container.appendChild(row);
    }
    fillSelect(byId("memberTarget"), items, (item) => `${item.nick} (${item.role})`);
    fillSelect(byId("transferTarget"), items, (item) => item.nick);
  }

  function renderBots(items) {
    const container = byId("bots");
    container.replaceChildren();
    for (const item of items) {
      const row = document.createElement("div");
      row.className = "member";
      row.textContent = `@${item.name}`;
      container.appendChild(row);
    }
    fillSelect(byId("botTarget"), items, (item) => `@${item.name}`);
  }

  function wireCommand(buttonId, buildCommand) {
    byId(buttonId).addEventListener("click", () => {
      const command = buildCommand();
      if (command && typeof window.send === "function") {
        window.send(command, byId("roomName").textContent);
      }
    });
  }

  wireCommand("saveTopic", () => `!topic ${byId("topicInput").value.trim()}`);
  wireCommand("clearTopic", () => "!topic clear");
  wireCommand("saveRolePrompt", () => `!role ${byId("rolePromptInput").value.trim() || "clear"}`);
  wireCommand("promoteMember", () => byId("memberTarget").value && `!op ${byId("memberTarget").value}`);
  wireCommand("demoteMember", () => byId("memberTarget").value && `!deop ${byId("memberTarget").value}`);
  wireCommand("createBot", () => {
    const name = byId("botName").value.trim();
    const persona = byId("botPersona").value.trim();
    if (!name || !persona) {
      showError("Enter a bot name and persona.");
      return "";
    }
    return `!bot create ${name} ${persona}`;
  });
  wireCommand("askBot", () => {
    const name = byId("botTarget").value;
    const message = byId("botMessage").value.trim();
    if (!name || !message) {
      showError("Select a bot and enter a message.");
      return "";
    }
    byId("botMessage").value = "";
    return `!bot say ${name} ${message}`;
  });
  wireCommand("sendTransfer", () => {
    const nick = byId("transferTarget").value;
    const page = byId("transferPage").value;
    if (!nick) {
      showError("Select a registered user in this room.");
      return "";
    }
    return `!sendpage ${nick} ${page} ${byId("transferNote").value.trim()}`.trim();
  });

  async function refreshControls() {
    if (busy || !byId("roomName")) return;
    busy = true;
    try {
      const channel = byId("roomName").textContent || "#lobby";
      const response = await fetch(
        `/api/chatserv/state?channel=${encodeURIComponent(channel)}`,
        { credentials: "same-origin" }
      );
      const state = await response.json();
      if (!response.ok || !state.ok) {
        throw new Error(state.error || `HTTP ${response.status}`);
      }
      renderMembers(state.members || []);
      renderBots(state.bots || []);

      const mayModerate = state.platform_admin || ["owner", "op"].includes(state.channel.role);
      byId("discussionOptions").hidden = !mayModerate;
      byId("memberOptions").hidden = !mayModerate;
      byId("pageOptions").hidden = !mayModerate;
      byId("botOptions").hidden = !state.user;
      byId("topicInput").placeholder = state.channel.topic || "Set the room topic";
      if (document.activeElement !== byId("topicInput")) {
        byId("topicInput").value = state.channel.topic || "";
      }
      if (document.activeElement !== byId("rolePromptInput")) {
        byId("rolePromptInput").value = state.channel.role_prompt || "";
      }
    } catch (error) {
      console.error("Unable to refresh ChatServ side controls:", error);
    } finally {
      busy = false;
    }
  }

  refreshControls();
  window.setInterval(refreshControls, 5000);
})();
