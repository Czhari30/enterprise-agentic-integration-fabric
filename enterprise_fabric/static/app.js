const runButton = document.querySelector("#run");
const approveButton = document.querySelector("#approve");
let activeWorkflow = null;

function headers(role = "operator", subject = "demo-maker") {
  return {
    "Content-Type": "application/json",
    "X-Tenant-Id": "tenant-a",
    "X-Subject": subject,
    "X-Roles": role,
    "X-Scopes": "payments:read,integration:read,integration:write,payments:write,customers:restricted:read",
    "X-Clearance": "restricted",
  };
}

function render(data) {
  activeWorkflow = data.workflow_id;
  document.querySelector("#empty-state").classList.add("hidden");
  document.querySelector("#workflow-view").classList.remove("hidden");
  document.querySelector("#workflow-title").textContent = data.workflow_id;
  const badge = document.querySelector("#workflow-status");
  badge.textContent = data.status.replaceAll("_", " ");
  badge.className = `status-badge ${data.status}`;
  document.querySelector("#evidence-count").textContent = data.evidence.length;
  document.querySelector("#tool-count").textContent = data.plan.length;
  document.querySelector("#policy-count").textContent = data.policy_decisions.length;
  document.querySelector("#event-count").textContent = data.events.length;

  document.querySelector("#timeline").innerHTML = data.events.map((event) => `
    <li><strong>${event.type}</strong><span>${event.created_at}</span></li>
  `).join("");
  document.querySelector("#evidence-list").innerHTML = data.evidence.map((item) => `
    <article class="evidence-card">
      <strong>${item.title}</strong>
      <p>${item.excerpt}</p>
      <code>${item.citation} · ${item.score}</code>
    </article>
  `).join("");
  approveButton.classList.toggle("hidden", data.status !== "waiting_approval");
}

runButton.addEventListener("click", async () => {
  runButton.disabled = true;
  runButton.textContent = "Running controls…";
  const nonce = Date.now();
  const response = await fetch("/v1/workflows", {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      request_id: `demo-${nonce}`,
      idempotency_key: `enterprise-demo-${nonce}`,
      intent: document.querySelector("#intent").value,
      amount: Number(document.querySelector("#amount").value),
      currency: document.querySelector("#currency").value,
      metadata: {payment_ref: "PAY-DEMO-1042", message_id: "MSG-DEMO-77"},
    }),
  });
  render(await response.json());
  runButton.disabled = false;
  runButton.innerHTML = "Run governed workflow <span>→</span>";
});

approveButton.addEventListener("click", async () => {
  approveButton.disabled = true;
  const response = await fetch(`/v1/workflows/${activeWorkflow}/approve`, {
    method: "POST",
    headers: headers("approver", "demo-checker"),
    body: JSON.stringify({approval_reference: `APR-${Date.now()}`}),
  });
  render(await response.json());
  approveButton.disabled = false;
});
